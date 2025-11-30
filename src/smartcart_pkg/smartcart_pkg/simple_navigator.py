import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import json
import time
import math

# ==========================================
# ★ここをあなたの計測した座標に書き換えてください★
# 形式: [x(m), y(m), 向き(ラジアン)]
# 向き: 0.0=東, 1.57=北, 3.14=西, -1.57=南
# ==========================================
ITEM_LOCATIONS = {
    "curry roux":    [6.563,  7.9155,  1.57],  
    "beef":         [12.267, 10.7331,  3.14],   
    "pork":         [8.56, 11.03,  3.14],   
    "onion":        [8.413, -1.271, 1.57], 
    "carrot":        [10.81, -1.382, 1.57],
    "garlic":        [12.507,  -1.453,  1.57],
    "milk":        [12.288,  8.156,  1.57],
    "soy sauce":        [8.794,  8.1634,  1.57],
    "egg":        [12.742,  8.3377,  1.57],
    "rice":        [3.876,  9.521,  1.57],
}

# レジ（帰還場所）
CASHIER_LOCATION = [4.303, -1.636, -1.57]

def get_quaternion_from_euler(yaw):
    """向き(Yawラジアン)をクォータニオン(x,y,z,w)に変換する関数"""
    qx = 0.0
    qy = 0.0
    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)
    return qx, qy, qz, qw

class ShoppingNavigator(Node):
    def __init__(self):
        super().__init__('shopping_navigator')
        
        self.subscription = self.create_subscription(
            String,
            'shopping_list',
            self.listener_callback,
            10)
        
        self.navigator = BasicNavigator()
        
        # 初期位置の設定（とりあえず0,0,0とする）
        #self.set_initial_pose()

        self.get_logger().info('🔍 DEBUG: Waiting for Nav2 to activate...')
        self.navigator.waitUntilNav2Active()
        self.get_logger().info('✅ DEBUG: Nav2 is Ready! Waiting for shopping list...')
        self.get_logger().info('👉 Hint: Run "ros2 topic pub /shopping_list std_msgs/msg/String \"data: \'[\\\"vegetable\\\", \\\"meat\\\"]\'\" -1"')

    def set_initial_pose(self):
        """ロボットに「今は原点(0,0)にいるよ」と教え込む"""
        initial_pose = PoseStamped()
        initial_pose.header.frame_id = 'map'
        initial_pose.header.stamp = self.navigator.get_clock().now().to_msg()
        initial_pose.pose.position.x = -15.0
        initial_pose.pose.position.y = 0.0
        qx, qy, qz, qw = get_quaternion_from_euler(0.0) # 向き0
        initial_pose.pose.orientation.z = qz
        initial_pose.pose.orientation.w = qw
        self.navigator.setInitialPose(initial_pose)

    def listener_callback(self, msg):
        self.get_logger().info(f'📩 DEBUG: Message Received: {msg.data}')
        try:
            shopping_list = json.loads(msg.data)
            self.execute_shopping_trip(shopping_list)
        except Exception as e:
            self.get_logger().error(f'❌ DEBUG: JSON Error: {e}')

    def execute_shopping_trip(self, shopping_list):
        for item_name in shopping_list:
            target_coords = self.find_coordinates(item_name)
            
            if target_coords:
                x, y, yaw = target_coords
                self.get_logger().info(f'🚀 DEBUG: Trying to go to "{item_name}" at [x={x}, y={y}]')
                
                # 移動実行
                success = self.go_to_spot(target_coords)
                
                if success:
                    self.get_logger().info(f'🏁 DEBUG: Arrived at {item_name}. (Picking up...)')
                    time.sleep(2.0)
                else:
                    self.get_logger().error(f'💀 DEBUG: Failed to reach {item_name}.')
            else:
                self.get_logger().warn(f'❓ DEBUG: Location unknown for "{item_name}"')

        # 帰還
        self.get_logger().info('🏠 DEBUG: Returning to Cashier...')
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
        
        # 座標のセット
        goal_pose.pose.position.x = float(coords[0])
        goal_pose.pose.position.y = float(coords[1])
        
        # 向きのセット（追加した計算処理）
        yaw = float(coords[2])
        qx, qy, qz, qw = get_quaternion_from_euler(yaw)
        goal_pose.pose.orientation.x = qx
        goal_pose.pose.orientation.y = qy
        goal_pose.pose.orientation.z = qz
        goal_pose.pose.orientation.w = qw
        
        # --- 移動コマンド送信 ---
        self.navigator.goToPose(goal_pose)

        # --- 移動中の監視ループ ---
        i = 0
        while not self.navigator.isTaskComplete():
            i += 1
            feedback = self.navigator.getFeedback()
            if feedback and i % 5 == 0:
                rem = feedback.distance_remaining
                self.get_logger().info(f'   🚶 Moving... Distance remaining: {rem:.2f}m')
            
            time.sleep(0.1)

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            return True
        elif result == TaskResult.CANCELED:
            self.get_logger().warn('⚠️ DEBUG: Task was CANCELED')
            return False
        elif result == TaskResult.FAILED:
            self.get_logger().error('⚠️ DEBUG: Task FAILED')
            return False
        return False

def main():
    rclpy.init()
    node = ShoppingNavigator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()