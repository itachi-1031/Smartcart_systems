import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import time # 追加

# --- 画像処理・バーコード関連の追加 ---
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image

# --- ROS 2 関連のインポート ---
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
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
        self.get_logger().info('Shopping List UI Node Started!')

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
# 2.5 商品データベース & カート設定
# ==========================================

# バーコード(JANコード)と商品の対応表（モック）
# ※テスト用に手元の商品のバーコード値に書き換えて試してください
PRODUCT_DB = {
    "4902102000186": {"name": "コカ・コーラ 500ml", "price": 160},
    "4901330573429": {"name": "じゃがりこ サラダ", "price": 150},
    "4902720130541": {"name": "森永牛乳 1000ml", "price": 240},
    "4901301348022": {"name": "ニベア ボディウォッシュ", "price": 450},
    # テスト用ダミーコード
    "1234567890123": {"name": "特選和牛ステーキ", "price": 2000},
}

def init_cart_session():
    """カートの中身を初期化"""
    if 'cart' not in st.session_state:
        st.session_state['cart'] = []
    if 'total_price' not in st.session_state:
        st.session_state['total_price'] = 0

# アプリ起動時にカート初期化
init_cart_session()

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
        
        # --- 追加 ---
        st.warning("お会計の方")
        if st.button("📸 セルフレジへ", use_container_width=True):
            st.session_state['step'] = 'checkout'
            st.rerun()
        # -----------
            
    with col2:
        st.success("献立が決まっていない方")
        if st.button("👨‍🍳 AIシェフに相談する", use_container_width=True):
            st.session_state['step'] = 'chat_consultation'
            st.rerun()
            
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
# ... (show_chat_consultation_screen などの並びに追加) ...

def show_checkout_screen():
    st.header("🛒 スマート・セルフレジ")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("商品スキャン")
        st.info("カメラへのアクセスを許可し、バーコードを写してください")
        
        # カメラ入力ウィジェット
        img_file_buffer = st.camera_input("バーコードをスキャン")
        
        # 手動入力（カメラが読み取れない時用）
        manual_code = st.text_input("またはバーコードを手入力")
        if st.button("手入力で追加"):
            if manual_code:
                process_barcode(manual_code)
            
        if img_file_buffer is not None:
            # 画像データをOpenCV形式に変換
            bytes_data = img_file_buffer.getvalue()
            cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
            
            # バーコード検出
            decoded_objects = decode(cv2_img)
            
            if decoded_objects:
                for obj in decoded_objects:
                    barcode_data = obj.data.decode("utf-8")
                    rect = obj.rect
                    
                    # 画像上に枠を描画（オプション）
                    cv2.rectangle(cv2_img, (rect.left, rect.top), 
                                  (rect.left + rect.width, rect.top + rect.height), (0, 255, 0), 3)
                    
                    st.success(f"読み取り成功: {barcode_data}")
                    
                    # カートに追加処理
                    process_barcode(barcode_data)
                    
                    # 連続読み取りを防ぐために少しウェイトを入れるか、UI側で制御が必要
                    # Streamlitの仕様上、再実行されるため、二重追加防止ロジックを入れるとベター
                    break 
            else:
                st.warning("バーコードが検出されませんでした。もう一度試してください。")

    with col2:
        st.subheader("🧾 お会計")
        
        # カート表示
        if st.session_state['cart']:
            for i, item in enumerate(st.session_state['cart']):
                st.write(f"・{item['name']}: ¥{item['price']}")
            
            st.divider()
            total = sum(item['price'] for item in st.session_state['cart'])
            st.markdown(f"### 合計: ¥{total}")
            
            if st.button("お会計を確定する", type="primary"):
                # ROSロボットへ「会計終了・荷物持ち運びモード」などの指令を送る例
                payment_msg = json.dumps({"action": "payment_completed", "total": total})
                ros_node.send_list(payment_msg)
                
                st.session_state['step'] = 'payment_complete'
                st.rerun()
                
            if st.button("カートを空にする"):
                st.session_state['cart'] = []
                st.rerun()
        else:
            st.write("カートは空です")

def process_barcode(code):
    """バーコードを受け取ってカートに追加する処理"""
    # 直前の追加と同じコードなら連続追加を防ぐ（簡易的な防止策）
    if 'last_scanned_code' not in st.session_state:
        st.session_state['last_scanned_code'] = None
        
    # 今回は簡易化のため、同じ商品の連続スキャンも許可するが、
    # 実際は「追加しました」トーストを出してユーザーにフィードバックする
    
    if code in PRODUCT_DB:
        product = PRODUCT_DB[code]
        st.session_state['cart'].append(product)
        st.toast(f"追加: {product['name']}")
        time.sleep(1) # トーストを見せるためのウェイト
        st.rerun() # 画面更新
    else:
        st.error(f"商品マスタ未登録のコードです: {code}")

def show_payment_complete_screen():
    st.header("お支払い完了 🎉")
    st.success("ありがとうございました！")
    st.write("ロボットが荷運び位置へ移動します...")
    
    if st.button("トップに戻る"):
        st.session_state['cart'] = [] # カートクリア
        st.session_state['step'] = 'language_select'
        st.rerun()

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
    elif step == 'completion':
        show_completion_screen()
    elif step == 'checkout':
        show_checkout_screen()
    elif step == 'payment_complete':
        show_payment_complete_screen()

if __name__ == "__main__":
    main()