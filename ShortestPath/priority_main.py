from dronekit import connect, VehicleMode, LocationGlobalRelative
import math
import time
import serial
import json
import threading
import paho.mqtt.client as mqtt
import pyttsx3
from queue import PriorityQueue
from AStarSearch import a_star

# =================== CONSTANTS ===================
PIXHAWK_PORT = '/dev/ttyACM0'
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
ALTITUDE = 0.0
WAYPOINT_REACHED_RADIUS = 1
FORWARD_SPEED = 40
BACKWARD_SPEED = -40

PRIORITIES = {
    "EMERGENCY_STOP": 3,
    "STOP": 3,
    "RETURN_HOME": 2,
    "NAVIGATE": 1,
    "FORWARD": 0,
    "BACKWARD": 0,
    "LEFT": 0,
    "RIGHT": 0
}

vehicle = None
latest_servo1_value = None
latest_servo3_value = None
path = []
path_total_cost = 0.0
location_map = {}
engine = None
interrupt_event = threading.Event()
command_queue = PriorityQueue()

ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
ddsm_ser.setRTS(False)
ddsm_ser.setDTR(False)
print("[System] DDSM Connected")

# =================== MQTT CALLBACKS ===================
def on_connect(client, userdata, flags, rc):
    print(f"MQTT_CLIENT::Connected with result code {rc}")
    client.subscribe("chatpilot/rover/command")

def on_message(client, userdata, msg):
    """Add incoming commands to the priority queue."""
    command_str = msg.payload.decode().strip()
    print(f"MQTT_CLIENT::Received command: {command_str}")
    cmd_type = command_str.split(":", 1)[0].upper()

    # Determine command priority
    priority = PRIORITIES.get(cmd_type, 0)
    command_queue.put((-priority, command_str))  # Negative for max-heap
    print(f"[Queue] Added {cmd_type} with priority {priority}")

# =================== FUNCTIONS ===================
def get_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def scale_servo_to_speed(servo_value):
    if servo_value is None:
        return 0
    return int((servo_value - 1500) / 500 * 100)

def motor_control(left, right):
    global ddsm_ser
    cmd_right = {"T": 10010, "id": 2, "cmd": -right, "act": 3}
    cmd_left = {"T": 10010, "id": 1, "cmd": left, "act": 3}
    ddsm_ser.write((json.dumps(cmd_right) + '\n').encode())
    time.sleep(0.01)
    ddsm_ser.write((json.dumps(cmd_left) + '\n').encode())

def goto_position(vehicle, target_location):
    if vehicle is None:
        print("[Navigation] No vehicle connected.")
        return

    lat, lon, alt = target_location.lat, target_location.lon, target_location.alt
    print(f"[Navigation] Moving to target: {lat}, {lon}, alt={alt}")
    vehicle.simple_goto(LocationGlobalRelative(lat, lon, alt))

    while not interrupt_event.is_set():
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
            print("[Navigation] Target reached.")
            break

        time.sleep(0.3)

    if interrupt_event.is_set():
        print("[Navigation] Interrupted during movement.")
        motor_control(0, 0)
        return

def execute_command(command_str, mqtt_client):
    """Handles execution of commands."""
    global path, path_total_cost
    interrupt_event.clear()
    cmd = command_str.upper()

    mqtt_client.publish("chatpilot/rover/status", f"EXECUTING:{cmd}")

    if cmd == "FORWARD":
        motor_control(FORWARD_SPEED, FORWARD_SPEED)
    elif cmd == "BACKWARD":
        motor_control(BACKWARD_SPEED, BACKWARD_SPEED)
    elif cmd == "LEFT":
        motor_control(30, 40)
    elif cmd == "RIGHT":
        motor_control(40, 30)
    elif cmd == "STOP" or cmd == "EMERGENCY_STOP":
        motor_control(0, 0)
    elif cmd.startswith("NAVIGATE"):
        try:
            rest = command_str.split(":", 1)[1]
            parts = [p.strip() for p in rest.split(",")]
            if len(parts) != 2:
                print("[Error] Invalid NAVIGATE format. Use NAVIGATE:START,END")
                return
            start = int(parts[0])
            end = int(parts[1])
        except Exception as e:
            print(f"[Error] Parsing NAVIGATE: {e}")
            return

        found_path, total_cost = a_star(start, end)
        if not found_path:
            print(f"[System] No path found from {start} to {end}.")
            return

        path = found_path
        path_total_cost = total_cost
        print(f"[System] Path with {len(path)} waypoints, cost={total_cost:.2f}m")
        engine.say(f"Navigating from {start} to {end}. Distance {round(total_cost, 2)} meters.")
        engine.runAndWait()

        for index, node in enumerate(path):
            if interrupt_event.is_set():
                print("[System] NAVIGATE interrupted.")
                break
            lat, lon = node["coords"][0], node["coords"][1]
            target = LocationGlobalRelative(float(lat), float(lon), ALTITUDE)
            goto_position(vehicle, target)
            print(f"[System] Reached waypoint {index+1}: {lat}, {lon}")
            time.sleep(0.5)
        motor_control(0, 0)
    mqtt_client.publish("chatpilot/rover/status", f"COMPLETED:{cmd}")

def executor_thread(mqtt_client):
    """Continuously checks the queue and executes highest-priority command."""
    while True:
        if not command_queue.empty():
            _, command = command_queue.get()
            # If something is executing, interrupt it first
            if not command_queue.empty():
                interrupt_event.set()
                time.sleep(0.5)
                interrupt_event.clear()
            execute_command(command, mqtt_client)
        time.sleep(0.5)

# =================== MAIN ===================
def main():
    global vehicle, engine
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("13.232.191.178", 1883, 60)
    client.loop_start()

    engine = pyttsx3.init()
    print("[System] Connecting to Pixhawk...")
    vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
    print("[System] Connection success...")

    @vehicle.on_message('SERVO_OUTPUT_RAW')
    def servo_listener(self, name, message):
        global latest_servo1_value, latest_servo3_value
        latest_servo1_value = message.servo1_raw
        latest_servo3_value = message.servo3_raw

    print("[System] Arming vehicle...")
    vehicle.armed = True
    while not vehicle.armed:
        print("[System] Waiting for arming...")
        time.sleep(1)
    print("[System] Vehicle Armed.")
    vehicle.mode = VehicleMode("GUIDED")

    # Start command executor
    threading.Thread(target=executor_thread, args=(client,), daemon=True).start()
    print("[System] Priority command handler started.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[System] Keyboard interrupt, stopping...")
        motor_control(0, 0)
    finally:
        try:
            vehicle.channels.overrides = {}
            vehicle.armed = False
            vehicle.close()
        except Exception:
            pass
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
