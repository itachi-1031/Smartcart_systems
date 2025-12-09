import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node

def generate_launch_description():
    # ==========================================
    # 1. パラメータ設定
    # ==========================================
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    map_dir = '/home/morio/smartcart_sys/maps/supermarket_map.yaml'
    params_dir = '/home/morio/smartcart_sys/nav2_params.yaml'
    
    # TurtleBot3のURDFファイルのパス
    urdf_path = os.path.join(
        get_package_share_directory('turtlebot3_description'),
        'urdf',
        'turtlebot3_burger.urdf')

    # ==========================================
    # 2. 起動設定
    # ==========================================

    # A. 世界とロボット (Gazebo)
    start_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            '/home/morio/smartcart_sys/smartcart_sys/start_supermarket.launch.py'
        ])
    )

    # B. ロボットの体を配信 (Robot State Publisher)
    # ★修正ポイント：xacroコマンドを使って、変な名前(${namespace})を確実に消去する！
    # namespace:="" を渡すことで、空文字に置換します。
    robot_desc = Command(['xacro ', urdf_path, ' namespace:=""'])

    start_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': robot_desc
        }],
    )

    # C. Nav2 起動
    start_nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('nav2_bringup'), 'launch', 'bringup_launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'map': map_dir,
            'params_file': params_dir,
            'cmd_vel_topic': '/cmd_vel'
        }.items(),
    )

    # D. RViz 起動
    start_rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('nav2_bringup'), 'launch', 'rviz_launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
        }.items(),
    )

    # ==========================================
    # 3. 実行リスト
    # ==========================================
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation clock'),
        
        start_gazebo,
        start_robot_state_publisher,
        start_nav2,
        start_rviz
    ])
