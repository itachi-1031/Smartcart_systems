import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import time 

# --- 画像処理・バーコード関連 ---
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image

# --- ROS 2 関連 ---
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import threading

# .envファイル読み込み
load_dotenv()

# ==========================================
# 1. ROS 2 ノード設定
# ==========================================
class ShoppingListNode(Node):
    def __init__(self):
        super().__init__('shopping_list_ui_node')
        self.publisher_ = self.create_publisher(String, 'shopping_list', 10)
        self.get_logger().info('Shopping List UI Node Started!')

    def send_list(self, items_json):
        msg = String()
        msg.data = items_json
        self.publisher_.publish(msg)
        self.get_logger().info(f'Published: {msg.data}')

@st.cache_resource
def setup_ros():
    if not rclpy.ok():
        rclpy.init()
    node = ShoppingListNode()
    thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread.start()
    return node

ros_node = setup_ros()


# ==========================================
# 2. Gemini API 設定
# ==========================================
def configure_gemini():
    load_dotenv() 
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.error("❌ エラー: APIキーが読み込めていません。")
        return None
    genai.configure(api_key=api_key)
    return True
    
@st.cache_resource
def get_gemini_model():
    return genai.GenerativeModel('gemini-2.5-flash')

def analyze_recipe_with_gemini(prompt_text):
    configure_gemini()
    model = get_gemini_model()
    
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
    """Geminiの回答からJSON部分だけを抜き出す（強化版）"""
    import re
    try:
        # パターン1: ```json [ ... ] ``` の形
        match = re.search(r'```json\s*(\[.*?\])\s*```', text, re.DOTALL)
        if match: return match.group(1)

        # パターン2: ``` [ ... ] ``` (json指定なしのコードブロック)
        match = re.search(r'```\s*(\[.*?\])\s*```', text, re.DOTALL)
        if match: return match.group(1)

        # パターン3: 生の [ ... ] が書いてある場合（スクリーンショットはこれの可能性が高い）
        # 「[」で始まり、「"」を含み、「]」で終わる塊を探す
        match = re.search(r'(\[\s*".*?"\s*.*\])', text, re.DOTALL)
        if match: return match.group(1)
        
        return None
    except:
        return None

# ==========================================
# 2.5 商品データベース & カート設定
# ==========================================

def init_cart_session():
    if 'cart' not in st.session_state:
        st.session_state['cart'] = []
    if 'total_price' not in st.session_state:
        st.session_state['total_price'] = 0
    if 'robot_list' not in st.session_state:
        st.session_state['robot_list'] = []
    
CATEGORY_ITEMS = {
    "野菜・果物": ["キャベツ", "レタス", "トマト", "玉ねぎ", "人参", "バナナ", "リンゴ"],
    "精肉・鮮魚": ["鶏もも肉", "豚バラ肉", "牛ミンチ", "サケの切り身", "マグロ刺身"],
    "乳製品・卵": ["牛乳", "ヨーグルト", "チーズ", "卵(10個入)", "バター"],
    "調味料・粉": ["醤油", "マヨネーズ", "カレールー", "小麦粉", "パン粉"],
    "お菓子・飲料": ["ポテトチップス", "チョコレート", "コーラ", "お茶", "水(2L)"]
}

# 画像に合わせて更新したデータベース
PRODUCT_DB = {
    "4902777003665": {"name": "あらびきウインナー", "price": 398},
    "4902380198406": {"name": "日清 サラダ油", "price": 450},
    "4900000001006": {"name": "野菜（じゃがいも/なす）", "price": 158},
    "4902402854501": {"name": "ジャワカレー 中辛", "price": 350},
    "4973360566850": {"name": "サトウのごはん", "price": 140},
    "4902402848357": {"name": "こくまろカレー 中辛", "price": 220},
    "4901002113520": {"name": "S&B 味付塩こしょう", "price": 190},
    "4908011502444": {"name": "お米 5kg", "price": 2400},
    "4902402853818": {"name": "バーモントカレー 中辛", "price": 298},
    # 既存テストデータ
    "4902102000186": {"name": "コカ・コーラ 500ml", "price": 160},
    "4517586001667": {"name": "広島レモンケーキ", "price": 250},
}

# ==========================================
# 3. 画面表示関数群
# ==========================================

def show_category_select_screen():
    st.header("売り場から探す")
    st.write("どの売り場の商品をお探しですか？")

    categories = list(CATEGORY_ITEMS.keys())
    cols = st.columns(2)
    for i, category in enumerate(categories):
        with cols[i % 2]:
            if st.button(f"📍 {category}", use_container_width=True):
                st.session_state['selected_category'] = category
                st.session_state['step'] = 'category_products'
                st.rerun()

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.warning("お会計の方")
        if st.button("📸 セルフレジへ", use_container_width=True):
            st.session_state['step'] = 'checkout'
            st.rerun()
            
    with col2:
        st.success("献立が決まっていない方")
        if st.button("👨‍🍳 AIシェフに相談する", use_container_width=True):
            st.session_state['step'] = 'chat_consultation'
            st.rerun()
            
    st.divider()
    if st.session_state['robot_list']:
        st.info(f"現在選択中の商品: {st.session_state['robot_list']}")
        if st.button("このリストでロボットに依頼する (確定)", type="primary"):
            json_str = json.dumps(st.session_state['robot_list'], ensure_ascii=False)
            ros_node.send_list(json_str)
            st.toast("ロボットに出発指令を送りました！")
            st.session_state['step'] = 'checkout' # ここでもレジへ移動させる
            st.rerun()
            
    st.divider()
    if st.button("単純な質問・自由入力はこちら"):
        st.session_state['step'] = 'free_input'
        st.rerun()

def show_category_products_screen():
    category = st.session_state.get('selected_category', '未選択')
    st.header(f"{category} コーナー")
    
    if st.button("🔙 売り場選択に戻る"):
        st.session_state['step'] = 'category_select'
        st.rerun()
        
    st.divider()
    items = CATEGORY_ITEMS.get(category, [])
    current_selection = [item for item in st.session_state['robot_list'] if item in items]
    
    selected_items = st.multiselect(
        "欲しい商品にチェックを入れてください",
        options=items,
        default=current_selection
    )
    
    if st.button("リストを更新して戻る", type="primary"):
        other_items = [item for item in st.session_state['robot_list'] if item not in items]
        st.session_state['robot_list'] = other_items + selected_items
        st.toast("買い物リストを更新しました")
        time.sleep(0.5)
        st.session_state['step'] = 'category_select'
        st.rerun()

def show_analysis_result_screen():
    st.header("分析結果 & 買い物リスト")
    
    if 'analysis_result' in st.session_state:
        result_text = st.session_state['analysis_result']
        st.markdown(result_text)
        
        json_str = extract_json_from_text(result_text)
        
        st.divider()
        st.subheader("ロボットへの指令")
        
        # --- 修正箇所：条件分岐を変更 ---
        if json_str:
            # 成功した場合
            try:
                shopping_list = json.loads(json_str)
                st.success(f"検出された買い物リスト: {shopping_list}")
                
                if st.button("🛒 このリストで買い物に行く！ (レジ画面へ)", type="primary"):
                    ros_node.send_list(json_str)
                    st.toast("ロボットに指令を送りました！")
                    st.session_state['step'] = 'checkout'
                    time.sleep(1)
                    st.rerun()
            except:
                st.error("リストの形式が正しくありませんでしたが、買い物画面へ進めます。")
                if st.button("🛒 買い物画面へ進む", type="primary"):
                    st.session_state['step'] = 'checkout'
                    st.rerun()
        else:
            # 失敗した場合（ここが重要！ボタンが出ない原因の対策）
            st.warning("⚠️ 買い物リストを自動検出できませんでしたが、買い物には行けます。")
            if st.button("🛒 とりあえず買い物画面へ進む", type="primary"):
                st.session_state['step'] = 'checkout'
                st.rerun()

    if st.button("トップに戻る"):
        st.session_state['step'] = 'category_select'
        st.rerun()

def show_free_input_screen():
    st.header("自由入力相談")
    text = st.text_area("食材や悩み・質問を入力してください")
    if st.button("送信"):
        result = analyze_recipe_with_gemini(text)
        st.session_state['analysis_result'] = result
        st.session_state['step'] = 'analysis_result'
        st.rerun()
    if st.button("戻る"):
        st.session_state['step'] = 'category_select'
        st.rerun()

def show_chat_consultation_screen():
    st.header("👨‍🍳 AIシェフと献立相談")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "こんにちは！今日の気分や、冷蔵庫にある食材を教えてください。"}
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- ボタン表示判定ロジック (修正版) ---
    if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        if last_msg["role"] == "assistant":
            json_str = extract_json_from_text(last_msg["content"])
            
            if json_str:
                st.divider()
                st.success("💡 買い物リストが作成されました！")
                
                if st.button("🛒 このリストで買い物に行く (レジへ)", type="primary"):
                    try:
                        # 1. JSONをパース（辞書のリストとして読み込む）
                        raw_list = json.loads(json_str)
                        
                        # 2. ロボット用（英語のみのリスト）を作成して送信
                        # データ形式が [{"en": "Carrot", "ja": "人参"}, ...] となるため
                        robot_list = [item['en'] for item in raw_list]
                        ros_node.send_list(json.dumps(robot_list))
                        
                        # 3. 人間用（日本語＋チェック状態）を保存
                        # 'checked': False を追加しておくのがポイント
                        st.session_state['shopping_memo'] = []
                        for item in raw_list:
                            st.session_state['shopping_memo'].append({
                                'en': item['en'],
                                'ja': item['ja'],
                                'checked': False
                            })
                            
                    except Exception as e:
                        st.error(f"リストの読み込みに失敗しました: {e}")
                        st.session_state['shopping_memo'] = []

                    st.toast("ロボットに出発指令を送りました！🚀")
                    st.session_state['step'] = 'checkout'
                    time.sleep(1)
                    st.rerun()
    # ---------------------------

    if prompt := st.chat_input("例: チキンカレーが食べたい"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("シェフが思考中..."):
                configure_gemini()
                
                # ★重要変更★: 出力形式を {en: "...", ja: "..."} のリストに変更
                system_instruction = """
                あなたはプロの家庭料理シェフ兼買い物アドバイザーです。
                ユーザーと合意してメニューが決定した場合のみ、回答の最後に必ず「買い物リスト」を以下のJSON形式で出力してください。
                
                【重要：出力フォーマット】
                ロボット用の英語名("en")と、人間用の日本語名("ja")をセットにしてください。
                
                出力例:
                ```json
                [
                    {"en": "Chicken", "ja": "鶏肉"},
                    {"en": "Onion", "ja": "玉ねぎ"},
                    {"en": "Curry Roux", "ja": "カレールー"}
                ]
                ```
                """
                model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)
                gemini_history = []
                for msg in st.session_state.messages[:-1]:
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg["content"]]})
                
                chat = model.start_chat(history=gemini_history)
                response = chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()

def show_checkout_screen():
    st.header("🛒 スマート・セルフレジ")
    
    col_nav1, col_nav2 = st.columns([2, 1])
    with col_nav2:
        if st.button("🔙 売り場に戻って商品を追加", use_container_width=True):
            st.session_state['step'] = 'category_select'
            st.rerun()

    st.divider()

    if 'camera_key_id' not in st.session_state:
        st.session_state['camera_key_id'] = 0
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("商品スキャン")
        # （ここは変更なしなので省略、前のコードのまま）
        st.info("カメラにバーコードをかざしてください")
        
        current_key = f"camera_{st.session_state['camera_key_id']}"
        img_file_buffer = st.camera_input("バーコードをスキャン", key=current_key)
        
        manual_code = st.text_input("またはバーコードを手入力")
        if st.button("手入力で追加"):
            if manual_code:
                process_barcode(manual_code)
                st.session_state['camera_key_id'] += 1
                st.rerun()
            
        if img_file_buffer is not None:
            bytes_data = img_file_buffer.getvalue()
            cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
            
            gray_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
            decoded_objects = decode(gray_img)
            if not decoded_objects:
                _, thresh_img = cv2.threshold(gray_img, 100, 255, cv2.THRESH_BINARY)
                decoded_objects = decode(thresh_img)
            
            if decoded_objects:
                for obj in decoded_objects:
                    barcode_data = obj.data.decode("utf-8")
                    st.success(f"読み取り成功: {barcode_data}")
                    process_barcode(barcode_data)
                    st.session_state['camera_key_id'] += 1
                    st.rerun()
                    break 

    with col2:
        # （...買い物リスト表示部分はそのまま...）

        # ここから既存のカート表示
        st.subheader("🧾 お会計 (Current Cart)")
        if st.session_state['cart']:
            for i, item in enumerate(st.session_state['cart']):
                st.write(f"・{item['name']}: ¥{item['price']}")
            
            st.divider()
            total = sum(item['price'] for item in st.session_state['cart'])
            st.markdown(f"### 合計: ¥{total}")
            
            # ★修正1: key="pay_btn" を追加
            if st.button("お会計を確定する", type="primary", key="pay_btn"):
                payment_msg = json.dumps({"action": "payment_completed", "total": total})
                ros_node.send_list(payment_msg)
                st.session_state['step'] = 'payment_complete'
                st.rerun()
                
            # ★修正2: key="clear_cart_btn" を追加（念のためこっちも）
            if st.button("カートを空にする", key="clear_cart_btn"):
                st.session_state['cart'] = []
                st.rerun()
        else:
            st.write("カートは空です")

    # --- 右側：買い物リスト ＆ カート ---
    with col2:
        # --- 買い物リスト表示 ---
        if 'shopping_memo' in st.session_state and st.session_state['shopping_memo']:
            st.warning("📝 **買うものリスト**")
            
            for item in st.session_state['shopping_memo']:
                if isinstance(item, dict):
                    name = item.get('ja', item.get('en', '商品'))
                    is_checked = item.get('checked', False)
                    
                    if is_checked:
                        st.markdown(f"##### ✅ ~~{name}~~ (GET!)")
                    else:
                        st.markdown(f"##### ⬜ {name}")
                else:
                    st.write(item)
            st.divider()
        # --------------------------------
        
        # --- カート表示 ---
        st.subheader("🧾 お会計 (Current Cart)")
        if st.session_state['cart']:
            for i, item in enumerate(st.session_state['cart']):
                st.write(f"・{item['name']}: ¥{item['price']}")
            
            st.divider()
            total = sum(item['price'] for item in st.session_state['cart'])
            st.markdown(f"### 合計: ¥{total}")
            
            # ★修正: キーの名前を 'pay_btn_final' に変更して、重複エラーを回避
            if st.button("お会計を確定する", type="primary", key="pay_btn_final"):
                payment_msg = json.dumps({"action": "payment_completed", "total": total})
                ros_node.send_list(payment_msg)
                st.session_state['step'] = 'payment_complete'
                st.rerun()
                
            # ★修正: こちらも名前を変更 ('clear_cart_btn_final')
            if st.button("カートを空にする", key="clear_cart_btn_final"):
                st.session_state['cart'] = []
                st.rerun()
        else:
            st.write("カートは空です")

def process_barcode(code):
    current_time = time.time()
    
    if 'last_scanned_code' not in st.session_state:
        st.session_state['last_scanned_code'] = None
    if 'last_scan_time' not in st.session_state:
        st.session_state['last_scan_time'] = 0

    last_code = st.session_state['last_scanned_code']
    last_time = st.session_state['last_scan_time']

    if code == last_code and (current_time - last_time) < 3.0:
        return 
    
    if code in PRODUCT_DB:
        product = PRODUCT_DB[code]
        st.session_state['cart'].append(product)
        st.session_state['last_scanned_code'] = code
        st.session_state['last_scan_time'] = current_time
        st.toast(f"追加: {product['name']}")

        # --- ★追加機能: 買い物リストの自動チェック機能 ---
        if 'shopping_memo' in st.session_state:
            scanned_name = product['name'] # 例: "バーモントカレー 中辛"
            
            for item in st.session_state['shopping_memo']:
                target_name = item['ja']   # 例: "カレールー"
                
                # 部分一致判定（どちらかがどちらかを含んでいればOKとする）
                # 例: "カレー" が "バーモントカレー" に含まれるならチェック
                if target_name in scanned_name or scanned_name in target_name:
                    if not item['checked']:
                        item['checked'] = True
                        st.toast(f"✅ リストの「{target_name}」をコンプリート！")
        # -----------------------------------------------

    else:
        if code == last_code and (current_time - last_time) < 3.0:
            return
        st.error(f"登録なし: {code}")
        st.session_state['last_scanned_code'] = code
        st.session_state['last_scan_time'] = current_time

def show_payment_complete_screen():
    st.header("お支払い完了 🎉")
    st.success("ありがとうございました！")
    
    if st.button("トップに戻る"):
        st.session_state['cart'] = []
        st.session_state['step'] = 'category_select'
        st.rerun()
    
    # チャット画面からの直接支払い完了遷移の場合のハンドリング
    if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        if last_msg["role"] == "assistant":
            json_str = extract_json_from_text(last_msg["content"])
            if json_str:
                st.divider()
                st.info("続けてロボットに買い物リストを送りますか？")
                if st.button("🛒 送る"):
                    ros_node.send_list(json_str)
                    st.toast("送信しました！")

def show_navigation_screen():
    with st.sidebar:
        st.title("メニュー")
        if st.button("最初から"):
            st.session_state['step'] = 'category_select'
            st.rerun()
        st.write("ROS2: ✅ Connected")

def main():
    init_cart_session()
    st.title("Supermarket Guide App 🤖")
    
    if 'step' not in st.session_state:
        st.session_state['step'] = 'category_select'
    if 'language' not in st.session_state:
        st.session_state['language'] = '日本語'

    show_navigation_screen()
    step = st.session_state['step']
    
    if step == 'category_select':
        show_category_select_screen()
    elif step == 'chat_consultation':
        show_chat_consultation_screen()
    elif step == 'category_products':
        show_category_products_screen()
    elif step == 'analysis_result':
        show_analysis_result_screen()
    elif step == 'free_input':
        show_free_input_screen()
    elif step == 'checkout':
        show_checkout_screen()
    elif step == 'payment_complete':
        show_payment_complete_screen()

if __name__ == "__main__":
    main()