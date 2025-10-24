from dronekit import connect, VehicleMode, LocationGlobalRelative
import math
import time
import threading
import serial
import json
import paho.mqtt.client as mqtt  # Import MQTT library
import pyttsx3
# from playaudio import play_sound
from AStarSearch import a_star

# =================== CONSTANTS ===================
PIXHAWK_PORT = '/dev/ttyACM0'   # Pixhawk serial port
# PIXHAWK_PORT = "tcp:192.168.80.1:5762"
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
ALTITUDE = 0.0    
WAYPOINT_REACHED_RADIUS = 1      # For rovers, altitude is 0
FILE_NAME = "logged_coordinates.txt"  # Changed to cords.txt
TURN_SPEED = 30
FORWARD_SPEED = 40
BACKWARD_SPEED = -40
forward_sound = "moveforward.wav"
stop_sound = "stop.wav"
left_sound = "left.wav"
right_sound = "right.wav"

vehicle = None
arrived = False
latest_servo1_value = None
latest_servo3_value = None
path = []
location_map = {}  # Dictionary to store named locations
engine = None

ddsm_ser = serial.Serial(DDSM_PORT, baudrate=SERIAL_BAUDRATE)
ddsm_ser.setRTS(False)
ddsm_ser.setDTR(False)
print("[System] DDSM Connected")

# =================== MQTT Callbacks ===================
def on_connect(client, userdata, flags, rc):
    print(f"MQTT_CLIENT::Connected with result code {rc}")
    client.subscribe("chatpilot/rover/command")  # Subscribe to the command topic

def on_message(client, userdata, msg):
    global path, vehicle
    command_str = msg.payload.decode()
    command_str = command_str.upper()
    print(f"MQTT_CLIENT::Received command: {command_str}")

    if command_str == "FORWARD":
        print("[System] Received command: FORWARD")
        path = []  # Clear path to prioritize manual control
        motor_control(FORWARD_SPEED, FORWARD_SPEED)
    elif command_str == "LEFT":
        print("[System] Received command: LEFT")
        path = []  # Clear path to prioritize manual control
        motor_control(30, 40)
    elif command_str == "RIGHT":
        print("[System] Received command: RIGHT")
        path = []  # Clear path to prioritize manual control
        motor_control(40, 30)
    elif command_str == "STOP":
        print("[System] Received command: STOP")
        path = []  # Clear path to prioritize manual control
        motor_control(0, 0)
    elif command_str == "BACKWARD":
        print("[System] Command received: BACKWARD")
        motor_control(BACKWARD_SPEED, BACKWARD_SPEED)
    elif command_str.startswith("NAVIGATE"):
        print(f"{command_str}")
        # Navigate: A,B
        parts = command_str.split(":")[1].split(",")
        if len(parts) != 2:
            print("[Error] Invalid NAVIGATE format. Use NAVIGATE:START,END")
            return
        start = parts[0].strip()
        end = parts[1].strip()
        path = a_star(start, end)
        engine.say(f"Navigating from {start} to {end}")
        try:
            for x in path:
                target_location = LocationGlobalRelative(x["coords"][0], x["coords"][1], ALTITUDE)
                goto_position(vehicle, target_location)
                print(f"[System] Reached waypoint {x['node']+1} --> {x[0]}, {x[1]}")
                time.sleep(0.5)
            print("[System] Reached destination")
            motor_control(0, 0)

        except KeyboardInterrupt:
            print("[System] Stopping test...")
            motor_control(0, 0)

# =================== FUNCTIONS ===================

def get_haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates in meters"""
    R = 6371000  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def scale_servo_to_speed(servo_value):
    if servo_value is None:
        return 0
    # Map servo PWM (1000-2000 µs) to speed (-100 to 100)
    return int((servo_value - 1500) / 500 * 100)

def goto_position(vehicle, target_location):
    global latest_servo1_value, latest_servo3_value
    print(f"[Navigation] Moving to target: {target_location.lat}, {target_location.lon}")
    vehicle.simple_goto(target_location)

    while True:
        current_location = vehicle.location.global_relative_frame
        dist_to_target = get_haversine_distance(
            current_location.lat, current_location.lon,
            target_location.lat, target_location.lon
        )
        print(f"[Navigation] Distance to target: {dist_to_target:.2f} meters")

        if dist_to_target <= WAYPOINT_REACHED_RADIUS:
            print("[Navigation] Target Reached!")
            break

        servo1 = latest_servo1_value
        servo3 = latest_servo3_value
        speed_left = scale_servo_to_speed(servo1)
        speed_right = scale_servo_to_speed(servo3)
        motor_control(speed_left, speed_right)
        time.sleep(0.1)

def motor_control(left, right):
    global ddsm_ser
    command_right = {
        "T": 10010,
        "id": 2,
        "cmd": -right,  # reverse polarity for right wheel
        "act": 3
    }
    command_left = {
        "T": 10010,
        "id": 1,
        "cmd": left,
        "act": 3
    }
    ddsm_ser.write((json.dumps(command_right) + '\n').encode())
    time.sleep(0.01)
    ddsm_ser.write((json.dumps(command_left) + '\n').encode())

# =================== MAIN ===================

def main():
    global path, location_map, vehicle, engine

    # Initialize MQTT Client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("13.232.191.178", 1883, 60)
    client.loop_start()
    engine = pyttsx3.init()

    print(f"[System] Loaded named locations: {location_map.keys()}")

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

    print("[System] Setting GUIDED mode...")
    vehicle.mode = VehicleMode("GUIDED")
    print(f"[System] Vehicle Mode --> {vehicle.mode.name}")

    try:
        # Main loop to continuously check for navigation commands or execute existing path
        while True:
            if path:
                print(f"[System] Traversing path: {path}")
                for index, x in enumerate(path):
                    target_location = LocationGlobalRelative(x[0], x[1], ALTITUDE)
                    goto_position(vehicle, target_location)
                    print(f"[System] Reached waypoint {index+1} --> {x[0]}, {x[1]}")
                    time.sleep(0.5)
                print("[System] Reached destination")
                motor_control(0, 0)
                path = []
            time.sleep(1)

    except KeyboardInterrupt:
        print("[System] Stopping test...")
        motor_control(0, 0)

    finally:
        vehicle.channels.overrides = {}
        vehicle.armed = False
        vehicle.close()
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
