import sys
import termios
import tty
import serial
import json
import time
from dronekit import connect, VehicleMode
import os

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


def get_location():
    global vehicle
    loc = vehicle.location.global_frame
    return (loc.lat, loc.lon, loc.alt)
# ==============================
# Main Control Loop
# ==============================
def main():
    
    print("connected")  
    rover = Rover()
    speed = 80  # base motor speed
    print("\n🎮 Rover Keyboard Controller (Skid Steering)")
    print("============================================")
    print("Use keys:")
    print("   W - Forward")
    print("   S - Backward")
    print("   A - Turn Left")
    print("   D - Turn Right")
    print("   Space - Stop")
    print("   Q - Quit")
    print("   R - Record")
    print("============================================\n")

    try:
        while True:
            key = getch().lower()

            if key == 'w':
                rover.set_motor_speeds(speed, speed)
            elif key == 's':
                rover.set_motor_speeds(-speed, -speed)
            elif key == 'a':
                rover.set_motor_speeds(30, -30)
            elif key == 'd':
                rover.set_motor_speeds(-30, 30)
            elif key == ' ':
                rover.stop()
            elif key == 'q':
                rover.stop()
                print("👋 Exiting rover control...")
                break
            

            if key == 'r':
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
        rover.stop()
        rover.ddsm_ser.close()
        print("\n🛑 Keyboard interrupt — Rover stopped safely")


vehicle = connect('/dev/ttyACM0', wait_ready=False)
if __name__ == "__main__":
    main()
