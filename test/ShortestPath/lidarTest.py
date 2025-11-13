import time
from rplidar import RPLidar
import threading

FRONT_ANGLE_RANGE = 30
SIDE_ANGLE_LEFT = 90
SIDE_ANGLE_RIGHT = 270
MIN_DISTANCE_FRONT = 1500
LIDAR_PORT = "/dev/ttyUSB0"

latest_scan = None


def lidar_thread_func(lidar):
    global latest_scan
    for scan in lidar.iter_scans():
        latest_scan = scan

    if (not is_front_clear()):
        motor_control(0, 0)


def is_front_clear():
    global latest_scan
    if latest_scan is None:
        return True

    for (_, angle, dist) in latest_scan:
        if (angle >= 345 or angle <= 15) and (0 < dist < MIN_DISTANCE_FRONT):
            return False
    return True


def is_left_clear():
    global latest_scan
    if latest_scan is None:
        return True

    for (_, angle, dist) in latest_scan:
        if (angle >= 270 or angle <= 340) and (0 < dist < MIN_DISTANCE_FRONT + 100):
            return False
    return True


def main():
    global latest_scan
    print("Connecting to LiDAR...")

    lidar = RPLidar(LIDAR_PORT)
    print("LiDAR connected!")

    # START THREAD — do NOT call the function yourself
    threading.Thread(target=lidar_thread_func, args=(lidar,), daemon=True).start()

    print("Waiting for first scan...")
    while latest_scan is None:
        time.sleep(0.1)

    print("LiDAR ready! Starting checks...\n")

    while True:
        if is_front_clear():
            print("------------ Front clear ----------------")
        else:
            if is_left_clear():
                print("++++++++++++++ Left clear ++++++++++++++")
            else:
                print("================ BLOCKED ================")

        time.sleep(0.1)


main()
