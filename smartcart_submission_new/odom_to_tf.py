import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped

class OdomToTf(Node):
    def __init__(self):
        super().__init__('odom_to_tf_broadcaster')
        self.br = TransformBroadcaster(self)

        # ★ここが修正ポイント！
        # Gazebo (Best Effort) に合わせて、QoSを設定します
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # 設定したQoSを使って購読
        self.subscription = self.create_subscription(
            Odometry, 
            '/odom', 
            self.handle_odom, 
            qos_profile
        )
        self.get_logger().info("OdomToTf Node Started! Waiting for /odom...")

    def handle_odom(self, msg):
        # データが来たらログを出す（確認用）
        # self.get_logger().info("Received Odom data!", throttle_duration_sec=5)
        
        t = TransformStamped()

        # ヘッダー情報のコピー
        t.header.stamp = msg.header.stamp
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint' # TurtleBot3の足元

        # 位置情報のコピー
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z

        # 回転情報のコピー
        t.transform.rotation = msg.pose.pose.orientation

        # TFを配信！
        self.br.sendTransform(t)

def main():
    rclpy.init()
    node = OdomToTf()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()