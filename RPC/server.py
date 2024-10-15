import json
import socket
import math

def floor_function(x):
    """指定した数値を切り捨てて最も近い整数を返す関数"""
    return math.floor(x)

def nroot_function(n, x):
    """n乗根を計算する関数"""
    return x ** (1/n)

def reverse_function(s):
    """文字列を逆にして返す関数"""
    return s[::-1]

def valid_anagram_function(str1, str2):
    """2つの文字列がアナグラムであるかを判定する関数"""
    return sorted(str1) == sorted(str2)

def sort_function(strArr):
    """文字列の配列をソートして返す関数"""
    return sorted(strArr)

# 関数マッピング
# メソッド名を関数にマッピングする辞書を作成
functions = {
    "floor": floor_function,
    "nroot": nroot_function,
    "reverse": reverse_function,
    "validAnagram": valid_anagram_function,
    "sort": sort_function,
}

# ソケットの設定
# TCP/IPソケットを作成し、特定のアドレスとポートでバインド
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('localhost', 65432))  # ローカルホストのポート65432で待機
server_socket.listen()  # 接続を待機

print("サーバはポート65432で待機しています...")

while True:
    # クライアントからの接続を待ち、接続されたら受け入れる
    conn, addr = server_socket.accept()
    with conn:
        print('接続された:', addr)  # 接続されたクライアントのアドレスを表示
        data = conn.recv(1024)  # クライアントからデータを受信
        if not data:  # データがなければループを終了
            break
        
        # 受信したデータをJSONとしてデコード
        request = json.loads(data.decode())
        
        # リクエストからメソッド名、パラメータ、リクエストIDを取得
        method = request.get("method")
        params = request.get("params", [])  # デフォルト値として空のリストを指定
        request_id = request.get("id")

        # リクエストされたメソッドが関数マッピングに存在するかを確認
        if method in functions:
            try:
                # 対応する関数を呼び出し、結果を取得
                result = functions[method](*params)
                # 成功したレスポンスを作成
                response = {
                    "results": result,
                    "result_type": type(result).__name__,  # 結果の型を取得
                    "id": request_id  # リクエストIDを保持
                }
            except Exception as e:
                # エラーが発生した場合、エラーメッセージをレスポンスに含める
                response = {
                    "error": str(e),
                    "id": request_id
                }
        else:
            # メソッドが存在しない場合、エラーレスポンスを作成
            response = {
                "error": "Method not found",
                "id": request_id
            }

        # レスポンスをクライアントに送信
        conn.sendall(json.dumps(response).encode())
