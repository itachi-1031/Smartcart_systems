# スマートカート・プロジェクト (Smart Cart System)

スーパーマーケットでの買い物支援ロボットのシミュレーションシステムです。
指定された商品棚へ自律移動し、買い物をシミュレーションします。

## 動作環境
- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo (Harmonic/Sim)

## 実行手順

ターミナル1
```
source /opt/ros/jazzy/setup.bash
ros2 launch ~/smartcart_sys/smartcart_sys/bringup_all.launch.py
```

ターミナル2   

    source .venv/bin/activate   #仮想環境を起動する
    source /opt/ros/jazzy/setup.bash
    streamlit run app.py

ターミナル3
'''

    export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:~/smartcart_sys2/models
    source /opt/ros/jazzy/setup.bash
    python3 ~/smartcart_sys/simple_navigator.py
