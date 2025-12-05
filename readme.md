# Smart Cart Project (Shopping Support Robot)

## 概要
スーパーマーケットでの買い物支援を行うスマートカートロボットの制御システムです。
ROS 2 Jazzy と TurtleBot3 シミュレーション環境を使用し、タブレットアプリ（Python）と連携して自律移動・商品スキャンを行います。

## 動作環境
* **OS:** Ubuntu 24.04 LTS
* **ROS Version:** ROS 2 Jazzy Jalisco
* **Simulator:** Gazebo (Harmonic) + TurtleBot3
* **Language:** Python 3.12

## ディレクトリ構成
```text
smartcart_submission_new/
├── src/
│   └── smartcart_pkg/  (ROS 2 Package)
├── requirements.txt
└── README.md
```

## セットアップ方法
1. 依存関係のインストール

仮想環境の作成（推奨）

python3 -m venv .venv
source .venv/bin/activate

## 必要なライブラリのインストール
```
pip install -r requirements.txt
```
2. ビルド
```
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 実行手順（マルチターミナル構成）
### 本システムは複数のノードが連携して動作します。 以下の順序で、それぞれ新しいターミナルを開いて実行してください。

すべてのターミナルで
```
source install/setup.bash
source /opt/ros/jazzy/setup.bash
```

仮想環境を使う場合は 
```
source .venv/bin/activate
```
を実行してからコマンドを打ってください。


### 【Terminal 1】シミュレーション環境 (Gazebo)
スーパーマーケットのワールドを展開し、ロボットを出現させます。

```
export TURTLEBOT3_MODEL=burger
ros2 launch smartcart_pkg start_supermarket.launch.py
```

### 【Terminal 2】ナビゲーション制御 (Navigator)
ロボットの移動ロジックを司るメインノードです。
```
ros2 run smartcart_pkg shopping_navigator
# または簡易版: ros2 run smartcart_pkg simple_navigator
```

### 【Terminal 3】タブレット・ユーザーインターフェース (App)
ユーザーが操作する画面（買い物リスト表示）を起動します。
```
# GUIアプリの起動
streamlit run src/smartcart_pkg/smartcart_pkg/app.py
```

### 【Terminal 4】商品スキャナー (Scanner)
バーコード読み取り（カートへの商品投入）をシミュレーションします。
```
ros2 run smartcart_pkg cart_scanner
```

### 【Terminal 5】速度変換・制御 (Converter)
※必要な場合のみ実行（アプリからの指令をロボットの速度指令に変換など）
```
python3 src/smartcart_pkg/smartcart_pkg/vel_converter.py
```

### 【Terminal 6】デバッグ用：トピック監視 (Topic Echo)
ロボットの状態やセンサー値を確認します。
```
ros2 topic echo /scan
# または: ros2 topic echo /cmd_vel
```

### 【Terminal 7】デバッグ用：通信グラフ確認 (RQT Graph)
ノード間の接続関係を可視化します。
```
rqt_graph
```
### 【Terminal 8】その他ツール (RViz2 など)
地図やセンサー情報を可視化します（Launchに含まれていない場合）。

```
ROS2 run rviz2 rviz2
```


