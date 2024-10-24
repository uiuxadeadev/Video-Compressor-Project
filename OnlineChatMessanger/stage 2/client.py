import socket
import threading

BUFFER_SIZE = 4096
SERVER_TCP_PORT = 9001
SERVER_UDP_PORT = 9002

def tcp_connect(server_address, room_name, operation):
    """TCPでチャットルームを作成または参加"""
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.connect((server_address, SERVER_TCP_PORT))
    
    room_name_bytes = room_name.encode('utf-8')
    room_name_size = len(room_name_bytes)
    
    # TCPプロトコルの構築 (ルーム名サイズ、操作コード、状態コード、ルーム名)
    packet = bytes([room_name_size]) + bytes([operation]) + bytes([0]) + room_name_bytes
    tcp_sock.sendall(packet)
    
    response = tcp_sock.recv(BUFFER_SIZE)
    response_str = response.decode('utf-8')
    print(response_str)
    
    # トークンの部分を正しく取得する
    if "Room created" in response_str or "Joined room" in response_str:
        token = response_str.split()[-1].encode('utf-8')  # トークン部分のみ抽出
        return token
    
    return b''

def udp_chat(server_address, token, room_name):
    """UDPでメッセージ送信と受信を行う"""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def receive_messages():
        while True:
            data, _ = udp_sock.recvfrom(BUFFER_SIZE)
            print("Received:", data.decode('utf-8'))
    
    # メッセージの受信スレッドを開始
    threading.Thread(target=receive_messages, daemon=True).start()
    
    while True:
        message = input("Message: ").encode('utf-8')
        room_name_bytes = room_name.encode('utf-8')
        token_size = len(token)
        
        # UDPメッセージのパケットフォーマットを再確認して修正
        packet = bytes([len(room_name_bytes)]) + bytes([token_size]) + room_name_bytes + token + message
        udp_sock.sendto(packet, (server_address, SERVER_UDP_PORT))

def start_client():
    """クライアントの起動"""
    server_address = input("Enter server address (default '127.0.0.1'): ") or '127.0.0.1'
    room_name = input("Enter room name: ")
    operation = int(input("1: Create room, 2: Join room: "))
    
    # TCPでルーム作成または参加
    token = tcp_connect(server_address, room_name, operation)
    
    if token:
        udp_chat(server_address, token, room_name)
    else:
        print("Failed to connect to room.")

if __name__ == '__main__':
    start_client()
