from dronekit import connect, VehicleMode, LocationGlobalRelative
from rplidar import RPLidar
import math
import time
import threading
import serial
import json
from collections import deque

# =================== CONSTANTS ===================
LIDAR_PORT = '/dev/ttyUSB0'     # Lidar port
PIXHAWK_PORT = '/dev/ttyACM0'   # Pixhawk serial port
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
MIN_DISTANCE = 500  # mm (obstacle threshold)
ALTITUDE = 0.0
WAYPOINT_REACHED_RADIUS = 1  # meters
FILE_NAME = "logged_coordinates.txt"
TURN_SPEED = 30
FORWARD_SPEED = 40

# =================== GLOBALS ===================
latest_scan = None
latest_servo1_value = None
latest_servo3_value = None
scan_lock = threading.Lock()
servo_lock = threading.Lock()
scan_buffer = deque(maxlen=5)

# =================== SERIAL ===================
ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
ddsm_ser.setRTS(False)
ddsm_ser.setDTR(False)
print("[System] DDSM Connected")

# =================== FUNCTIONS ===================

def read_coordinates_from_file(filename):
    coordinates = []
    try:
        with open(filename, 'r') as file:
            for line in file:
                line = line.replace(" ", "")
                parts = line.strip().split(',')
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    coordinates.append((lat, lon))
                except:
                    print(f"[File] Skipping invalid line: {line.strip()}")
    except FileNotFoundError:
        print(f"[File] {filename} not found")
    return coordinates

def get_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def lidar_thread_func(lidar):
    global latest_scan
    for scan in lidar.iter_scans():
        scan_buffer.append(scan)
        # Simple averaging over last few scans
        avg_scan = []
        for i in range(len(scan)):
            angles = [s[i][1] for s in scan_buffer]
            dists = [s[i][2] for s in scan_buffer]
            avg_scan.append((0, sum(angles)/len(angles), sum(dists)/len(dists)))
        with scan_lock:
            latest_scan = avg_scan

def is_front_clear():
    with scan_lock:
        scan_data = latest_scan
        if scan_data is None:
            return True
        for (_, angle, dist) in scan_data:
            if (angle >= 340 or angle <= 20) and 0 < dist < MIN_DISTANCE:
                return False
    return True

def is_left_clear():
    with scan_lock:
        scan_data = latest_scan
        if scan_data is None:
            return True
        for (_, angle, dist) in scan_data:
            if (270 <= angle <= 340) and 0 < dist < MIN_DISTANCE+100:
                return False
    return True

def is_right_clear():
    with scan_lock:
        scan_data = latest_scan
        if scan_data is None:
            return True
        for (_, angle, dist) in scan_data:
            if (20 < angle <= 90) and 0 < dist < MIN_DISTANCE+100:
                return False
    return True

def scale_servo_to_speed(servo_value):
    if servo_value is None:
        return 0
    return int((servo_value - 1500) / 500 * 100)

def motor_control(left, right):
    try:
        command_right = {"T": 10010, "id": 2, "cmd": -right, "act": 3}
        command_left = {"T": 10010, "id": 1, "cmd": left, "act": 3}
        ddsm_ser.write((json.dumps(command_right) + '\n').encode())
        time.sleep(0.01)
        ddsm_ser.write((json.dumps(command_left) + '\n').encode())
    except Exception as e:
        print(f"[Motor] Serial write error: {e}")

# ===== Slope-aware speed adjustment =====
def adjust_speed_for_slope(base_speed, vehicle):
    """
    Adjusts speed based on pitch angle.
    Positive pitch: uphill -> increase speed slightly
    Negative pitch: downhill -> decrease speed
    """
    pitch_deg = math.degrees(vehicle.attitude.pitch)
    adjusted_speed = base_speed

    if pitch_deg > 2:  # uphill
        adjusted_speed += 10
        print(f"[Slope] Uphill: {pitch_deg:.2f}°, speed -> {adjusted_speed}")
    elif pitch_deg < -2:  # downhill
        adjusted_speed -= 15
        print(f"[Slope] Downhill: {pitch_deg:.2f}°, speed -> {adjusted_speed}")

    adjusted_speed = max(10, min(80, adjusted_speed))
    return adjusted_speed

# ===== Reactive obstacle avoidance =====
def reactive_avoidance():
    print("[Obstacle] Starting reactive avoidance")
    while not is_front_clear():
        if is_left_clear():
            print("[Obstacle] Turning left")
            motor_control(-TURN_SPEED, TURN_SPEED)
        elif is_right_clear():
            print("[Obstacle] Turning right")
            motor_control(TURN_SPEED, -TURN_SPEED)
        else:
            print("[Obstacle] Trapped! Rotating 180")
            motor_control(TURN_SPEED, -TURN_SPEED)
            time.sleep(2)
        time.sleep(0.5)
    motor_control(FORWARD_SPEED, FORWARD_SPEED)
    time.sleep(0.5)

# ===== Navigation to GPS waypoint =====
def goto_position(vehicle, target_location):
    print(f"[Navigation] Moving to: {target_location.lat}, {target_location.lon}")
    vehicle.simple_goto(target_location)
    while True:
        current_location = vehicle.location.global_relative_frame
        dist_to_target = get_haversine_distance(
            current_location.lat, current_location.lon,
            target_location.lat, target_location.lon
        )
        print(f"[Navigation] Distance to target: {dist_to_target:.2f} m")
        if dist_to_target <= WAYPOINT_REACHED_RADIUS:
            print("[Navigation] Target Reached")
            motor_control(0,0)
            break
        if not is_front_clear():
            reactive_avoidance()
        else:
            with servo_lock:
                speed_left = scale_servo_to_speed(latest_servo1_value)
                speed_right = scale_servo_to_speed(latest_servo3_value)
            speed_left = adjust_speed_for_slope(speed_left, vehicle)
            speed_right = adjust_speed_for_slope(speed_right, vehicle)
            motor_control(speed_left, speed_right)
        time.sleep(0.1)

# =================== MAIN ===================
def main():
    global latest_servo1_value, latest_servo3_value
    path = read_coordinates_from_file(FILE_NAME)
    path = list(reversed(path))
    if not path:
        print("[System] No waypoints found. Exiting.")
        return

    print("[System] Starting LIDAR...")
    lidar = RPLidar(LIDAR_PORT, timeout = 3)
    threading.Thread(target=lidar_thread_func, args=(lidar,), daemon=True).start()
    while latest_scan is None:
        print("[System] Waiting for LIDAR data...")
        time.sleep(1)
    print("[System] LIDAR ready.")

    print("[System] Connecting to Pixhawk...")
    vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
    print("[System] Pixhawk connected")

    @vehicle.on_message('SERVO_OUTPUT_RAW')
    def servo_listener(self, name, message):
        global latest_servo1_value, latest_servo3_value
        with servo_lock:
            latest_servo1_value = message.servo1_raw
            latest_servo3_value = message.servo3_raw

    print("[System] Arming vehicle...")
    vehicle.armed = True
    while not vehicle.armed:
        print("[System] Waiting for arming...")
        time.sleep(1)
    print("[System] Vehicle Armed.")

    vehicle.mode = VehicleMode("GUIDED")
    while vehicle.mode.name != "GUIDED":
        print("[System] Waiting for GUIDED mode...")
        time.sleep(1)
    print(f"[System] Mode --> {vehicle.mode.name}")

    try:
        for idx, wp in enumerate(path):
            target_location = LocationGlobalRelative(wp[0], wp[1], ALTITUDE)
            goto_position(vehicle, target_location)
            print(f"[System] Waypoint {idx+1} reached: {wp[0]}, {wp[1]}")
        print("[System] All waypoints completed")
        motor_control(0,0)

    except KeyboardInterrupt:
        print("[System] Stopping test...")
        motor_control(0,0)

    finally:
        vehicle.channels.overrides = {}
        vehicle.close()
        lidar.stop()
        lidar.stop_motor()
        lidar.disconnect()
        ddsm_ser.close()

main()
