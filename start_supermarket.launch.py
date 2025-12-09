import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # ★重要: あなたのパッケージ名に合わせてください
    package_name = 'smartcart_sys2' 

    # 1. パス設定 (ここを自動取得に変更)
    # 自分のパッケージのインストール場所を取得
    pkg_share = get_package_share_directory(package_name)
    
    # TurtleBot3のパッケージ場所を取得 (標準パスに依存しない安全な方法)
    pkg_tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    # ファイルパスの結合
    world_file = os.path.join(pkg_share, 'worlds', 'supermarket.sdf')
    my_model_path = os.path.join(pkg_share, 'models')
    
    # TurtleBot3のモデルパス
    tb3_model_path = os.path.join(pkg_tb3_gazebo, 'models', 'turtlebot3_burger', 'model.sdf')
    tb3_models_dir = os.path.join(pkg_tb3_gazebo, 'models')

    return LaunchDescription([
        # 2. 環境変数の設定
        # 自作モデルパスと、TurtleBot3のモデルパスを結合
        SetEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=f"{my_model_path}:{tb3_models_dir}"
        ),

        # 3. Gazeboの起動
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': f'-r {world_file}'}.items(),
        ),

        # 4. TurtleBot3を出現させる
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
