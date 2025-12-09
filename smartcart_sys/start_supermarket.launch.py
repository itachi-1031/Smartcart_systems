import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # 1. パス設定
    base_path = '/home/morio/smartcart_sys'
    world_file = os.path.join(base_path, 'worlds', 'supermarket.sdf')
    model_path = os.path.join(base_path, 'models')
    tb3_model_path = '/opt/ros/jazzy/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf'
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    return LaunchDescription([
        # 2. 環境変数の設定
        SetEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=f"{model_path}:/opt/ros/jazzy/share/turtlebot3_gazebo/models"
        ),

        # 3. Gazeboの起動
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': f'-r {world_file}'}.items(),
        ),

        # 4. ロボットを出現させる
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[
                '-name', 'turtlebot3_burger',
                '-file', tb3_model_path,
                '-x', '-14.0',
                '-y', '0.0',
                '-z', '0.2'
            ],
            output='screen',
        ),

        # 5. 通信ブリッジ (TwistStamped対応 & 全トピック入り)
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            arguments=[
                '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
                # Nav2に合わせて TwistStamped で受信する設定
                '/cmd_vel@geometry_msgs/msg/TwistStamped@gz.msgs.Twist', 
                '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
                '/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',
                '/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
                '/imu@sensor_msgs/msg/Imu[gz.msgs.IMU',
                '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
            ],
            remappings=[
                ('/model/turtlebot3_burger/cmd_vel', '/cmd_vel'),
                ('/model/turtlebot3_burger/odometry', '/odom'),
                ('/model/turtlebot3_burger/scan', '/scan'),
                ('/model/turtlebot3_burger/tf', '/tf'),
                ('/model/turtlebot3_burger/imu', '/imu'),
                ('/model/turtlebot3_burger/joint_state', '/joint_states'),
            ],
            output='screen'
        ),
    ])