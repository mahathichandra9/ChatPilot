from rplidar import RPLidar, RPLidarException
import time
import sys

PORT = '/dev/ttyUSB0'  # Adjust if needed

def main():
    try:
        lidar = RPLidar(PORT, timeout=3)
    except Exception as e:
        print(f"❌ Cannot open LiDAR on {PORT}: {e}")
        sys.exit(1)

    print("✅ LiDAR connected. Streaming data... Ctrl+C to stop.")

    try:
        # Purge stale data if possible
        try:
            lidar._serial.reset_input_buffer()
            lidar._serial.reset_output_buffer()
        except:
            pass

        # Spin-up
        lidar.stop()
        lidar.stop_motor()
        lidar.start_motor()
        time.sleep(2)

        # Stream measurements
        iterator = lidar.iter_measurments(max_buf_meas=500)
        while True:
            try:
                _, quality, angle, distance = next(iterator)
                print(f"Angle {angle:.1f}°, Distance {distance} mm, Quality {quality}")
            except RPLidarException:
                continue
            except StopIteration:
                break
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n🛑 Scan stopped by user")
    finally:
        try:
            lidar.stop()
            lidar.stop_motor()
            lidar.disconnect()
        except:
            pass
        print("✅ LiDAR disconnected")

if __name__ == "__main__":
    main()

