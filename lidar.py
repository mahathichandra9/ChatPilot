from rplidar import RPLidar
import matplotlib.pyplot as plt
import math

# ====================== CONFIG ======================
PORT_NAME = '/dev/ttyUSB0'  # Change to your port, e.g. 'COM3' on Windows
lidar = RPLidar(PORT_NAME)

# ====================== SETUP PLOT ======================
plt.ion()
fig = plt.figure()
ax = fig.add_subplot(111, polar=True)
line, = ax.plot([], [], 'b.')
ax.set_rmax(4000)  # Max range in mm (4 meters)
ax.grid(True)
ax.set_title("RPLidar Live Scan", va='bottom')

# ====================== MAIN LOOP ======================
try:
    print("Starting RPLidar... Press Ctrl+C to stop.")
    for scan in lidar.iter_scans():
        angles = []
        distances = []

        # Collect scan data
        for (_, angle, distance) in scan:
            if distance > 0:  # Ignore invalid readings
                angles.append(math.radians(angle))
                distances.append(distance)

        # Update plot
        line.set_xdata(angles)
        line.set_ydata(distances)
        plt.pause(0.001)
        ax.set_rmax(max(distances + [4000]))

except KeyboardInterrupt:
    print("\nStopping LIDAR...")

finally:
    lidar.stop()
    lidar.disconnect()
    print("LIDAR stopped and disconnected.")
