import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import json
import time

ITEM_LOCATIONS = {
    "carrot":     [1.0, 0.0],   # X=1m 前方
    "onion":      [0.0, 1.0],   # Y=1m 左
    "potato":     [-1.0, 0.0],  # X=-1m 後方
    "curry roux": [0.0, -1.0],  # Y=-1m 右
    "beef":       [0.5, 0.5],   # 斜め前
    "meat":       [0.5, 0.5],
}

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
        
        self.set_initial_pose()

        self.get_logger().info('🔍 DEBUG: Waiting for Nav2 to activate...')
        self.navigator.waitUntilNav2Active()
        self.get_logger().info('✅ DEBUG: Nav2 is Ready! Waiting for shopping list...')

    def set_initial_pose(self):
        """ロボットに「今は原点(0,0)にいるよ」と教え込む"""
        initial_pose = PoseStamped()
        initial_pose.header.frame_id = 'map'
        initial_pose.header.stamp = self.navigator.get_clock().now().to_msg()
        initial_pose.pose.position.x = 0.0
        initial_pose.pose.position.y = 0.0
        initial_pose.pose.orientation.z = 0.0
        initial_pose.pose.orientation.w = 1.0
        self.navigator.setInitialPose(initial_pose)
        self.get_logger().info('📍 DEBUG: Initial Pose Set to (0, 0)')

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
                x, y = target_coords
                self.get_logger().info(f'🚀 DEBUG: Trying to go to "{item_name}" at [x={x}, y={y}]')
                
                # 移動実行
                success = self.go_to_spot(target_coords)
                
                if success:
                    self.get_logger().info(f'🏁 DEBUG: Arrived at {item_name}. (Picking up...)')
                    time.sleep(2.0)
                else:
                    self.get_logger().error(f'💀 DEBUG: Failed to reach {item_name}. (Path blocked?)')
            else:
                self.get_logger().warn(f'❓ DEBUG: Location unknown for "{item_name}"')

        # 帰還
        self.get_logger().info('🏠 DEBUG: Returning to Cashier...')
        self.go_to_spot(CASHIER_LOCATION)

    def find_coordinates(self, item_name):
        search_key = item_name.lower()
        # 部分一致検索
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
        
        # --- 移動コマンド送信 ---
        self.navigator.goToPose(goal_pose)

        # --- 移動中の監視ループ ---
        i = 0
        while not self.navigator.isTaskComplete():
            i += 1
            feedback = self.navigator.getFeedback()
            if feedback and i % 5 == 0: # ログが多すぎないように5回に1回表示
                # 残り距離を表示
                rem = feedback.distance_remaining
                self.get_logger().info(f'   🚶 Moving... Distance remaining: {rem:.2f}m')
            
            # タイムアウト回避のために少し待つ
            # time.sleep(0.1) を入れるとメッセージ処理がブロックされることがあるので注意が必要だが
            # simple_commander内では処理されている。念の為少しsleepさせても良い。
            time.sleep(0.1)

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            return True
        elif result == TaskResult.CANCELED:
            self.get_logger().warn('⚠️ DEBUG: Task was CANCELED')
            return False
        elif result == TaskResult.FAILED:
            self.get_logger().error('⚠️ DEBUG: Task FAILED (Unreachable target?)')
            return False
        return False

def main():
    rclpy.init()
    node = ShoppingNavigator()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()