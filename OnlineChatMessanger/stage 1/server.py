import socket
import time

# 定数
SERVER_ADDRESS = '0.0.0.0'
SERVER_PORT = 9001
BUFFER_SIZE = 4096
TIMEOUT = 10  # クライアントのタイムアウト秒数

# クライアントの接続管理
clients = {}

def handle_client_message(data, address):
    """クライアントからのメッセージを処理し、他のクライアントにリレーする"""
    usernamelen = data[0]
    username = data[1:usernamelen + 1].decode('utf-8')
    message = data[usernamelen + 1:].decode('utf-8')
    
    print(f'Received message from {username} ({address}): {message}')
    
    # クライアントをリストに保存（最後にメッセージを受信した時間を記録）
    clients[address] = time.time()
    
    # メッセージを他のクライアントにリレー
    for client, last_active in list(clients.items()):
        if time.time() - last_active > TIMEOUT:
            print(f'Client {client} timed out')
            del clients[client]  # タイムアウトしたクライアントを削除
            continue
        if client != address:  # 自分以外のクライアントに送信
            sock.sendto(data, client)

def start_server():
    """サーバーを起動してクライアントの接続を待ち受ける"""
    print(f'Starting server on {SERVER_ADDRESS}:{SERVER_PORT}')
    
    # UDPソケットを作成
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_ADDRESS, SERVER_PORT))
    
    try:
        while True:
            print('Waiting to receive message...')
            data, address = sock.recvfrom(BUFFER_SIZE)
            if data:
                handle_client_message(data, address)
    except Exception as e:
        print(f'Server error: {e}')
    finally:
        sock.close()

if __name__ == '__main__':
    start_server()
