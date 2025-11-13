import sys
import termios
import tty
import serial
import json
import time
from dronekit import connect, VehicleMode
import os
from sttOnRover import stt
# import pyttsx3

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
        # self.engine = pyttsx3.init()
        print("✅ Rover control ready (keyboard mode)")

    # def talk(self, response):
    #     self.engine.say(response)

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
    print("Connected")
    rover = Rover()
    speed = 40
    print("\n🎮 Rover voice Controller (Skid Steering)")
    print("============================================")
    print("Use keys:")
    print("R - record audio")

    print("============================================\n")

    try:
        while True:
            key = getch().lower()
            if key == 'r':
                command = stt().lower()
                if (command == "forward"):
                    rover.set_motor_speeds(speed, speed)
                    # rover.talk("Moving forward")
                elif (command == "stop"):
                    rover.set_motor_speeds(0, 0)
                    # rover.talk("Stopping rover")
                elif(command == "left"):
                    # rover.talk("Left")
                    rover.set_motor_speeds(30, -30)
                # elif (command == "right"):
                    rover.talk("Right")
                    rover.set_motor_speeds(-30, 30)
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
