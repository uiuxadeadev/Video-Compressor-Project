import socket
import threading

# 定数
SERVER_TCP_PORT = 9001
SERVER_UDP_PORT = 9002
BUFFER_SIZE = 4096

# ルーム名をキーにしてトークンのリストを保持する辞書
chat_rooms = {}  

# 具体例: 
# "myRoom"というチャットルームには2つのトークン（ホストとゲスト）が存在
# "anotherRoom"というチャットルームには異なるIPアドレスのホストとゲストが存在
# chat_rooms = {
#     "myRoom": ["host_127.0.0.1", "guest_127.0.0.1"],
#     "anotherRoom": ["host_192.168.0.1", "guest_192.168.0.2"]
# }

# クライアント情報の管理を行う辞書
clients = {}  

# 具体例: 
# "host_127.0.0.1" は IPアドレス "127.0.0.1" のポート5001で接続され、"myRoom"に参加中
# "guest_127.0.0.1" は IPアドレス "127.0.0.1" のポート5002で接続され、"myRoom"に参加中
# "guest_192.168.0.2" は IPアドレス "192.168.0.2" のポート5003で接続され、"anotherRoom"に参加中
# clients = {
#     "host_127.0.0.1": {"address": ("127.0.0.1", 5001), "room": "myRoom"},
#     "guest_127.0.0.1": {"address": ("127.0.0.1", 5002), "room": "myRoom"},
#     "guest_192.168.0.2": {"address": ("192.168.0.2", 5003), "room": "anotherRoom"}
# }

# 今後、チャットルームやクライアントが接続されると、この辞書にデータが追加される


def handle_tcp_connection(conn, addr):
    """TCP接続を処理し、チャットルームの作成や参加を管理する"""
    try:
        data = conn.recv(BUFFER_SIZE)
        if not data:
            return
        
        # ヘッダー処理 (ルーム名サイズ、操作コード、状態コード、ペイロード)
        room_name_size = data[0]
        operation_code = data[1]
        state_code = data[2]
        room_name = data[3:3 + room_name_size].decode('utf-8')
        
        # ルーム作成 (operation_code == 1)
        if operation_code == 1:
            if room_name not in chat_rooms:
                chat_rooms[room_name] = []  # ルームに所属するクライアントを保持
                token = f"host_{addr[0]}".encode('utf-8')  # トークンを作成
                chat_rooms[room_name].append(token)
                conn.sendall(b"Room created " + token)  # 成功メッセージを送信
            else:
                conn.sendall(b"Room already exists")  # ルームが既に存在する場合
        
        # ルーム参加 (operation_code == 2)
        elif operation_code == 2:
            if room_name in chat_rooms:
                token = f"guest_{addr[0]}".encode('utf-8')
                chat_rooms[room_name].append(token)
                conn.sendall(b"Joined room " + token)
            else:
                conn.sendall(b"Room not found")
    
    finally:
        conn.close()

def udp_chat_handler():
    """UDP経由でチャットメッセージを処理する"""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(('0.0.0.0', SERVER_UDP_PORT))  # UDPポートをバインド
    
    while True:
        data, addr = udp_sock.recvfrom(BUFFER_SIZE)  # メッセージ受信
        room_name_size = data[0]
        token_size = data[1]
        room_name = data[2:2 + room_name_size].decode('utf-8')
        token = data[2 + room_name_size:2 + room_name_size + token_size]
        message = data[2 + room_name_size + token_size:].decode('utf-8')
        
        print(f"Received token: {token}, message: {message}")
        
        # トークンが一致するか確認
        if room_name in chat_rooms and token in chat_rooms[room_name]:
            # メッセージを同じルームの他のクライアントにリレー
            for client_token in chat_rooms[room_name]:
                if client_token != token:
                    udp_sock.sendto(message.encode('utf-8'), addr)
        else:
            print(f"Unauthorized access attempt with token: {token}")
            udp_sock.sendto(b"Unauthorized", addr)

def start_server():
    """サーバーの起動と接続受付の開始"""
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind(('0.0.0.0', SERVER_TCP_PORT))
    tcp_sock.listen(5)  # 同時に5つの接続を許可
    
    print(f"Server started on TCP port {SERVER_TCP_PORT} and UDP port {SERVER_UDP_PORT}")
    
    # UDPチャット用のスレッドを開始
    threading.Thread(target=udp_chat_handler, daemon=True).start()
    
    try:
        while True:
            conn, addr = tcp_sock.accept()  # TCP接続を受け入れる
            threading.Thread(target=handle_tcp_connection, args=(conn, addr), daemon=True).start()
    
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        tcp_sock.close()  # サーバー終了時にソケットを閉じる

if __name__ == '__main__':
    start_server()