import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node

def generate_launch_description():
    # ★重要: パッケージ名を定義
    package_name = 'smartcart_sys2'
    
    # ★重要: インストールされたパッケージのパスを取
    pkg_share = get_package_share_directory(package_name)

    # ==========================================
    # 1. パラメータ設定 (相対パス化)
    # ==========================================
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # マップファイルのパス
    # maps/supermarket_map.yaml を参照
    map_dir = os.path.join(pkg_share, 'maps', 'supermarket_map.yaml')
    
    # パラメータファイルのパス
    # config/nav2_params.yaml を参照 (※ファイルをconfigフォルダに入れてください！)
    params_dir = os.path.join(pkg_share, 'config', 'nav2_params.yaml')
    
    # TurtleBot3のURDFファイルのパス (これはそのままでOK)
    urdf_path = os.path.join(
        get_package_share_directory('turtlebot3_description'),
        'urdf',
        'turtlebot3_burger.urdf')

    # ==========================================
    # 2. 起動設定
    # ==========================================

    # A. 世界とロボット (Gazebo)
    # 修正: 自作の別launchファイルを呼び出すときも pkg_share を使う
    start_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(pkg_share, 'launch', 'start_supermarket.launch.py')
        ])
    )

    # B. ロボットの体を配信 (Robot State Publisher)
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
