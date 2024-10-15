import json
import socket
import math

# 関数定義
def floor_function(x):
    return math.floor(x)

def nroot_function(n, x):
    return x ** (1/n)

def reverse_function(s):
    return s[::-1]

def valid_anagram_function(str1, str2):
    return sorted(str1) == sorted(str2)

def sort_function(strArr):
    return sorted(strArr)

# 関数マッピング
functions = {
    "floor": floor_function,
    "nroot": nroot_function,
    "reverse": reverse_function,
    "validAnagram": valid_anagram_function,
    "sort": sort_function,
}

# ソケットの設定
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('localhost', 65432))
server_socket.listen()

print("サーバはポート65432で待機しています...")

while True:
    conn, addr = server_socket.accept()
    with conn:
        print('接続された:', addr)
        data = conn.recv(1024)
        if not data:
            break
        
        request = json.loads(data.decode())
        
        method = request.get("method")
        params = request.get("params", [])
        request_id = request.get("id")

        if method in functions:
            try:
                result = functions[method](*params)
                response = {
                    "results": result,
                    "result_type": type(result).__name__,
                    "id": request_id
                }
            except Exception as e:
                response = {
                    "error": str(e),
                    "id": request_id
                }
        else:
            response = {
                "error": "Method not found",
                "id": request_id
            }

        conn.sendall(json.dumps(response).encode())
