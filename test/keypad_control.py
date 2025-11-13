import sys
import termios
import tty
import serial
import json
import time
import threading
import os
import pyttsx3
from dronekit import connect, VehicleMode

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
# RTK Fix Type Monitor Thread
# ==============================
def rtk_monitor(vehicle, stop_event):
    """
    Monitors vehicle.gps_0.fix_type and announces status using pyttsx3.
    Says fix type once on start, repeats 'RTK not fixed' until fixed,
    then says 'Ready!' once when RTK fix achieved.
    """
    engine = pyttsx3.init()
    engine.setProperty('rate', 160)
    last_fix = None
    ready_announced = False

    def announce(text):
        print(f"[RTK_MON] {text}")
        engine.say(text)
        engine.runAndWait()

    fix_descriptions = {
        0: "No GPS",
        1: "No fix",
        2: "2D fix",
        3: "3D fix",
        4: "DGPS fix",
        5: "RTK float",
        6: "RTK fixed"
    }

    # Wait until vehicle.gps_0 is ready
    while not stop_event.is_set():
        try:
            fix_type = vehicle.gps_0.fix_type
            break
        except:
            time.sleep(0.5)
    time.sleep(1)

    # Announce initial fix type
    try:
        fix_type = vehicle.gps_0.fix_type
        fix_name = fix_descriptions.get(fix_type, f"Unknown fix type {fix_type}")
        announce(f"Current GPS fix type is {fix_name}")
    except:
        announce("Unable to read GPS fix type")

    # Loop to monitor RTK status
    while not stop_event.is_set():
        try:
            fix_type = vehicle.gps_0.fix_type
            fix_name = fix_descriptions.get(fix_type, f"Unknown fix type {fix_type}")

            if fix_type == 6:
                if not ready_announced:
                    announce("Ready. RTK fixed.")
                    ready_announced = True
                last_fix = fix_type
            else:
                if fix_type != last_fix:
                    announce(f"GPS fix type is {fix_name}")
                announce("RTK not fixed")
                ready_announced = False
                last_fix = fix_type

        except Exception as e:
            print("[RTK_MON] Error reading GPS fix:", e)
            announce("GPS error")

        time.sleep(3)  # Check every 3 seconds

    engine.stop()
    print("[RTK_MON] Stopped RTK monitoring thread.")


# ==============================
# Main Control Loop
# ==============================
def main():
    global vehicle

    print("[System] Connecting to Pixhawk...")
    vehicle = connect('/dev/ttyACM0', wait_ready=False)
    print("[System] Connected to Pixhawk")

    # Start RTK monitoring thread
    stop_event = threading.Event()
    rtk_thread = threading.Thread(target=rtk_monitor, args=(vehicle, stop_event), daemon=True)
    rtk_thread.start()

    # Rover setup
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
    print("   R - Record GPS")
    print("   Q - Quit")
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
            elif key == 'r':
                location = get_location()
                lat, lon, alt = location
                file_path = os.path.abspath("cords.txt")
                with open(file_path, "a") as file:
                    file.write(f"{lat}, {lon}, {alt}\n")
                print(f"[GPS Saved] {lat}, {lon}, {alt}")
                print(f"Wrote to:\n{file_path}\n")
            elif key == 'q':
                rover.stop()
                print("👋 Exiting rover control...")
                break

    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt — Rover stopped safely")
    finally:
        stop_event.set()
        rover.stop()
        rover.ddsm_ser.close()
        vehicle.close()
        print("✅ Clean exit completed.")


if __name__ == "__main__":
    main()
