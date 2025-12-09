import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped

class VelocityConverter(Node):
    def __init__(self):
        super().__init__('velocity_converter')
        # Nav2からの新型(Stamped)を受け取る
        self.subscription = self.create_subscription(
            TwistStamped,
            '/cmd_vel_nav',  # Nav2にはここに出させる
            self.listener_callback,
            10)
        # Gazeboへ旧型(Twist)を流す
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)

    def listener_callback(self, msg):
        # 中身(Twist)だけ取り出してそのまま流す
        out_msg = msg.twist
        self.publisher.publish(out_msg)

def main():
    rclpy.init()
    node = VelocityConverter()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()