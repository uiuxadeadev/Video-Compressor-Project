# クライアントサーバー間通信アプリケーション

このプロジェクトは、Pythonのソケット通信を使ったシンプルなクライアントサーバーアプリケーションです。クライアントはユーザーからの入力をサーバーに送信し、サーバーは `Faker` ライブラリを使用してランダムな応答を生成し、クライアントに返します。TCP通信を使用してクライアントとサーバー間でメッセージのやり取りを行います。

## 構成

このプロジェクトは2つのPythonスクリプトで構成されています。

- `server.py`：クライアントからの接続を待機し、受け取ったメッセージに基づいてランダムな応答を返すサーバースクリプト。
- `client.py`：ユーザーからの入力をサーバーに送信し、サーバーからの応答を受け取るクライアントスクリプト。

## 依存関係

このアプリケーションは、以下のPythonパッケージを使用しています。

- `faker`: サーバー側でランダムなデータを生成するために使用されます。

依存関係をインストールするために、以下のコマンドを実行してください。

```bash
pip install faker
```

## ファイル構成

```
.
├── client.py       # クライアントスクリプト
├── server.py       # サーバースクリプト
└── README.md       # この説明書
```

## 実行方法

1. **サーバーの起動**

   まず、`server.py` を実行してサーバーを起動します。サーバーはクライアントからの接続を待機します。

   ```bash
   python server.py
   ```

   出力例：
   ```
   Starting up on localhost port 65432
   Waiting for a connection...
   ```

2. **クライアントの起動**

   別のターミナルを開き、`client.py` を実行してクライアントを起動します。クライアントはサーバーに接続し、ユーザーが入力したメッセージを送信します。

   ```bash
   python client.py
   ```

   実行すると、次のようにユーザーの入力を求められます。

   ```
   Enter message to send to the server: <ここにメッセージを入力>
   ```

3. **サーバーからの応答**

   サーバーは `Faker` ライブラリを使用してランダムなメッセージを生成し、クライアントに返します。クライアントはサーバーからの応答を受け取り、それを表示します。

   クライアント出力例：
   ```
   Enter message to send to the server: Hello Server!
   Received response from server: The quick brown fox jumps over the lazy dog.
   ```

   サーバー出力例：
   ```
   Connection from ('127.0.0.1', 65432)
   Received message: Hello Server!
   Sending back response: The quick brown fox jumps over the lazy dog.
   ```

## 注意事項

- サーバーは常に先に起動させてください。
- クライアントとサーバーは同じホスト（ローカルマシン）で通信します。異なるホストで通信する場合は、`server.py` の `localhost` を対応するホストのIPアドレスに変更してください。

## 参考

- [Pythonソケットモジュール](https://docs.python.org/ja/3/library/socket.html)
- [Fakerライブラリ](https://faker.readthedocs.io/en/master/) 

## ライセンス

このプロジェクトにはライセンスがありません。