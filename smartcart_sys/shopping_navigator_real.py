import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import json
import time

# --- REAL ROBOT CONFIGURATION (i-Cart Mini) ---
# 1. Do NOT set initial pose in code. Use RViz "2D Pose Estimate" 
#    or ensure AMCL is localized before running this node.
# 2. Coordinates must be measured from your actual map (.pgm/.yaml).
#    Run: ros2 topic echo /amcl_pose 
#    Drive robot to the shelf, record the X, Y coordinates.

ITEM_LOCATIONS = {
    # TODO: REPLACE THESE WITH REAL COORDINATES FROM YOUR MAP
    "carrot":     [2.5, 0.5],   
    "onion":      [1.2, -1.5],   
    "potato":     [-0.5, 2.0],  
    "curry roux": [3.0, 1.0],  
    "beef":       [0.0, 0.0], # Placeholder
}

# The location of the cashier/home dock
CASHIER_LOCATION = [0.0, 0.0] 

class ShoppingNavigator(Node):
    def __init__(self):
        super().__init__('shopping_navigator')
        
        self.subscription = self.create_subscription(
            String,
            'shopping_list',
            self.listener_callback,
            10)
        
        self.navigator = BasicNavigator()
        
        # CRITICAL CHANGE FOR REAL ROBOT:
        # We removed self.set_initial_pose().
        # On a real robot, resetting the pose to (0,0) randomly 
        # destroys the localization provided by AMCL.
        
        self.get_logger().info('Waiting for Nav2...')
        self.navigator.waitUntilNav2Active()
        self.get_logger().info('Nav2 Ready. Waiting for /shopping_list topic...')

    def listener_callback(self, msg):
        self.get_logger().info(f'Received Order: {msg.data}')
        try:
            shopping_list = json.loads(msg.data)
            self.execute_shopping_trip(shopping_list)
        except Exception as e:
            self.get_logger().error(f'JSON Error: {e}')

    def execute_shopping_trip(self, shopping_list):
        for item_name in shopping_list:
            target_coords = self.find_coordinates(item_name)
            
            if target_coords:
                x, y = target_coords
                self.get_logger().info(f'Navigating to {item_name} ({x}, {y})')
                
                success = self.go_to_spot(target_coords)
                
                if success:
                    self.get_logger().info(f'Arrived at {item_name}. Loading item...')
                    time.sleep(3.0) # Simulate loading time
                else:
                    self.get_logger().error(f'Failed to reach {item_name}')
            else:
                self.get_logger().warn(f'Item "{item_name}" not found in database.')

        self.get_logger().info('Returning to Cashier...')
        self.go_to_spot(CASHIER_LOCATION)

    def find_coordinates(self, item_name):
        search_key = item_name.lower()
        for key, coords in ITEM_LOCATIONS.items():
            if key in search_key or search_key in key:
                return coords
        return None

    def go_to_spot(self, coords):
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'map'
        goal_pose.header.stamp = self.navigator.get_clock().now().to_msg()
        goal_pose.pose.position.x = float(coords[0])
        goal_pose.pose.position.y = float(coords[1])
        goal_pose.pose.orientation.w = 1.0
        
        self.navigator.goToPose(goal_pose)

        i = 0
        while not self.navigator.isTaskComplete():
            i += 1
            feedback = self.navigator.getFeedback()
            if feedback and i % 10 == 0:
                self.get_logger().info(f'Distance remaining: {feedback.distance_remaining:.2f}m')
            
            # Allow time for callbacks to process
            time.sleep(0.1)

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            return True
        elif result == TaskResult.CANCELED:
            self.get_logger().warn('Task CANCELED')
            return False
        elif result == TaskResult.FAILED:
            self.get_logger().error('Task FAILED')
            return False
        return False

def main():
    rclpy.init()
    node = ShoppingNavigator()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()