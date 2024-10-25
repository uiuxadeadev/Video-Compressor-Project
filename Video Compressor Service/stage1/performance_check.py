#performance_check.py
import os
import time
from datetime import datetime
import logging
from typing import Tuple, Optional, Dict
import argparse
import random
import string

class FilesystemPerformanceChecker:
    def __init__(self, 
                 upload_dir: str,
                 packet_size: int = 1400,
                 target_packets_per_sec: int = 20000,
                 buffer_size: Optional[int] = None):
        self.upload_dir = upload_dir
        self.packet_size = packet_size
        self.target_packets_per_sec = target_packets_per_sec
        self.buffer_size = buffer_size or (packet_size * target_packets_per_sec)
        self.logger = logging.getLogger('FilesystemPerformance')

    def generate_test_file(self, size_mb: int = 100) -> str:
        """
        MP4形式のテストファイルを生成する
        
        Args:
            size_mb: 生成するファイルのサイズ（MB）
            
        Returns:
            str: 生成したファイルのパス
        """
        test_file = os.path.join(self.upload_dir, f'test_video_{size_mb}mb.mp4')
        
        # MP4ファイルヘッダー（最小限の構造）
        mp4_header = bytes.fromhex(
            '00 00 00 20 66 74 79 70 69 73 6F 6D 00 00 02 00' 
            '69 73 6F 6D 69 73 6F 32 6D 70 34 31 00 00 00 08'
            '6D 6F 6F 76'
        )
        
        # ファイル生成
        chunk_size = 1024 * 1024  # 1MB
        with open(test_file, 'wb') as f:
            # MP4ヘッダーを書き込む
            f.write(mp4_header)
            
            # 残りのデータを書き込む（ビデオストリームを模倣）
            remaining_size = (size_mb * 1024 * 1024) - len(mp4_header)
            while remaining_size > 0:
                write_size = min(chunk_size, remaining_size)
                video_like_data = os.urandom(write_size)
                f.write(video_like_data)
                remaining_size -= write_size
        
        return test_file

    def calculate_transfer_stats(self, packets_per_second: float) -> Dict[str, float]:
        """
        パケット数から転送統計を計算する
        
        Args:
            packets_per_second: 1秒あたりのパケット数
            
        Returns:
            Dict[str, float]: 転送統計情報
        """
        # 実測値の計算
        actual_bytes_per_sec = packets_per_second * self.packet_size
        actual_mb_per_sec = actual_bytes_per_sec / (1024 * 1024)
        
        # 要件値の計算
        required_bytes_per_sec = self.target_packets_per_sec * self.packet_size
        required_mb_per_sec = required_bytes_per_sec / (1024 * 1024)
        
        # 達成率の計算
        achievement_rate = (packets_per_second / self.target_packets_per_sec) * 100
        
        return {
            'actual_pps': packets_per_second,
            'required_pps': float(self.target_packets_per_sec),
            'achievement_rate': achievement_rate,
            'actual_mbps': actual_mb_per_sec,
            'required_mbps': required_mb_per_sec,
            'packet_size_bytes': float(self.packet_size)
        }

    def run_performance_test(self) -> Tuple[Dict[str, float], bool]:
        """
        ファイルシステムの書き込みパフォーマンスをテスト
        
        Returns:
            Tuple[Dict[str, float], bool]: (パフォーマンス統計, パフォーマンス要件を満たしているか)
        """
        test_file = os.path.join(self.upload_dir, 'perftest.mp4')
        test_data = b'x' * self.packet_size
        
        try:
            start_time = datetime.now()
            
            with open(test_file, 'wb', buffering=self.buffer_size) as f:
                for _ in range(self.target_packets_per_sec):
                    f.write(test_data)
                f.flush()
                os.fsync(f.fileno())
            
            elapsed = (datetime.now() - start_time).total_seconds()
            packets_per_second = self.target_packets_per_sec / elapsed
            
            stats = self.calculate_transfer_stats(packets_per_second)
            meets_requirement = stats['actual_pps'] >= stats['required_pps']
            
            if not meets_requirement:
                self.logger.warning(
                    f"Filesystem performance insufficient. "
                    f"Current: {stats['actual_pps']:.0f} packets/sec, "
                    f"Required: {stats['required_pps']:.0f} packets/sec"
                )
            
            return stats, meets_requirement
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def check_disk_space(self, required_space: int) -> bool:
        """
        必要な空き容量があるかチェック
        
        Args:
            required_space: 必要な空き容量（バイト）
            
        Returns:
            bool: 十分な空き容量があるか
        """
        stats = os.statvfs(self.upload_dir)
        free_space = stats.f_frsize * stats.f_bavail
        return free_space >= required_space

def format_performance_results(stats: Dict[str, float]) -> str:
    """
    パフォーマンス結果を整形された文字列として返す
    
    Args:
        stats: パフォーマンス統計情報
        
    Returns:
        str: 整形された結果文字列
    """
    return f"""
パフォーマンス結果
----------------
実測値: {stats['actual_pps']:,.0f} packets/sec
要件値: {stats['required_pps']:,.0f} packets/sec
達成率: {stats['achievement_rate']:.2f}% ({stats['actual_pps']:,.0f} / {stats['required_pps']:,.0f} * 100)

データ転送速度の結果
----------------
パケットサイズ: {stats['packet_size_bytes']:,.0f} bytes
実効転送速度: 約 {stats['actual_mbps']:.2f} MB/sec ({stats['actual_pps']:,.0f} * {stats['packet_size_bytes']:,.0f} bytes)
要件転送速度: {stats['required_mbps']:.2f} MB/sec ({stats['required_pps']:,.0f} * {stats['packet_size_bytes']:,.0f} bytes)
"""

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    parser = argparse.ArgumentParser(description='ファイルシステムパフォーマンステスト')
    parser.add_argument('--upload-dir', required=True, help='テスト用ディレクトリパス')
    parser.add_argument('--packet-size', type=int, default=1400, help='パケットサイズ')
    parser.add_argument('--target-pps', type=int, default=20000, help='目標パケット/秒')
    parser.add_argument('--generate-test-file', type=int, help='テストファイルサイズ(MB)')
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger('main')
    
    # アップロードディレクトリの作成
    os.makedirs(args.upload_dir, exist_ok=True)
    
    checker = FilesystemPerformanceChecker(
        upload_dir=args.upload_dir,
        packet_size=args.packet_size,
        target_packets_per_sec=args.target_pps
    )
    
    # テストファイルの生成（指定された場合）
    if args.generate_test_file:
        test_file = checker.generate_test_file(args.generate_test_file)
        logger.info(f"テストファイルを生成しました: {test_file}")
    
    # パフォーマンステストの実行
    stats, meets_req = checker.run_performance_test()
    
    # 結果の表示
    print(format_performance_results(stats))
    logger.info(f"要件を満たしている: {meets_req}")
    
    return 0 if meets_req else 1

if __name__ == '__main__':
    exit(main())