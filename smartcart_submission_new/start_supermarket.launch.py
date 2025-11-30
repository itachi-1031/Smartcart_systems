import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # 1. パッケージのディレクトリを動的に取得
    # 'smartcart_pkg' はあなたのパッケージ名に合わせてください
    pkg_share = get_package_share_directory('smartcart_pkg')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    # TurtleBot3のパスも動的に取得（/opt/ros/jazzy... と書くより安全です）
    try:
        tb3_share = get_package_share_directory('turtlebot3_gazebo')
        tb3_model_path = os.path.join(tb3_share, 'models', 'turtlebot3_burger', 'model.sdf')
    except Exception:
        # 見つからない場合のフォールバック（Jazzy標準パス）
        tb3_model_path = '/opt/ros/jazzy/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf'

    # 2. パス設定 (installディレクトリ内のパスになります)
    world_file = os.path.join(pkg_share, 'worlds', 'supermarket.sdf')
    
    # モデルディレクトリのパス
    # setup.pyで 'models' フォルダが正しくインストールされている前提です
    custom_model_path = os.path.join(pkg_share, 'models')

    return LaunchDescription([
        # 3. 環境変数の設定
        # 自作モデルパスと、TurtleBot3のモデルパス(標準)を連結
        SetEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=f"{custom_model_path}:/opt/ros/jazzy/share/turtlebot3_gazebo/models"
        ),

        # 4. Gazeboの起動
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': f'-r {world_file}'}.items(),
        ),

        # 5. TurtleBot3を出現させる
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[
                '-name', 'turtlebot3_burger',
                '-file', tb3_model_path,
                '-x', '-15.0',
                '-y', '0.0',
                '-z', '0.3'
            ],
            output='screen',
        ),
    ])