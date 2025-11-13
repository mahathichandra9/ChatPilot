import heapq
import threading
import time
import json
import serial
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging
import paho.mqtt.client as mqtt
from AStarSearch import a_star

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Priority Levels (lower number = higher priority)
class TaskPriority(IntEnum):
    EMERGENCY = 0    # Emergency stops, obstacle avoidance
    HIGH = 1         # Critical navigation
    MEDIUM = 2       # Normal navigation, route changes
    LOW = 3          # Basic movements

class TaskState(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    QUEUED = "queued"

class TaskType(Enum):
    EMERGENCY_STOP = "stop"
    OBSTACLE_AVOIDANCE = "obstacle_avoidance"
    NAVIGATE = "navigate"
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"

@dataclass
class RoverTask:
    task_id: str
    task_type: TaskType
    priority: TaskPriority
    command: str
    parameters: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    state: TaskState = TaskState.PENDING
    duration: float = 0.0  # Expected duration in seconds
    
    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at

class RoverPriorityController:
    """Priority-based task controller with actual motor control"""
    
    def __init__(self, ddsm_port='/dev/ttyACM1', vehicle=None):
        # Task management
        self.task_queue: List[RoverTask] = []
        self.current_task: Optional[RoverTask] = None
        self.interrupted_tasks: List[RoverTask] = []
        self.completed_tasks: List[RoverTask] = []
        
        # Control parameters
        self.FORWARD_SPEED = 40
        self.BACKWARD_SPEED = -40
        self.TURN_SPEED = 30
        
        # Hardware connections
        self.vehicle = vehicle
        self.ddsm_ser = None
        self.init_motor_serial(ddsm_port)
        
        # Threading
        self.running = False
        self.lock = threading.Lock()
        self.executor_thread = None
        self.current_task_thread = None
        self.stop_current_task = threading.Event()
        
        # Navigation state
        self.navigation_active = False
        self.current_path = []
        self.current_waypoint = 0
        
        # Obstacle handling
        self.obstacle_detected = False
        
    def init_motor_serial(self, port):
        """Initialize serial connection for motor control"""
        try:
            self.ddsm_ser = serial.Serial(port, baudrate=115200)
            self.ddsm_ser.setRTS(False)
            self.ddsm_ser.setDTR(False)
            logger.info(f"Motor serial connected on {port}")
        except Exception as e:
            logger.error(f"Failed to connect motor serial: {e}")
    
    def motor_control(self, left: int, right: int):
        """Direct motor control - THIS IS THE ACTUAL ACTION"""
        if not self.ddsm_ser:
            logger.error("Motor serial not connected!")
            return
            
        cmd_right = {"T": 10010, "id": 2, "cmd": -right, "act": 3}
        cmd_left = {"T": 10010, "id": 1, "cmd": left, "act": 3}
        
        try:
            self.ddsm_ser.write((json.dumps(cmd_right) + '\\n').encode())
            time.sleep(0.01)
            self.ddsm_ser.write((json.dumps(cmd_left) + '\\n').encode())
            logger.debug(f"Motor command sent: L={left}, R={right}")
        except Exception as e:
            logger.error(f"Motor control error: {e}")
    
    def stop_motors(self):
        """Stop all motors immediately"""
        self.motor_control(0, 0)
        logger.info("🛑 MOTORS STOPPED")
    
    def start(self):
        """Start the priority task controller"""
        self.running = True
        self.executor_thread = threading.Thread(target=self._execution_loop)
        self.executor_thread.start()
        logger.info("Priority controller started")
    
    def stop(self):
        """Stop the controller"""
        self.running = False
        self.stop_current_task.set()
        self.stop_motors()
        if self.executor_thread:
            self.executor_thread.join()
        logger.info("Priority controller stopped")
    
    def add_task(self, command: str, priority: TaskPriority = None) -> str:
        """Add a new task to the priority queue"""
        task = self._create_task(command, priority)
        
        with self.lock:
            # Emergency stop clears everything
            if task.task_type == TaskType.EMERGENCY_STOP:
                logger.warning("⚠️ EMERGENCY STOP - Clearing all tasks")
                self.stop_current_task.set()
                self.task_queue.clear()
                self.current_task = task
                self._execute_emergency_stop()
                return task.task_id
            
            # Check if we should interrupt current task
            if self.current_task and task.priority < self.current_task.priority:
                logger.info(f"Interrupting current task for higher priority: {task.task_type.value}")
                self.stop_current_task.set()
                self.interrupted_tasks.append(self.current_task)
                
            heapq.heappush(self.task_queue, task)
            logger.info(f"📝 Task added: {task.task_id} [{task.priority.name}] - {task.command}")
        
        return task.task_id
    
    def _create_task(self, command: str, priority: Optional[TaskPriority]) -> RoverTask:
        """Create a task from command string"""
        command_upper = command.upper()
        task_id = f"task_{int(time.time() * 1000)}"
        
        # Parse command and assign properties
        if "STOP" in command_upper:
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.EMERGENCY_STOP,
                priority=TaskPriority.EMERGENCY,
                command=command,
                parameters={},
                duration=0
            )
        elif "NAVIGATE" in command_upper:
            try:
                parts = command.split(":", 1)[1].split(",")
                params = {"start": parts[0].strip(), "end": parts[1].strip()}
            except:
                params = {}
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.NAVIGATE,
                priority=priority or TaskPriority.MEDIUM,
                command=command,
                parameters=params,
                duration=30  # Estimated navigation time
            )
        elif "FORWARD" in command_upper:
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.FORWARD,
                priority=priority or TaskPriority.LOW,
                command=command,
                parameters={},
                duration=3
            )
        elif "BACKWARD" in command_upper:
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.BACKWARD,
                priority=priority or TaskPriority.LOW,
                command=command,
                parameters={},
                duration=3
            )
        elif "LEFT" in command_upper:
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.LEFT,
                priority=priority or TaskPriority.LOW,
                command=command,
                parameters={},
                duration=2
            )
        elif "RIGHT" in command_upper:
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.RIGHT,
                priority=priority or TaskPriority.LOW,
                command=command,
                parameters={},
                duration=2
            )
        else:
            return RoverTask(
                task_id=task_id,
                task_type=TaskType.FORWARD,
                priority=priority or TaskPriority.LOW,
                command=command,
                parameters={"raw": command},
                duration=3
            )
    
    def _execution_loop(self):
        """Main execution loop"""
        while self.running:
            with self.lock:
                # Process interrupted tasks first (resume them)
                if self.interrupted_tasks and not self.current_task:
                    self.current_task = self.interrupted_tasks.pop()
                    logger.info(f"📌 Resuming interrupted task: {self.current_task.task_id}")
                
                # Get next task from queue
                if not self.current_task and self.task_queue:
                    self.current_task = heapq.heappop(self.task_queue)
                    logger.info(f"▶️ Starting task: {self.current_task.task_id} [{self.current_task.priority.name}]")
                
                if self.current_task:
                    task = self.current_task
                    self.stop_current_task.clear()
                    
                    # Execute task in separate thread for interruptibility
                    self.current_task_thread = threading.Thread(
                        target=self._execute_task_with_interrupt,
                        args=(task,)
                    )
                    self.current_task_thread.start()
                    self.current_task_thread.join()  # Wait for completion or interruption
                    
                    # Task completed or interrupted
                    if not self.stop_current_task.is_set():
                        self.completed_tasks.append(task)
                        logger.info(f"✅ Task completed: {task.task_id}")
                    
                    self.current_task = None
            
            time.sleep(0.1)
    
    def _execute_task_with_interrupt(self, task: RoverTask):
        """Execute a task with interruption capability"""
        task.state = TaskState.EXECUTING
        
        try:
            if task.task_type == TaskType.FORWARD:
                self._execute_forward(task)
            elif task.task_type == TaskType.BACKWARD:
                self._execute_backward(task)
            elif task.task_type == TaskType.LEFT:
                self._execute_left(task)
            elif task.task_type == TaskType.RIGHT:
                self._execute_right(task)
            elif task.task_type == TaskType.NAVIGATE:
                self._execute_navigation(task)
            elif task.task_type == TaskType.OBSTACLE_AVOIDANCE:
                self._execute_obstacle_avoidance(task)
                
        except Exception as e:
            logger.error(f"Task execution error: {e}")
        finally:
            if self.stop_current_task.is_set():
                task.state = TaskState.INTERRUPTED
                logger.info(f"Task interrupted: {task.task_id}")
            else:
                task.state = TaskState.COMPLETED
    
    # ============ ACTUAL MOVEMENT EXECUTION METHODS ============
    
    def _execute_forward(self, task: RoverTask):
        """Execute forward movement"""
        logger.info("🔼 Executing FORWARD movement")
        self.motor_control(self.FORWARD_SPEED, self.FORWARD_SPEED)
        
        # Run for duration or until interrupted
        start_time = time.time()
        while time.time() - start_time < task.duration:
            if self.stop_current_task.is_set():
                break
            time.sleep(0.1)
        
        self.stop_motors()
    
    def _execute_backward(self, task: RoverTask):
        """Execute backward movement"""
        logger.info("🔽 Executing BACKWARD movement")
        self.motor_control(self.BACKWARD_SPEED, self.BACKWARD_SPEED)
        
        start_time = time.time()
        while time.time() - start_time < task.duration:
            if self.stop_current_task.is_set():
                break
            time.sleep(0.1)
        
        self.stop_motors()
    
    def _execute_left(self, task: RoverTask):
        """Execute left turn"""
        logger.info("◀️ Executing LEFT turn")
        self.motor_control(-self.TURN_SPEED, self.TURN_SPEED)
        
        start_time = time.time()
        while time.time() - start_time < task.duration:
            if self.stop_current_task.is_set():
                break
            time.sleep(0.1)
        
        self.stop_motors()
    
    def _execute_right(self, task: RoverTask):
        """Execute right turn"""
        logger.info("▶️ Executing RIGHT turn")
        self.motor_control(self.TURN_SPEED, -self.TURN_SPEED)
        
        start_time = time.time()
        while time.time() - start_time < task.duration:
            if self.stop_current_task.is_set():
                break
            time.sleep(0.1)
        
        self.stop_motors()
    
    def _execute_emergency_stop(self):
        """Execute emergency stop immediately"""
        logger.critical("🚨 EMERGENCY STOP EXECUTED")
        self.stop_motors()
        self.navigation_active = False
        time.sleep(0.5)  # Ensure stop is registered
    
    def _execute_navigation(self, task: RoverTask):
        """Execute navigation with A* path"""
        start = task.parameters.get("start")
        end = task.parameters.get("end")
        
        logger.info(f"🗺️ Executing NAVIGATION: {start} → {end}")
        
        try:
            # Get path from A*
            if start and end and start.isdigit() and end.isdigit():
                path, cost = a_star(int(start), int(end))
                
                if path:
                    logger.info(f"Path found with {len(path)} waypoints, cost={cost:.2f}m")
                    self.navigation_active = True
                    
                    # Navigate through waypoints
                    for i, waypoint in enumerate(path):
                        if self.stop_current_task.is_set():
                            logger.info("Navigation interrupted")
                            break
                        
                        logger.info(f"📍 Waypoint {i+1}/{len(path)}: Node {waypoint['node']}")
                        
                        # Simple navigation: forward for each waypoint
                        self.motor_control(self.FORWARD_SPEED, self.FORWARD_SPEED)
                        time.sleep(2)  # Time to reach waypoint
                        
                        # Brief stop at waypoint
                        self.stop_motors()
                        time.sleep(0.5)
                    
                    self.navigation_active = False
                    logger.info("Navigation completed")
                else:
                    logger.error(f"No path found from {start} to {end}")
            else:
                # For non-numeric navigation (A, B, C)
                logger.info(f"Navigating to named location: {end}")
                self.motor_control(self.FORWARD_SPEED, self.FORWARD_SPEED)
                time.sleep(5)
                self.stop_motors()
                
        except Exception as e:
            logger.error(f"Navigation error: {e}")
        finally:
            self.stop_motors()
            self.navigation_active = False
    
    def _execute_obstacle_avoidance(self, task: RoverTask):
        """Execute obstacle avoidance maneuver"""
        logger.warning("🚧 Executing OBSTACLE AVOIDANCE")
        
        # Stop immediately
        self.stop_motors()
        time.sleep(0.5)
        
        # Turn right
        logger.info("Turning right to avoid obstacle")
        self.motor_control(self.TURN_SPEED, -self.TURN_SPEED)
        time.sleep(1.5)
        
        # Move forward
        logger.info("Moving forward past obstacle")
        self.motor_control(self.FORWARD_SPEED, self.FORWARD_SPEED)
        time.sleep(3)
        
        # Turn left to resume course
        logger.info("Turning left to resume course")
        self.motor_control(-self.TURN_SPEED, self.TURN_SPEED)
        time.sleep(1.5)
        
        self.stop_motors()
        self.obstacle_detected = False
        logger.info("Obstacle avoidance completed")
    
    def handle_obstacle_detection(self):
        """Called when obstacle is detected"""
        with self.lock:
            if not self.obstacle_detected:
                self.obstacle_detected = True
                logger.warning("⚠️ OBSTACLE DETECTED")
                
                # Create high-priority obstacle avoidance task
                obstacle_task = RoverTask(
                    task_id=f"obstacle_{int(time.time() * 1000)}",
                    task_type=TaskType.OBSTACLE_AVOIDANCE,
                    priority=TaskPriority.HIGH,
                    command="OBSTACLE_AVOIDANCE",
                    parameters={},
                    duration=6
                )
                
                # Interrupt current task if needed
                if self.current_task:
                    self.stop_current_task.set()
                
                # Add to front of queue
                heapq.heappush(self.task_queue, obstacle_task)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current controller status"""
        with self.lock:
            return {
                'current_task': {
                    'id': self.current_task.task_id,
                    'type': self.current_task.task_type.value,
                    'priority': self.current_task.priority.name,
                    'state': self.current_task.state.value
                } if self.current_task else None,
                'queued_tasks': len(self.task_queue),
                'interrupted_tasks': len(self.interrupted_tasks),
                'completed_tasks': len(self.completed_tasks),
                'navigation_active': self.navigation_active,
                'obstacle_detected': self.obstacle_detected
            }