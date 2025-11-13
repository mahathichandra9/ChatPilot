from dronekit import connect, VehicleMode, LocationGlobalRelative
import time
import threading
import paho.mqtt.client as mqtt
import pyttsx3
from task_manager import RoverPriorityController, TaskPriority
from rplidar import RPLidar

# =================== CONFIGURATION ===================
PIXHAWK_PORT = '/dev/ttyACM0'
DDSM_PORT = '/dev/ttyACM1'
LIDAR_PORT = '/dev/ttyUSB0'
BAUDRATE = 57600
MIN_DISTANCE = 500  # mm for obstacle detection

# Global variables
vehicle = None
controller = None
engine = None
lidar = None

# =================== MQTT CALLBACKS ===================
def on_connect(client, userdata, flags, rc):
    print(f"MQTT Connected with result code {rc}")
    client.subscribe("chatpilot/rover/command")

def on_message(client, userdata, msg):
    """Handle incoming commands and add to priority controller"""
    global controller
    
    command = msg.payload.decode().strip()
    print(f"\\n📨 MQTT Command Received: {command}")
    
    # Add to priority controller
    if controller:
        task_id = controller.add_task(command)
        print(f"✅ Task queued: {task_id}")

# =================== LIDAR OBSTACLE DETECTION ===================
def lidar_monitoring_thread():
    """Monitor LiDAR for obstacles"""
    global controller, lidar
    
    if not lidar:
        return
    
    try:
        for scan in lidar.iter_scans():
            # Check front sector for obstacles
            front_clear = True
            for (_, angle, distance) in scan:
                if (angle >= 340 or angle <= 20) and 0 < distance < MIN_DISTANCE:
                    front_clear = False
                    break
            
            # If obstacle detected, notify controller
            if not front_clear and controller:
                controller.handle_obstacle_detection()
                time.sleep(2)  # Avoid multiple detections
                
    except Exception as e:
        print(f"LiDAR error: {e}")

# =================== STATUS DISPLAY ===================
def status_display_thread():
    """Display controller status periodically"""
    global controller
    
    while controller:
        status = controller.get_status()
        
        print("\\n" + "="*60)
        print("📊 TASK CONTROLLER STATUS")
        print("-"*60)
        
        if status['current_task']:
            task = status['current_task']
            print(f"▶️  Current: {task['type']} [{task['priority']}] - {task['state']}")
        else:
            print("▶️  Current: None")
        
        print(f"📋 Queued: {status['queued_tasks']} tasks")
        print(f"⏸️  Interrupted: {status['interrupted_tasks']} tasks")
        print(f"✅ Completed: {status['completed_tasks']} tasks")
        
        if status['navigation_active']:
            print("🗺️ Navigation: ACTIVE")
        if status['obstacle_detected']:
            print("🚧 Obstacle: DETECTED")
        
        print("="*60)
        
        time.sleep(5)

# =================== MAIN ===================
def main():
    global vehicle, controller, engine, lidar
    
    print("\\n" + "="*60)
    print("🤖 ROVER PRIORITY TASK CONTROLLER")
    print("="*60)
    
    # Initialize TTS
    engine = pyttsx3.init()
    engine.say("Initializing rover priority controller")
    engine.runAndWait()
    
    # Connect to Pixhawk
    print("\\n📡 Connecting to Pixhawk...")
    try:
        vehicle = connect(PIXHAWK_PORT, baud=BAUDRATE, wait_ready=False)
        print("✅ Pixhawk connected")
        
        # Arm vehicle
        print("🔓 Arming vehicle...")
        vehicle.armed = True
        while not vehicle.armed:
            time.sleep(1)
        vehicle.mode = VehicleMode("GUIDED")
        print(f"✅ Vehicle armed in {vehicle.mode.name} mode")
    except Exception as e:
        print(f"❌ Pixhawk connection failed: {e}")
        vehicle = None
    
    # Initialize Priority Controller
    print("\\n🎮 Initializing Priority Controller...")
    controller = RoverPriorityController(ddsm_port=DDSM_PORT, vehicle=vehicle)
    controller.start()
    print("✅ Priority Controller started")
    
    # Initialize LiDAR
    try:
        print("\\n📡 Initializing LiDAR...")
        lidar = RPLidar(LIDAR_PORT)
        lidar_thread = threading.Thread(target=lidar_monitoring_thread, daemon=True)
        lidar_thread.start()
        print("✅ LiDAR monitoring started")
    except Exception as e:
        print(f"⚠️ LiDAR initialization failed: {e}")
    
    # Start status display
    status_thread = threading.Thread(target=status_display_thread, daemon=True)
    status_thread.start()
    
    # Initialize MQTT
    print("\\n📡 Connecting to MQTT broker...")
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect("13.232.191.178", 1883, 60)
    mqtt_client.loop_start()
    print("✅ MQTT connected")
    
    print("\\n" + "="*60)
    print("🚀 SYSTEM READY - Waiting for commands...")
    print("="*60)
    
    try:
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\\n\\n⛔ Shutdown requested...")
        
    finally:
        # Cleanup
        print("🔄 Cleaning up...")
        
        if controller:
            controller.stop()
        
        if vehicle:
            vehicle.armed = False
            vehicle.close()
        
        if lidar:
            lidar.stop()
            lidar.stop_motor()
            lidar.disconnect()
        
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        
        print("✅ Shutdown complete")

if __name__ == "__main__":
    main()