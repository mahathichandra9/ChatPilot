import time
from task_manager import RoverTaskManager, TaskPriority

def test_priority_system():
    """Test the priority-based task system"""
    
    # Initialize task manager
    manager = RoverTaskManager()
    manager.start()
    
    try:
        # Simulate a sequence of commands with different priorities
        print("\\n[TEST] Starting priority task system test...")
        
        # Add low priority task
        print("\\n[1] Adding FORWARD command (LOW priority)")
        manager.add_task("FORWARD", TaskPriority.LOW)
        time.sleep(1)
        
        # Add medium priority navigation
        print("\\n[2] Adding NAVIGATE command (MEDIUM priority)")
        manager.add_task("NAVIGATE:0,5", TaskPriority.MEDIUM)
        time.sleep(1)
        
        # Add another low priority task (should queue)
        print("\\n[3] Adding LEFT command (LOW priority) - should queue")
        manager.add_task("LEFT", TaskPriority.LOW)
        time.sleep(1)
        
        # Emergency stop (should execute immediately)
        print("\\n[4] Adding STOP command (HIGH priority) - should execute immediately")
        manager.add_task("STOP", TaskPriority.HIGH)
        time.sleep(2)
        
        # Check status
        status = manager.get_status()
        print(f"\\n[STATUS] Current state:")
        print(f"  - Current task: {status['current_task']}")
        print(f"  - Queued tasks: {status['queued_tasks']}")
        print(f"  - Completed tasks: {status['completed_tasks']}")
        
        # Let tasks complete
        time.sleep(10)
        
        # Final status
        final_status = manager.get_status()
        print(f"\\n[FINAL STATUS]")
        print(f"  - Completed tasks: {final_status['completed_tasks']}")
        
    finally:
        manager.stop()
        print("\\n[TEST] Test complete")

if __name__ == "__main__":
    test_priority_system()