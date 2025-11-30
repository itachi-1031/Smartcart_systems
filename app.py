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
# 2. Gemini API 設定 (デバッグ用)
# ==========================================
def configure_gemini():
    # .env ファイルを強制的にカレントディレクトリから読み込む
    load_dotenv() 

    api_key = os.getenv("GOOGLE_API_KEY")
    
    # --- 診断用コード (ここから) ---
    if not api_key:
        st.error("❌ エラー: APIキーが読み込めていません。変数名が GOOGLE_API_KEY か確認してください。")
        st.write("現在のカレントディレクトリ:", os.getcwd())
        st.write("このフォルダに .env ファイルがあるか確認してください。")
        return None
    else:
        # キーの最初の5文字だけ表示して確認（セキュリティのため全表示はしない）
        st.success(f"✅ APIキーを読み込みました！ (先頭: {api_key[:5]}...)")
    # --- 診断用コード (ここまで) ---

    genai.configure(api_key=api_key)
    return True
    
@st.cache_resource
def get_gemini_model():
    return genai.GenerativeModel('gemini-2.5-flash')

def analyze_recipe_with_gemini(prompt_text):
    configure_gemini()
    model = get_gemini_model()
    
    # ★重要★
    # チェックリストで照合しやすいように「日本語」での出力を強制します
    system_instruction = """
    あなたはスーパーマーケットの買い物支援AIです。
    ユーザーの要望に応じたレシピを提案してください。
    
    【重要：買い物リスト作成ルール】
    回答の最後には必ず、そのレシピに必要な「買うものリスト」を以下のJSON形式のブロックで出力してください。
    
    ★ルール★
    1. 商品名は必ず「英語」で書いてください（レジの商品名と照合するため）。
    2. 一般的な名称（例: "cabbage", "milk", "pork"）を使ってください。
    
    出力例:
    ```json
    ["cabbage", "milk", "pork", "carrot"]
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

def init_cart_session():
    """カートの中身を初期化"""
    if 'cart' not in st.session_state:
        st.session_state['cart'] = []
    if 'total_price' not in st.session_state:
        st.session_state['total_price'] = 0
        
    # --- 追加: ロボットに頼む用リスト ---
    if 'robot_list' not in st.session_state:
        st.session_state['robot_list'] = []
    
# --- 追加: 売り場と商品のリスト（ナビゲーション用） ---
CATEGORY_ITEMS = {
    "野菜・果物": ["キャベツ", "レタス", "トマト", "玉ねぎ", "人参", "バナナ", "リンゴ"],
    "精肉・鮮魚": ["鶏もも肉", "豚バラ肉", "牛ミンチ", "サケの切り身", "マグロ刺身"],
    "乳製品・卵": ["牛乳", "ヨーグルト", "チーズ", "卵(10個入)", "バター"],
    "調味料・粉": ["醤油", "マヨネーズ", "カレールー", "小麦粉", "パン粉"],
    "お菓子・飲料": ["ポテトチップス", "チョコレート", "コーラ", "お茶", "水(2L)"]
}

# バーコード(JANコード)と商品の対応表（モック）
# ※テスト用に手元の商品のバーコード値に書き換えて試してください
PRODUCT_DB = {
    "4902102000186": {"name": "コカ・コーラ 500ml", "price": 160},
    "4901330573429": {"name": "じゃがりこ サラダ", "price": 150},
    "4902720130541": {"name": "森永牛乳 1000ml", "price": 240},
    "4901301348022": {"name": "ニベア ボディウォッシュ", "price": 450},
    "1920193011005": {"name": "マスカレード・ナイト", "price": 1100},
    "1928030015001": {"name": "なぜ僕らは働くのか", "price": 1500},
    "1111111111111": {"name": "玉ねぎ", "price": 200}, 
}

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
    st.header("売り場から探す")
    st.write("どの売り場の商品をお探しですか？")

    # 売り場リストをボタンとして表示
    categories = list(CATEGORY_ITEMS.keys())
    
    # 2列でボタンを配置
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
    # 現在のリスト確認用
    if st.session_state['robot_list']:
        st.info(f"現在選択中の商品: {st.session_state['robot_list']}")
        if st.button("このリストでロボットに依頼する (確定)", type="primary"):
            json_str = json.dumps(st.session_state['robot_list'], ensure_ascii=False)
            ros_node.send_list(json_str)
            st.toast("ロボットに出発指令を送りました！")
            st.balloons()
            
    st.divider()
    if st.button("単純な質問・自由入力はこちら"):
        st.session_state['step'] = 'free_input'
        st.rerun()

def show_category_products_screen():
    # 選択されたカテゴリを取得
    category = st.session_state.get('selected_category', '未選択')
    
    st.header(f"{category} コーナー")
    
    if st.button("🔙 売り場選択に戻る"):
        st.session_state['step'] = 'category_select'
        st.rerun()
        
    st.divider()

    # そのカテゴリの商品リストを取得
    items = CATEGORY_ITEMS.get(category, [])
    
    # マルチセレクトで商品を選ばせる
    # (既にリストに入っているものはデフォルトで選択済みにする処理)
    current_selection = [item for item in st.session_state['robot_list'] if item in items]
    
    selected_items = st.multiselect(
        "欲しい商品にチェックを入れてください",
        options=items,
        default=current_selection
    )
    
    # リストの更新処理
    if st.button("リストを更新して戻る", type="primary"):
        # 1. 今のカテゴリ以外のアイテムを一時保存
        other_items = [item for item in st.session_state['robot_list'] if item not in items]
        # 2. 「今のカテゴリ以外」+「今回選んだもの」でリストを再構築
        st.session_state['robot_list'] = other_items + selected_items
        
        st.toast("買い物リストを更新しました")
        time.sleep(0.5)
        st.session_state['step'] = 'category_select'
        st.rerun()

    st.divider()
    st.caption("※ここにない商品は自由入力で相談してください")

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
        st.markdown(result_text)
        
        # JSON部分を抽出
        json_str = extract_json_from_text(result_text)
        
        st.divider()
        st.subheader("買い物リストの操作")
        
        if json_str:
            try:
                # JSONをリストに変換
                shopping_list = json.loads(json_str)
                st.info(f"検出されたリスト: {shopping_list}")
                
                # ★★★ ここが重要！ ★★★
                # AIが作ったリストを、アプリ全体の「買い物リスト」として保存する
                st.session_state['robot_list'] = shopping_list
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # ロボットへ送信
                    if st.button("🤖 ロボットに指令を送る", type="primary"):
                        ros_node.send_list(json_str)
                        st.toast("ロボットに指令を送りました！")
                
                with col2:
                    # チェックリスト画面へ移動
                    if st.button("📸 チェックリスト(レジ)へ移動"):
                        st.session_state['step'] = 'checkout'
                        st.rerun()
                        
            except json.JSONDecodeError:
                st.error("リストの読み込みに失敗しました。")
        else:
            st.warning("買い物リストがうまく生成されませんでした。")

    st.divider()
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
            {"role": "assistant", "content": "こんにちは！今日の気分や、冷蔵庫にある食材を教えてください。一緒に献立を考えましょう！"}
        ]

    # 2. 履歴表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 3. 入力処理
    if prompt := st.chat_input("例: チキンカレーが食べたい"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("シェフが思考中..."):
                configure_gemini()
                
                # 日本語でJSONを出力させるプロンプト
                system_instruction = """
                あなたはプロの家庭料理シェフ兼買い物アドバイザーです。
                ユーザーと会話して献立を決めてください。
                
                【重要：買い物リスト生成ルール】
                会話の結果、メニューが決定した場合のみ、回答の最後に必ず「買い物リスト」をJSON形式で出力してください。
                
                ★ルール★
                商品名は「日本語」で出力してください。（チェックリスト用）
                
                出力例:
                ```json
                ["鶏肉", "玉ねぎ", "人参", "カレールー"]
                ```
                """

                model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)
                
                # 履歴変換
                gemini_history = []
                for msg in st.session_state.messages[:-1]:
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg["content"]]})
                
                chat = model.start_chat(history=gemini_history)
                response = chat.send_message(prompt)
                response_text = response.text

                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

    # 4. JSON検出時のボタン表示（ここも修正）
    if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        if last_msg["role"] == "assistant":
            json_str = extract_json_from_text(last_msg["content"])
            
            if json_str:
                st.divider()
                st.info("💡 献立が決まりました！")
                
                # JSONをロードして保存
                try:
                    shopping_list = json.loads(json_str)
                    st.session_state['robot_list'] = shopping_list # ★ここで保存！
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🛒 ロボットに指令", key="chat_send_ros", type="primary"):
                            ros_node.send_list(json_str)
                            st.toast("ロボット送信完了！")
                    with col2:
                        # チェックリストへ移動ボタン
                        if st.button("📸 チェックリストへ", key="chat_go_checkout"):
                            st.session_state['step'] = 'checkout'
                            st.rerun()
                except:
                    pass
                
def show_checkout_screen():
    st.header("🛒 スマート・セルフレジ & チェックリスト")
    
    # カメラIDの初期化
    if 'camera_key_id' not in st.session_state:
        st.session_state['camera_key_id'] = 0
    
    # 画面を2分割（左：カメラ、右：リストと会計）
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📷 商品スキャン")
        st.info("バーコードを写すと、リストから自動でチェックされます")
        
        # カメラ入力（Key Rotationにより連続スキャン対応）
        current_key = f"camera_{st.session_state['camera_key_id']}"
        img_file_buffer = st.camera_input("バーコードをスキャン", key=current_key)
        
        # 手動入力
        manual_code = st.text_input("またはバーコードを手入力")
        if st.button("手入力で追加"):
            if manual_code:
                process_barcode(manual_code)
                st.session_state['camera_key_id'] += 1
                st.rerun()
            
        if img_file_buffer is not None:
            # 画像処理
            bytes_data = img_file_buffer.getvalue()
            cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
            decoded_objects = decode(cv2_img)
            
            if decoded_objects:
                for obj in decoded_objects:
                    barcode_data = obj.data.decode("utf-8")
                    st.success(f"読み取り成功: {barcode_data}")
                    
                    # カートに追加処理
                    process_barcode(barcode_data)
                    
                    # カメラリセット & 画面更新
                    st.session_state['camera_key_id'] += 1
                    st.rerun()
                    break 
            else:
                st.warning("バーコードが検出されませんでした。")

    with col2:
        # --- ここが新機能：チェックリスト表示システム ---
        st.subheader("📝 お買い物チェックリスト")
        
        target_list = st.session_state.get('robot_list', [])
        cart_items = st.session_state.get('cart', [])
        
        # カートに入っている商品名のリストを作成
        scanned_names = [item['name'] for item in cart_items]
        
        if not target_list:
            st.info("買い物リストは空です。「売り場選択」や「AI相談」でリストを作れます。")
        else:
            # 進捗状況の計算
            found_count = 0
            
            # リストのアイテムを一つずつ表示
            for target_item in target_list:
                is_found = False
                
                # 照合ロジック: リストの言葉が、スキャンした商品名に含まれているか？
                # 例: target="牛乳", scanned="森永牛乳 1000ml" -> Hit!
                for scanned_name in scanned_names:
                    if target_item in scanned_name:
                        is_found = True
                        break
                
                if is_found:
                    # チェック済みの表示
                    st.markdown(f"✅ ~~**{target_item}**~~ (Get!)")
                    found_count += 1
                else:
                    # 未チェックの表示
                    st.markdown(f"⬜ {target_item}")
            
            # プログレスバー表示
            progress = found_count / len(target_list)
            st.progress(progress)
            st.caption(f"進捗: {found_count} / {len(target_list)}")

        st.divider()
        
        # --- 既存のお会計表示 ---
        st.subheader("🧾 現在の合計")
        
        if cart_items:
            # 詳細表示（アコーディオンに収納してスッキリさせる）
            with st.expander("カートの中身を見る", expanded=False):
                for item in cart_items:
                    st.write(f"・{item['name']}: ¥{item['price']}")
            
            total = sum(item['price'] for item in cart_items)
            st.metric(label="合計金額", value=f"¥{total:,}")
            
            if st.button("お会計を確定する", type="primary", use_container_width=True):
                payment_msg = json.dumps({"action": "payment_completed", "total": total})
                ros_node.send_list(payment_msg)
                st.session_state['step'] = 'payment_complete'
                st.rerun()
                
            if st.button("カートを空にする", use_container_width=True):
                st.session_state['cart'] = []
                st.rerun()
        else:
            st.write("カートは空です")

def process_barcode(code):
    """バーコードを受け取ってカートに追加する処理"""
    
    # --- 修正: 連続読み取り防止ロジック ---
    current_time = time.time()
    
    # セッションステートの初期化
    if 'last_scanned_code' not in st.session_state:
        st.session_state['last_scanned_code'] = None
    if 'last_scan_time' not in st.session_state:
        st.session_state['last_scan_time'] = 0

    # 「直前と同じコード」かつ「前回の追加から 5秒以内」なら何もしない
    last_code = st.session_state['last_scanned_code']
    last_time = st.session_state['last_scan_time']

    if code == last_code and (current_time - last_time) < 5.0:
        return 
    # ------------------------------------
    
    if code in PRODUCT_DB:
        product = PRODUCT_DB[code]
        st.session_state['cart'].append(product)
        
        # --- 修正: 追加した時間とコードを記録 ---
        st.session_state['last_scanned_code'] = code
        st.session_state['last_scan_time'] = current_time
        # ------------------------------------

        st.toast(f"追加: {product['name']}")
        
        # ★★★ 修正箇所：ここにあった sleep と rerun を削除またはコメントアウト ★★★
        # time.sleep(1) 
        # st.rerun() 
        
    else:
        # 未登録コードの場合
        if code == last_code and (current_time - last_time) < 5.0:
            return
            
        st.error(f"商品マスタ未登録のコードです: {code}")
        st.session_state['last_scanned_code'] = code
        st.session_state['last_scan_time'] = current_time

def show_payment_complete_screen():
    st.header("お支払い完了 🎉")
    st.success("ありがとうございました！")
    st.write("ロボットが荷運び位置へ移動します...")
    
    if st.button("トップに戻る"):
        st.session_state['cart'] = [] # カートクリア
        st.session_state['step'] = 'language_select'
        st.rerun()

    # ★ここより下にあった「ROS送信ボタンの判定」などのコードはすべて削除しました★

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

    init_cart_session()

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