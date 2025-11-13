from dronekit import connect, VehicleMode, LocationGlobalRelative
import math
import time
import serial
import json

# =================== CONSTANTS ===================
PIXHAWK_PORT = '/dev/ttyACM0'   # Pixhawk serial port
DDSM_PORT = '/dev/ttyACM1'
SERIAL_BAUDRATE = 115200
BAUDRATE = 57600
TARGET_LAT = 17.3973234  # Replace with your target latitude
TARGET_LON = 78.4899548  # Replace with your target longitude
ALTITUDE = 0.0    
WAYPOINT_REACHED_RADIUS = 0.5      # For rovers, altitude is 0
FILE_NAME = "logged_coordinates.txt"
TURN_SPEED = 30
FORWARD_SPEED = 40

arrived = False
latest_servo1_value = None
latest_servo3_value = None
path = []

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
                except ValueError:
                    print(f"Skipping invalid line: {line.strip()}")
    except FileNotFoundError:
        print(f"File not found: {filename}")
    
    coordinates.reverse()
    return coordinates


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
    global latest_servo1_value, latest_servo3_value, arrived
    print(f"[Navigation] Moving to target: {target_location.lat}, {target_location.lon}")
    vehicle.simple_goto(target_location)

    while True:
        current_location = vehicle.location.global_relative_frame
        dist_to_target = get_haversine_distance(current_location.lat, current_location.lon, target_location.lat, target_location.lon)
        print(f"[Navigation] Distance to target: {dist_to_target:.2f} meters")

        if dist_to_target <= WAYPOINT_REACHED_RADIUS or arrived:
            arrived = False
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
    global path
    path = read_coordinates_from_file(FILE_NAME)
    print(f"[System] Coordinates {path}")

    print("[System] Connecting to Pixhawk...")
    vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
    print("[System] Connection success...")

    @vehicle.on_message('SERVO_OUTPUT_RAW')
    def servo_listener(self, name, message):
        global latest_servo1_value, latest_servo3_value
        latest_servo1_value = message.servo1_raw
        latest_servo3_value = message.servo3_raw

    @vehicle.on_message('MISSION_ITEM_REACHED')
    def item_reached(self, name, message):
        global arrived
        arrived = True
        print(f"[MESSAGE] Reached waypoint: {message.seq}")

    print("[System] Arming vehicle...")
    vehicle.armed = True
    while not vehicle.armed:
        print("[System] Waiting for arming...")
        time.sleep(1)
    print("[System] Vehicle Armed.")

    print("[System] Setting GUIDED mode...")
    vehicle.mode = VehicleMode("GUIDED")
    while vehicle.mode.name != "GUIDED":
        print("[System] Waiting for GUIDED mode...")
        time.sleep(1)
    print(f"[System] Vehicle Mode --> {vehicle.mode.name}")

    try:
        for index, x in enumerate(path):
            target_location = LocationGlobalRelative(x[0], x[1], ALTITUDE)
            goto_position(vehicle, target_location)
            print(f"[System] Reached waypoint {index+1} --> {x[0]}, {x[1]}")
            time.sleep(0.5)
        print("[System] Reached destination")
        motor_control(0, 0)

    except KeyboardInterrupt:
        print("[System] Stopping test...")
        motor_control(0, 0)

    finally:
        vehicle.channels.overrides = {}
        vehicle.close()
        ddsm_ser.close()


main()
