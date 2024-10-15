import socket
import sys
from faker import Faker

# Fakerオブジェクトを作成
fake = Faker()

# サーバー用のTCP/IPソケットを作成
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# サーバーアドレスとポートを定義
server_address = ('localhost', 65432)
print('Starting up on {} port {}'.format(*server_address))

# ソケットをアドレスにバインド
sock.bind(server_address)

# 接続要求を待つリスニングモードに設定
sock.listen(1)

while True:
    print('Waiting for a connection...')
    connection, client_address = sock.accept()

    try:
        print('Connection from', client_address)

        # データのやり取りを行うループ
        while True:
            data = connection.recv(1024).decode('utf-8')
            print('Received message:', data)

            if data:
                # Fakerでランダムな応答メッセージを生成
                fake_response = fake.sentence()
                print('Sending back response:', fake_response)
                connection.sendall(fake_response.encode('utf-8'))
            else:
                print('No data from', client_address)
                break

    finally:
        # 接続を閉じる
        connection.close()
