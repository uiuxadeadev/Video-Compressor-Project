# server/performance_manager.py

import os
import time
import psutil
from datetime import datetime
import logging
from typing import Dict, Tuple, Optional
from common.logging_config import LogConfig

class PerformanceManager:
    """Manages server performance requirements and monitoring"""
    
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        self.packet_size = 1400  # Required packet size in bytes
        self.min_packets_per_second = 5000  # Minimum required packets per second
        self.min_processing_cpu_percent = 60
        self.io_buffer_size = self.packet_size * self.min_packets_per_second
        self.logger = LogConfig.get_component_logger("PerformanceManager")
        
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

    def check_system_resources(self) -> Tuple[bool, str]:
        """
        総合的なシステムリソースチェック
        
        Returns:
            Tuple[bool, str]: (要件を満たしているか, メッセージ)
        """
        # 1. CPU使用率のチェック
        cpu_available = 100 - psutil.cpu_percent(interval=1)
        if cpu_available < self.min_processing_cpu_percent:
            return False, f"Insufficient CPU available. Need {self.min_processing_cpu_percent}%, but only {cpu_available}% available"

        # 2. メモリ使用率のチェック
        memory = psutil.virtual_memory()
        if memory.available < 2 * 1024 * 1024 * 1024:  # 2GB未満
            return False, f"Insufficient memory. Only {memory.available / (1024*1024*1024):.1f}GB available"

        # 3. IOパフォーマンスのチェック
        stats, meets_io_req = self.check_io_performance()
        if not meets_io_req:
            return False, f"IO performance insufficient. Current: {stats['actual_pps']:.0f} packets/sec, Required: {self.min_packets_per_second}"

        # 4. ディスク容量のチェック
        if not self._check_disk_space():
            return False, "Insufficient disk space"

        # 全てのチェックをパス
        self._log_performance_results(stats, True)
        return True, "All system requirements met"

    def check_io_performance(self) -> Tuple[Dict[str, float], bool]:
        """
        Check if IO performance meets packet processing requirements
        
        Returns:
            Tuple[Dict[str, float], bool]: (performance stats, meets requirements)
        """
        test_file = os.path.join(self.upload_dir, 'perf_test')
        test_data = b'x' * self.packet_size
        
        try:
            start_time = datetime.now()
            
            # Write test data
            with open(test_file, 'wb', buffering=self.io_buffer_size) as f:
                for _ in range(self.min_packets_per_second):
                    f.write(test_data)
                f.flush()
                os.fsync(f.fileno())
            
            # Calculate performance metrics
            elapsed = (datetime.now() - start_time).total_seconds()
            actual_pps = self.min_packets_per_second / elapsed
            
            # Calculate statistics
            stats = self._calculate_performance_stats(actual_pps)
            meets_requirement = stats['actual_pps'] >= stats['required_pps']
            
            return stats, meets_requirement
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def _check_disk_space(self) -> bool:
        """
        ディスク容量のチェック
        
        Returns:
            bool: 十分な容量があるか
        """
        stats = psutil.disk_usage(self.upload_dir)
        required_space = 10 * 1024 * 1024 * 1024  # 最低10GB必要とする
        return stats.free >= required_space

    def _calculate_performance_stats(self, actual_pps: float) -> Dict[str, float]:
        """Calculate performance statistics"""
        actual_bytes_per_sec = actual_pps * self.packet_size
        actual_mb_per_sec = actual_bytes_per_sec / (1024 * 1024)
        
        required_bytes_per_sec = self.min_packets_per_second * self.packet_size
        required_mb_per_sec = required_bytes_per_sec / (1024 * 1024)
        
        achievement_rate = (actual_pps / self.min_packets_per_second) * 100
        
        return {
            'actual_pps': actual_pps,
            'required_pps': float(self.min_packets_per_second),
            'achievement_rate': achievement_rate,
            'actual_mbps': actual_mb_per_sec,
            'required_mbps': required_mb_per_sec,
            'packet_size_bytes': float(self.packet_size)
        }

    def _format_performance_results(self, stats: Dict[str, float]) -> str:
        """Format performance results as string"""
        return f"""
Performance Results
-----------------
Actual Rate: {stats['actual_pps']:,.0f} packets/sec
Required Rate: {stats['required_pps']:,.0f} packets/sec
Achievement Rate: {stats['achievement_rate']:.2f}% ({stats['actual_pps']:,.0f} / {stats['required_pps']:,.0f} * 100)

Data Transfer Results
-------------------
Packet Size: {stats['packet_size_bytes']:,.0f} bytes
Actual Transfer Rate: ~{stats['actual_mbps']:.2f} MB/sec ({stats['actual_pps']:,.0f} * {stats['packet_size_bytes']:,.0f} bytes)
Required Transfer Rate: {stats['required_mbps']:.2f} MB/sec ({stats['required_pps']:,.0f} * {stats['packet_size_bytes']:,.0f} bytes)

System Resources
--------------
CPU Available: {100 - psutil.cpu_percent()}%
Memory Available: {psutil.virtual_memory().available / (1024*1024*1024):.1f}GB
Disk Space Available: {psutil.disk_usage(self.upload_dir).free / (1024*1024*1024):.1f}GB
"""

    def _log_performance_results(self, stats: Dict[str, float], meets_requirement: bool):
        """Log performance results"""
        result_str = self._format_performance_results(stats)
        if meets_requirement:
            self.logger.info("Performance requirements met")
        else:
            self.logger.warning("Performance requirements not met")
        self.logger.info(result_str)
        print(result_str)

    def can_process_new_task(self) -> Tuple[bool, Optional[str]]:
        """
        Check if system can handle a new video processing task
        
        Returns:
            Tuple[bool, Optional[str]]: (can process, error message if any)
        """
        meets_req, msg = self.check_system_resources()
        if not meets_req:
            return False, msg
        
        return True, None