import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # 1. パス設定
    pkg_share = get_package_share_directory('smartcart_pkg')
    world_file = os.path.join(pkg_share, 'worlds', 'supermarket.sdf')
    model_path = os.path.join(pkg_share, 'models')
    
    # TurtleBot3のモデルファイルの場所 (ROS 2 Jazzyの標準パス)
    # ※もしエラーになる場合は、ここを実際のパスに合わせて調整します
    tb3_model_path = '/opt/ros/jazzy/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf'

    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    return LaunchDescription([
        # 2. 環境変数の設定
        # 自作モデルと、TurtleBot3のモデル(標準)の両方をパスに含める
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

        # 4. TurtleBot3を出現させる (ここを修正しました！)
        # 'create' ノードを使って、新しいGazeboにロボットを登場させます
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[
                '-name', 'turtlebot3_burger',
                '-file', tb3_model_path,
                '-x', '-15.0',
                '-y', '0.0',
                '-z', '0.3' # 少し浮かせて埋まり防止
            ],
            output='screen',
        ),
    ])