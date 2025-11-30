import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import time


# --- ROS 2 関連のインポート ---
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np
import threading

# .envファイルから環境変数を読み込む
load_dotenv()

# ==========================================
# 1. ROS 2 ノード設定 (ここが追加部分！)
# ==========================================
class ShoppingListNode(Node):
    def __init__(self):
        super().__init__('shopping_list_ui_node')
        # JSON文字列を送るPublisher
        self.publisher_ = self.create_publisher(String, 'shopping_list', 10)
        
        # カート情報の購読
        self.create_subscription(String, 'cart_update', self.cart_callback, 10)
        self.latest_cart_data = None
        
        # 画像の購読
        self.create_subscription(CompressedImage, 'cart/image_raw/compressed', self.image_callback, 10)
        self.latest_image = None
        
        self.get_logger().info('Shopping List UI Node Started!')

    def cart_callback(self, msg):
        try:
            self.latest_cart_data = json.loads(msg.data)
        except:
            pass

    def image_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            self.latest_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"Image decode error: {e}")


    def send_list(self, items_json):
        """JSON文字列を受け取ってROSトピックに流す"""
        msg = String()
        msg.data = items_json
        self.publisher_.publish(msg)
        self.get_logger().info(f'Published: {msg.data}')

@st.cache_resource
def setup_ros():
    """
    Streamlitが再実行されてもノードを作り直さないようにキャッシュする関数
    """
    # まだ初期化されていなければ初期化
    if not rclpy.ok():
        rclpy.init()
    
    # ノード作成
    node = ShoppingListNode()
    
    # 別スレッドでspinさせる（これでアプリが止まらない）
    thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread.start()
    
    return node

# アプリ起動時に一度だけ実行される
ros_node = setup_ros()


# ==========================================
# 2. Gemini API 設定
# ==========================================
def configure_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
        else:
            st.error("Google API Keyが設定されていません。")
            return None
    
    genai.configure(api_key=api_key)
    return True

@st.cache_resource
def get_gemini_model():
    return genai.GenerativeModel('gemini-2.5-flash')

def analyze_recipe_with_gemini(prompt_text):
    configure_gemini()
    model = get_gemini_model()
    
    # ★重要★
    # ロボットが処理しやすいように、JSON形式での出力を強制するプロンプトを追加します
    system_instruction = """
    あなたはスーパーマーケットの買い物支援AIです。
    ユーザーの要望に応じたレシピを提案してください。
    
    【重要】
    回答の最後には必ず、そのレシピに必要な「買うものリスト」を以下のJSON形式のブロックで出力してください。
    それ以外の説明文はJSONの外に書いてください。
    
    ```json
    ["item_name_1", "item_name_2", "item_name_3"]
    ```
    """
    
    full_prompt = f"{system_instruction}\n\nユーザーの要望: {prompt_text}"

    try:
        with st.spinner('Geminiが分析中...'):
            response = model.generate_content(full_prompt)
            return response.text
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        return "分析に失敗しました。"

def extract_json_from_text(text):
    """Geminiの回答からJSON部分だけを抜き出すヘルパー関数"""
    try:
        import re
        match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1)
        else:
            return None
    except:
        return None

# ==========================================
# 3. 画面表示関数群
# ==========================================

def show_language_select_screen():
    st.header("Language / 言語")
    lang = st.radio("選択してください", ["日本語", "English"])
    if st.button("次へ / Next"):
        st.session_state['step'] = 'category_select'
        st.session_state['language'] = lang
        st.rerun()

def show_category_select_screen():
    st.header("カテゴリ選択")
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("欲しい物が決まっている方")
        if st.button("野菜コーナーへ", use_container_width=True):
            st.session_state['step'] = 'category_products'
            st.session_state['category'] = 'vegetables'
            st.rerun()
            
    with col2:
        st.success("献立が決まっていない方")
        # ここが新しいチャット機能への入り口です
        if st.button("👨‍🍳 AIシェフに相談する", use_container_width=True):
            st.session_state['step'] = 'chat_consultation'
            st.rerun()
            
    st.divider()
    if st.button("🛒 スマートカートでお買い物モード", type="primary", use_container_width=True):
        st.session_state['step'] = 'shopping_mode'
        st.rerun()

            
    # 既存の自由入力も残したい場合は下に配置
    st.divider()
    if st.button("単純な質問・自由入力はこちら"):
        st.session_state['step'] = 'free_input'
        st.rerun()

def show_category_products_screen():
    st.header("商品一覧")
    st.write("ここは手動選択画面です（今回はAI機能メインで実装）")
    if st.button("戻る"):
        st.session_state['step'] = 'category_select'
        st.rerun()

def show_ingredients_screen():
    st.header("材料詳細")
    if st.button("レシピを見る"):
        st.session_state['step'] = 'recipe_select'
        st.rerun()

def show_recipe_select_screen():
    st.header("レシピ選択")
    if st.button("Geminiでレシピを生成"):
        result = analyze_recipe_with_gemini("冷蔵庫にある余り物（卵、牛乳、キャベツ）で簡単なレシピを提案して")
        st.session_state['analysis_result'] = result
        st.session_state['step'] = 'analysis_result'
        st.rerun()

def show_suggestions_screen():
    st.header("提案一覧")
    pass

def show_ai_recommendation_screen():
    st.header("AI レコメンデーション")
    user_input = st.text_input("好みの味や気分を入力")
    if user_input and st.button("提案してもらう"):
        result = analyze_recipe_with_gemini(f"{user_input}という気分の時の夕飯を提案して")
        st.session_state['analysis_result'] = result
        st.session_state['step'] = 'analysis_result'
        st.rerun()

def show_analysis_result_screen():
    st.header("分析結果 & 買い物リスト")
    
    if 'analysis_result' in st.session_state:
        result_text = st.session_state['analysis_result']
        st.markdown(result_text) # Markdownとして綺麗に表示
        
        # JSON部分を抽出
        json_str = extract_json_from_text(result_text)
        
        st.divider()
        st.subheader("ロボットへの指令")
        
        if json_str:
            # 抽出できた場合
            shopping_list = json.loads(json_str)
            st.success(f"検出された買い物リスト: {shopping_list}")
            
            # ★ここでROS2送信★
            if st.button("🛒 このリストで買い物に行く！", type="primary"):
                ros_node.send_list(json_str) # ノード経由で送信
                st.toast("ロボットに指令を送りました！")
                st.balloons()
        else:
            st.warning("買い物リストがうまく生成されませんでした。もう一度試してください。")

    if st.button("トップに戻る"):
        st.session_state['step'] = 'language_select'
        st.rerun()

def show_free_input_screen():
    st.header("自由入力相談")
    text = st.text_area("食材や悩み・質問を入力してください")
    if st.button("送信"):
        result = analyze_recipe_with_gemini(text)
        st.session_state['analysis_result'] = result
        st.session_state['step'] = 'analysis_result'
        st.rerun()

def show_chat_consultation_screen():
    st.header("👨‍🍳 AIシェフと献立相談")
    
    # 1. チャット履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = [
            # 最初の挨拶は履歴に入れておくが、APIには送らなくても良い（あるいは文脈として送る）
            {"role": "assistant", "content": "こんにちは！今日の気分や、冷蔵庫にある食材を教えてください。一緒に献立を考えましょう！"}
        ]

    # 2. 過去のチャット履歴を画面に表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 3. ユーザーの入力処理
    if prompt := st.chat_input("例: チキンカレーが食べたい、コールスローも..."):
        # ユーザーの入力を表示・履歴に追加
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Geminiの応答を生成
        with st.chat_message("assistant"):
            with st.spinner("シェフが思考中..."):
                configure_gemini()
                
                # システムプロンプト（AIの役割定義）
                system_instruction = """
                あなたはプロの家庭料理シェフ兼買い物アドバイザーです。
                ユーザーの曖昧な要望から、具体的な献立を決定する手助けをしてください。
                これまでの会話の流れを汲んで、ユーザーがすでに答えたことを聞き返さないようにしてください。
                会話はすべて「日本語」で行ってください。
                
                【超重要：買い物リスト生成ルール】
                会話の結果、ユーザーと合意してメニューが決定した場合のみ、
                回答の最後に必ず「買い物リスト」を以下のJSON形式で出力してください。
                
                ★重要★
                買い物リストの**商品名（中身）は必ず「英語」に翻訳して**出力してください。
                （ロボットが英語しか理解できないためです）
                
                出力例:
                ```json
                ["Chicken", "Onion", "Carrot", "Curry Roux"]
                ```
                """

                # モデルの準備（システムプロンプトを設定）
                model = genai.GenerativeModel(
                    'gemini-2.5-flash',
                    system_instruction=system_instruction
                )
                
                # --- ★ここが修正ポイント：履歴の変換 ---
                # Streamlitの履歴(role: assistant)をGeminiの履歴(role: model)に変換
                gemini_history = []
                for msg in st.session_state.messages[:-1]: # 今回のprompt以外を履歴とする
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg["content"]]})
                
                # チャットセッションを開始（過去の文脈を持たせる）
                chat = model.start_chat(history=gemini_history)
                
                # 今回の入力を送信
                response = chat.send_message(prompt)
                response_text = response.text

                st.markdown(response_text)
                
                # 履歴に追加
                st.session_state.messages.append({"role": "assistant", "content": response_text})

    # 4. ROS送信ボタンの判定（入力ループの外に出す！）
    # 最新のメッセージが「assistant」であり、かつ「JSONが含まれている」場合のみボタンを出す
    if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        if last_msg["role"] == "assistant":
            json_str = extract_json_from_text(last_msg["content"])
            
            if json_str:
                st.divider()
                st.info("💡 献立が決まりました！買い物リストをロボットに送りますか？")
                
                # デバッグ用に中身を表示（不要なら消してもOK）
                # st.code(json_str, language='json')

                if st.button("🛒 ロボットに指令を送る", key="send_ros_btn", type="primary"):
                    # ここでログが出るはず
                    print(f"Button Clicked! Sending: {json_str}") 
                    ros_node.send_list(json_str)
                    st.toast("ロボットに買い物リストを送信しました！🚀")
                    st.balloons()

def show_navigation_screen():
    with st.sidebar:
        st.title("メニュー")
        if st.button("最初から"):
            st.session_state['step'] = 'language_select'
            st.rerun()
        st.write("ROS2 Status: ✅ Active")

def show_shopping_mode_screen():
    st.header("🛒 スマートカート (Shopping Mode)")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Live Camera")
        image_placeholder = st.empty()
        
        if ros_node.latest_image is not None:
            # OpenCV is BGR, Streamlit needs RGB
            img_rgb = cv2.cvtColor(ros_node.latest_image, cv2.COLOR_BGR2RGB)
            image_placeholder.image(img_rgb, channels="RGB", use_container_width=True)
        else:
            image_placeholder.info("カメラ映像待機中... (cart_scanner.pyを起動してください)")
            
    with col2:
        st.subheader("カートの中身")
        cart_placeholder = st.empty()
        
        if ros_node.latest_cart_data:
            data = ros_node.latest_cart_data
            st.metric("合計金額", f"¥{data.get('total_price', 0)}")
            st.metric("商品点数", f"{data.get('item_count', 0)}点")
            
            st.write("---")
            for item in data.get('items', []):
                st.text(f"・{item['name']} (¥{item['price']})")
        else:
            cart_placeholder.info("カートは空です")

    # 自動更新のためにrerun (実験的)
    time.sleep(0.1)
    st.rerun()

def show_completion_screen():
    st.header("完了")
    st.write("ご利用ありがとうございました。")

# ==========================================
# 4. メイン処理
# ==========================================

def main():
    st.title("Supermarket Guide App 🤖")
    
    if 'step' not in st.session_state:
        st.session_state['step'] = 'language_select'

    show_navigation_screen()

    step = st.session_state['step']
    
    if step == 'language_select':
        show_language_select_screen()
    elif step == 'category_select':
        show_category_select_screen()
    elif step == 'chat_consultation':
        show_chat_consultation_screen()
    elif step == 'category_products':
        show_category_products_screen()
    elif step == 'ingredients':
        show_ingredients_screen()
    elif step == 'suggestions':
        show_suggestions_screen()
    elif step == 'ai_recommendation':
        show_ai_recommendation_screen()
    elif step == 'analysis_result':
        show_analysis_result_screen()
    elif step == 'free_input':
        show_free_input_screen()
    elif step == 'recipe_select':
        show_recipe_select_screen()
    elif step == 'shopping_mode':
        show_shopping_mode_screen()
    elif step == 'completion':
        show_completion_screen()

if __name__ == "__main__":
    main()