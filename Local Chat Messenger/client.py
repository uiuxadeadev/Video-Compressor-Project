import socket
import sys

# クライアント用のTCP/IPソケットを作成
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# サーバーアドレスとポートを指定
server_address = ('localhost', 65432)
print('Connecting to {} port {}'.format(*server_address))

# サーバーに接続
try:
    sock.connect(server_address)
except socket.error as e:
    print(f'Connection error: {e}')
    sys.exit(1)

try:
    # ユーザーからの入力を受け取る
    message = input("Enter message to send to the server: ")

    # メッセージをサーバーに送信
    sock.sendall(message.encode('utf-8'))

    # サーバーからの応答を待つ
    data = sock.recv(1024)
    print('Received response from server:', data.decode('utf-8'))

finally:
    # ソケットを閉じる
    print('Closing socket')
    sock.close()
