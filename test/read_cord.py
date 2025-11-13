from dronekit import connect, VehicleMode
import time
import os
import sys
import termios
import tty
import serial
import json
import time

# ==============================
# Rover Motor Control Interface
# ==============================
class Rover:
    def __init__(self):
        port = "/dev/ttyACM1"
        baud = 115200
        self.left_speed = 0.0
        self.right_speed = 0.0
        self.ddsm_ser = serial.Serial(port, baudrate=baud)
        self.ddsm_ser.setRTS(False)
        self.ddsm_ser.setDTR(False)
        print("✅ Rover control ready (keyboard mode)")

    def set_motor_speeds(self, left, right):
        """Send motor speeds to the rover (replace this with your own hardware logic)."""
        self.left_speed = left
        self.right_speed = right
        command_left = {
            "T": 10010,
            "id": 2,
            "cmd": -left,  # reverse polarity for right wheel
            "act": 3
        }
        command_right = {
            "T": 10010,
            "id": 1,
            "cmd": right,
            "act": 3
        }
        self.ddsm_ser.write((json.dumps(command_right) + '\n').encode())
        time.sleep(0.01)
        self.ddsm_ser.write((json.dumps(command_left) + '\n').encode())
        time.sleep(0.1)
        print(f"⚙️  Left motor: {left:.2f}, Right motor: {right:.2f}")
        # Example UART or motor driver command:
        # serial.write(f"{left},{right}\n".encode())

    def stop(self):
        self.set_motor_speeds(0, 0)
        print("🛑 Rover stopped")

# ==============================
# Keyboard Input Handling
# ==============================
def getch():
    """Read one character from keyboard (works on Linux/macOS terminal)."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# Connect to the vehicle (replace with your connection string)
# vehicle = connect('127.0.0.1:14551', wait_ready=False)
vehicle = connect('127.0.0.1:14550', wait_ready=False)
print("connected")
# vehicle = connect('u', wait_ready=True, baud=57600)

# Function to get current location
def get_location():
    loc = vehicle.location.global_frame
    return (loc.lat, loc.lon, loc.alt)

# Store location every 5 seconds
try:
    while True:
        key = input("Enter 'r' to write to file (or 'q' to quit): ").strip().lower()
        
        if key == 'w':
            rover.set_motor_speeds(speed, speed)
        elif key == 's':
            rover.set_motor_speeds(-speed, -speed)
        elif key == 'a':
            rover.set_motor_speeds(speed, -speed)
        elif key == 'd':
            rover.set_motor_speeds(-speed, speed)
        elif key == ' ':
            rover.stop()
        elif key == 'r':
            location = get_location()
            lat = location[0]
            lon = location[1]
            alt = location[2]
            file_path = os.path.abspath("cords.txt")
            with open(file_path, "a") as file:
                file.write(f"{lat}, {lon}, {alt}\n")
            print(f"[GPS Saved] {lat}, {lon}, {alt}")
            print(f"Wrote to:\n{file_path}\n")
        elif key == 'q':
            print("Exiting program.")
            break
except KeyboardInterrupt:
    print("Location logging stopped by user.")

# Close vehicle connection
vehicle.close()

