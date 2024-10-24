import socket

# 定数
BUFFER_SIZE = 4096
SERVER_PORT = 9001

def send_message(sock, server_address, username, message):
    """メッセージをサーバーに送信"""
    usernamelen = len(username)
    packet = bytes([usernamelen]) + username + message
    sock.sendto(packet, server_address)

def receive_message(sock):
    """サーバーからのメッセージを受信"""
    data, _ = sock.recvfrom(BUFFER_SIZE)
    usernamelen = data[0]
    sender_username = data[1:usernamelen + 1].decode('utf-8')
    received_message = data[usernamelen + 1:].decode('utf-8')
    return sender_username, received_message

def start_client():
    """クライアントを起動してサーバーと通信"""
    # UDPソケットの作成
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # サーバーアドレスとユーザー名の入力
    server_address = input("Enter server address (default: '127.0.0.1'): ") or '127.0.0.1'
    server_address = (server_address, SERVER_PORT)
    username = input("Enter your username: ").encode('utf-8')
    
    try:
        while True:
            message = input("Enter message: ").encode('utf-8')
            if message:
                send_message(sock, server_address, username, message)
                
                # サーバーからのメッセージを受信して表示
                sender_username, received_message = receive_message(sock)
                print(f'{sender_username}: {received_message}')
    except Exception as e:
        print(f'Client error: {e}')
    finally:
        print('Closing socket')
        sock.close()

if __name__ == '__main__':
    start_client()
