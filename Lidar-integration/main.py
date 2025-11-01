from dronekit import connect, VehicleMode, LocationGlobalRelative
from rplidar import RPLidar, RPLidarException
import math, time, serial, json, threading, sys
import numpy as np
import paho.mqtt.client as mqtt
import pyttsx3
from AStarSearch import a_star

# =================== CONSTANTS ===================
PIXHAWK_PORT = '/dev/ttyACM0'
DDSM_PORT = '/dev/ttyACM1'
LIDAR_PORT = '/dev/ttyUSB0'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
ALTITUDE = 0.0
WAYPOINT_REACHED_RADIUS = 1
FORWARD_SPEED = 40
BACKWARD_SPEED = -40

# LiDAR Config (mm)
STOP_DISTANCE = 700          # Stop if obstacle closer than this
CLEAR_DISTANCE = 1000        # Consider clear if farther than this
FRONT_SECTOR = 30            # ± degrees around front
SIDE_SECTOR = 60             # degrees for side checks
LOOP_DELAY = 0.1

vehicle = None
engine = None
path = []
path_total_cost = 0.0
latest_servo1_value = None
latest_servo3_value = None
obstacle_detected = False

# =================== SERIAL SETUP ===================
try:
    ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
    ddsm_ser.setRTS(False)
    ddsm_ser.setDTR(False)
    print("[System] ✅ DDSM Connected")
except Exception as e:
    print(f"[Error] Cannot open DDSM port: {e}")
    sys.exit(1)

# =================== MQTT CALLBACKS ===================
def on_connect(client, userdata, flags, rc):
    print(f"MQTT_CLIENT::Connected with result code {rc}")
    client.subscribe("chatpilot/rover/command")

def on_message(client, userdata, msg):
    global path, path_total_cost, obstacle_detected

    command_str = msg.payload.decode().strip()
    print(f"MQTT_CLIENT::Received command: {command_str}")

    if obstacle_detected:
        print("[System] Ignoring command — obstacle detected.")
        motor_control(0, 0)
        return

    cmd = command_str.upper()
    if cmd == "FORWARD":
        motor_control(FORWARD_SPEED, FORWARD_SPEED)
    elif cmd == "BACKWARD":
        motor_control(BACKWARD_SPEED, BACKWARD_SPEED)
    elif cmd == "LEFT":
        motor_control(30, 40)
    elif cmd == "RIGHT":
        motor_control(40, 30)
    elif cmd == "STOP":
        motor_control(0, 0)
    elif cmd.startswith("NAVIGATE"):
        try:
            rest = command_str.split(":", 1)[1]
            start, end = map(int, rest.split(","))
        except Exception as e:
            print(f"[Error] Parsing NAVIGATE: {e}")
            return

        found_path, total_cost = a_star(start, end)
        if not found_path:
            print(f"[System] ❌ No path found from {start} to {end}.")
            return

        path[:] = found_path
        path_total_cost = total_cost
        print(f"[System] ✅ Path with {len(path)} waypoints, cost={total_cost:.2f}m")
        engine.say(f"Navigating from {start} to {end}. Distance {round(total_cost, 2)} meters.")
        engine.runAndWait()

# =================== MOTOR CONTROL ===================
def motor_control(left, right):
    global ddsm_ser
    cmd_right = {"T": 10010, "id": 2, "cmd": -right, "act": 3}
    cmd_left = {"T": 10010, "id": 1, "cmd": left, "act": 3}
    ddsm_ser.write((json.dumps(cmd_right) + '\n').encode())
    time.sleep(0.01)
    ddsm_ser.write((json.dumps(cmd_left) + '\n').encode())

# =================== LIDAR THREAD ===================
def lidar_thread():
    global obstacle_detected

    try:
        lidar = RPLidar(LIDAR_PORT, timeout=3)
    except Exception as e:
        print(f"❌ Cannot open LiDAR on {LIDAR_PORT}: {e}")
        return

    print("[LIDAR] ✅ Connected. Starting motor...")

    try:
        lidar.stop()
        lidar.stop_motor()
        lidar.start_motor()
        time.sleep(2)
        iterator = lidar.iter_measurments(max_buf_meas=500)

        print("[LIDAR] 🔄 Scanning...")

        while True:
            readings = []
            for _ in range(100):
                try:
                    _, quality, angle, distance = next(iterator)
                    if distance > 0:
                        readings.append((angle, distance))
                except RPLidarException:
                    continue

            if not readings:
                continue

            # Convert to numpy for fast math
            angles = np.array([a for a, _ in readings])
            distances = np.array([d for _, d in readings])

            def sector_min(center, half_angle):
                mask = ((angles >= (center - half_angle)) & (angles <= (center + half_angle)))
                vals = distances[mask]
                return np.min(vals) if len(vals) else np.inf

            # Sectors
            front = sector_min(0, FRONT_SECTOR)
            left = sector_min(90, SIDE_SECTOR)
            right = sector_min(270, SIDE_SECTOR)

            # Decision logic
            if front < STOP_DISTANCE:
                if not obstacle_detected:
                    print(f"[LIDAR] 🚫 Obstacle detected ahead ({front:.0f} mm). Stopping...")
                    motor_control(0, 0)
                obstacle_detected = True

                if left > CLEAR_DISTANCE:
                    print("[LIDAR] ⬅️ Path clear left — changing lane left.")
                    motor_control(30, 40)
                    time.sleep(1.5)
                    motor_control(0, 0)
                elif right > CLEAR_DISTANCE:
                    print("[LIDAR] ➡️ Path clear right — changing lane right.")
                    motor_control(40, 30)
                    time.sleep(1.5)
                    motor_control(0, 0)
                else:
                    print("[LIDAR] ⛔ Both sides blocked — waiting.")
                    motor_control(0, 0)
            else:
                if obstacle_detected:
                    print("[LIDAR] ✅ Path clear again. Resuming normal operation.")
                obstacle_detected = False

            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\n[LIDAR] Stopping...")

    finally:
        try:
            lidar.stop()
            lidar.stop_motor()
            lidar.disconnect()
        except:
            pass
        print("[LIDAR] ✅ LiDAR disconnected")

# =================== NAVIGATION ===================
def get_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def goto_position(vehicle, target_location):
    global latest_servo1_value, latest_servo3_value

    if vehicle is None:
        print("[Navigation] No vehicle connected.")
        return

    lat, lon, alt = target_location.lat, target_location.lon, target_location.alt
    print(f"[Navigation] Moving to target: {lat}, {lon}, alt={alt}")
    vehicle.simple_goto(LocationGlobalRelative(lat, lon, alt))

    while True:
        if obstacle_detected:
            print("[Navigation] ⛔ Paused — obstacle detected.")
            motor_control(0, 0)
            time.sleep(0.5)
            continue

        current_location = vehicle.location.global_relative_frame
        if not current_location or not current_location.lat:
            print("[Navigation] Waiting for GPS fix...")
            time.sleep(0.5)
            continue

        dist_to_target = get_haversine_distance(
            current_location.lat, current_location.lon,
            lat, lon
        )
        print(f"[Navigation] Distance to target: {dist_to_target:.2f}m")

        if dist_to_target <= WAYPOINT_REACHED_RADIUS:
            print("[Navigation] ✅ Target reached.")
            break

        time.sleep(0.5)

# =================== MAIN ===================
def main():
    global path, path_total_cost, vehicle, engine

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("13.232.191.178", 1883, 60)
    client.loop_start()

    engine = pyttsx3.init()
    print("[System] Connecting to Pixhawk...")
    vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
    print("[System] ✅ Pixhawk connected.")

    # Start LIDAR in background
    threading.Thread(target=lidar_thread, daemon=True).start()

    @vehicle.on_message('SERVO_OUTPUT_RAW')
    def servo_listener(self, name, message):
        global latest_servo1_value, latest_servo3_value
        latest_servo1_value = message.servo1_raw
        latest_servo3_value = message.servo3_raw

    print("[System] Arming vehicle...")
    vehicle.armed = True
    while not vehicle.armed:
        time.sleep(1)
    vehicle.mode = VehicleMode("GUIDED")
    print(f"[System] Vehicle Mode → {vehicle.mode.name}")

    try:
        while True:
            if not obstacle_detected and path:
                print(f"[System] Traversing path ({len(path)} waypoints)...")
                for index, node in enumerate(path):
                    lat, lon = node["coords"]
                    target = LocationGlobalRelative(float(lat), float(lon), ALTITUDE)
                    goto_position(vehicle, target)
                    print(f"[System] Reached waypoint {index+1}: {lat}, {lon}")
                    time.sleep(0.5)
                motor_control(0, 0)
                path.clear()
            time.sleep(1)

    except KeyboardInterrupt:
        print("[System] Keyboard interrupt, stopping...")
        motor_control(0, 0)

    finally:
        try:
            vehicle.armed = False
            vehicle.close()
        except:
            pass
        client.loop_stop()
        client.disconnect()
        print("[System] Shutdown complete.")

if __name__ == "__main__":
    main()
