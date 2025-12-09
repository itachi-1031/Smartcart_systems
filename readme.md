SmartCartAI Interface 
Ubuntu 24.04 + ROS 2 Jazzy 環境で動作する、スーパーマーケット向けスマートカートのユーザーインターフェースです。 Google Gemini APIを活用した「献立相談チャット」機能を持ち、決定した買い物リストをJSON形式でROS 2トピックとして配信します。

**機能概要**
AIシェフ機能: Google Gemini と対話し、献立やレシピを相談できます。
買い物リスト生成: 会話から必要な食材を抽出し、JSONデータに変換します。
ROS 2連携: ボタン一つでロボットの自律移動システムへ指令（商品リスト）を送信します。

**動作環境**
OS: Ubuntu 24.04 LTS (Noble Numbat)
ROS Distro: ROS 2 Jazzy jazzy
Python: 3.12
Hardware: PC (Simulation) / i-Cart mini (Real Robot)

**setup手順**

1,必要ツールのインストール
sudo apt update
sudo apt install python3-venv

2,プロジェクトの準備
mkdir smart_cart_project
cd smart_cart_project
#このディレクトリ内にapp.pyを配置

3,仮想環境の作成
python3 -m venv --system-site-packages venv

4,仮想環境のアクティベートとライブラリ導入
source venv/bin/activate
pip install streamlit google-generativeai python-dotenv

5,APIkeyの設定
nano .env
GOOGLE_API_KEY=YOUR_API_KEY_HERE

**実行手順**
# 1. ROS 2 環境の読み込み
source /opt/ros/jazzy/setup.bash

# 2. 仮想環境のアクティベート
source venv/bin/activate

# 3. アプリの起動
streamlit run app.py