# --- filename: cart_scanner.py ---
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import json
import time

# --- 簡易商品データベース ---
# 実際の商品のJANコード（バーコード下の数字）に書き換えてください
PRODUCT_DB = {
    "4900000000001": {"name": "りんご", "price": 150},
    "4900000000002": {"name": "牛乳", "price": 200},
    "4900000000003": {"name": "卵パック", "price": 250},
    "4900000000004": {"name": "キャベツ", "price": 120},
    # テスト用（手元の適当なバーコードで試すならここに追加）
}

class CartScannerNode(Node):
    def __init__(self):
        super().__init__('product_recognition_calculator')
        
        # カートの状態を配信するPublisher
        # トピック名: /cart_update
        self.publisher_ = self.create_publisher(String, 'cart_update', 10)
        
        # 画像配信用のPublisher
        self.image_publisher_ = self.create_publisher(CompressedImage, 'cart/image_raw/compressed', 10)
        
        # カートの中身
        self.cart_items = []
        
        # 連続読み取り防止用のバッファ
        self.last_code = None
        self.last_scan_time = 0
        
        self.get_logger().info('カメラ起動中... "q"キーで終了します')
        self.run_camera_loop()

    def run_camera_loop(self):
        # カメラ起動 (0, 1, 2... と順に試す)
        cap = None
        for i in range(3):
            self.get_logger().info(f"カメラデバイス /dev/video{i} を試行中...")
            temp_cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            
            if temp_cap.isOpened():
                # テスト読み込み
                ret, _ = temp_cap.read()
                if ret:
                    cap = temp_cap
                    self.get_logger().info(f"カメラ /dev/video{i} の接続に成功しました！")
                    break
                else:
                    temp_cap.release()
            
        if cap is None:
            self.get_logger().error("有効なカメラが見つかりませんでした。")
            self.get_logger().error("【対処法】")
            self.get_logger().error("1. WindowsのPowerShell(管理者)で 'usbipd wsl list' を実行し、カメラの状態を確認してください。")
            self.get_logger().error("2. 'Not attached' の場合: 'usbipd wsl attach --busid <BUSID>' を実行してください。")
            self.get_logger().error("3. 'Attached' の場合: 一度 'usbipd wsl detach --busid <BUSID>' をしてから、再度 attach してください。")
            return

        # カメラ設定
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        try:
            while rclpy.ok():
                ret, frame = cap.read()
                if not ret:
                    self.get_logger().warn("フレームの取得に失敗しました。再試行中...")
                    time.sleep(0.5)
                    continue

                # バーコード検出
                decoded_objects = decode(frame)
                
                for obj in decoded_objects:
                    # バーコードのデータを取得
                    barcode_data = obj.data.decode("utf-8")
                    
                    # 枠線を描画（視覚確認用）
                    points = obj.polygon
                    if len(points) == 4:
                        pts = [(p.x, p.y) for p in points]
                        # cv2.polylines(frame, [np.array(pts)], True, (0, 255, 0), 2)

                    # --- 商品認識・計算ロジック ---
                    # 同じ商品を連続で読み込まないように2秒あける
                    if barcode_data != self.last_code or (time.time() - self.last_scan_time > 2.0):
                        self.process_item(barcode_data)
                        self.last_code = barcode_data
                        self.last_scan_time = time.time()
                    
                    # 認識したコードを画面に表示
                    cv2.putText(frame, barcode_data, (obj.rect.left, obj.rect.top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # カメラ映像を表示（デバッグ用ウィンドウ）
                cv2.imshow('Smart Cart Scanner', frame)
                
                # ROSへ画像を送信
                self.publish_image(frame)

                # ROSのコールバック処理を回す（Publishなど）
                rclpy.spin_once(self, timeout_sec=0.01)

                # 'q'キーで終了
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        finally:
            if cap:
                cap.release()
            cv2.destroyAllWindows()

    def process_item(self, barcode):
        """図の「商品認識」→「計算」を行う部分"""
        if barcode in PRODUCT_DB:
            item = PRODUCT_DB[barcode]
            self.cart_items.append(item)
            
            # 合計金額計算
            total_price = sum(i['price'] for i in self.cart_items)
            
            # JSON作成
            cart_data = {
                "latest_item": item['name'],
                "total_price": total_price,
                "item_count": len(self.cart_items),
                "items": self.cart_items
            }
            
            # JSON送信
            msg = String()
            msg.data = json.dumps(cart_data, ensure_ascii=False)
            self.publisher_.publish(msg)
            
            self.get_logger().info(f'追加: {item["name"]} (合計: {total_price}円)')
        else:
            self.get_logger().warn(f'未登録の商品です: {barcode}')

    def publish_image(self, frame):
        """OpenCVの画像をROSのCompressedImageメッセージとして送信"""
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"
        
        # JPEGに圧縮
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            msg.data = np.array(buffer).tobytes()
            self.image_publisher_.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = CartScannerNode()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()