const net = require('net');

const client = new net.Socket();
const request = {
    method: "floor",
    params: [40.4],
    param_types: ["int"],
    id: 1
};

// サーバに接続
client.connect(65432, 'localhost', () => {
    console.log('サーバに接続しました');
    client.write(JSON.stringify(request));
});

// サーバからのレスポンスを受信
client.on('data', (data) => {
    const response = JSON.parse(data);
    console.log('受信したレスポンス:', response);
    client.destroy(); // 通信を終了
});

// エラー処理
client.on('error', (err) => {
    console.error('エラー:', err);
});

// 切断処理
client.on('close', () => {
    console.log('接続が閉じました');
});
