# performance_manager.py

import os
import time
import psutil
import logging
from typing import Tuple, Dict, Optional
from common.logging_config import LogConfig

class PerformanceManager:
    """Manages server performance requirements and monitoring"""
    
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        self.packet_size = 1400
        self.min_packets_per_second = 5000
        self.min_processing_cpu_percent = 60
        self.io_buffer_size = self.packet_size * self.min_packets_per_second
        self.logger = LogConfig.get_component_logger("PerformanceManager")

    def check_system_resources(self) -> Tuple[bool, str]:
        """
        Check if system meets all performance requirements
        
        Returns:
            Tuple[bool, str]: (requirements met, description)
        """
        # 1. Check CPU availability for video processing
        cpu_check = self._check_cpu_availability()
        if not cpu_check[0]:
            return cpu_check

        # 2. Check IO performance meets packet processing requirements
        io_check = self._check_io_performance()
        if not io_check[0]:
            return io_check

        # 3. Check memory availability
        memory_check = self._check_memory_availability()
        if not memory_check[0]:
            return memory_check

        return True, "All performance requirements met"

    def _check_cpu_availability(self) -> Tuple[bool, str]:
        """Check if enough CPU is available for video processing"""
        cpu_percent = psutil.cpu_percent(interval=1)
        available_cpu = 100 - cpu_percent
        
        if available_cpu < self.min_processing_cpu_percent:
            msg = f"Insufficient CPU available. Need {self.min_processing_cpu_percent}%, but only {available_cpu}% available"
            self.logger.warning(msg)
            return False, msg
            
        return True, f"Sufficient CPU available: {available_cpu}%"

    def _check_io_performance(self) -> Tuple[bool, str]:
        """Check if IO performance meets packet processing requirements"""
        test_file = os.path.join(self.upload_dir, 'perf_test')
        test_data = b'x' * self.packet_size
        
        try:
            # Test write performance
            start_time = time.time()
            with open(test_file, 'wb', buffering=self.io_buffer_size) as f:
                for _ in range(self.min_packets_per_second):
                    f.write(test_data)
                f.flush()
                os.fsync(f.fileno())
            
            elapsed = time.time() - start_time
            achieved_pps = self.min_packets_per_second / elapsed
            
            if achieved_pps < self.min_packets_per_second:
                msg = f"Insufficient IO performance. Achieved {achieved_pps:.0f} packets/sec, required {self.min_packets_per_second}"
                self.logger.warning(msg)
                return False, msg
            
            return True, f"IO performance sufficient: {achieved_pps:.0f} packets/sec"
            
        except Exception as e:
            msg = f"IO performance test failed: {e}"
            self.logger.error(msg)
            return False, msg
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def _check_memory_availability(self) -> Tuple[bool, str]:
        """Check if enough memory is available for video processing"""
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        
        # Require at least 2GB available memory for video processing
        if available_gb < 2:
            msg = f"Insufficient memory available. Need 2GB, but only {available_gb:.1f}GB available"
            self.logger.warning(msg)
            return False, msg
            
        return True, f"Sufficient memory available: {available_gb:.1f}GB"

    def monitor_processing_resources(self) -> Dict[str, float]:
        """
        Monitor resource usage during video processing
        
        Returns:
            Dict containing current resource usage metrics
        """
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_io_counters': psutil.disk_io_counters()._asdict()
        }

    def can_process_new_task(self) -> Tuple[bool, Optional[str]]:
        """
        Check if system can handle a new video processing task
        
        Returns:
            Tuple[bool, Optional[str]]: (can process, error message if any)
        """
        # Check system resources
        resources_ok, msg = self.check_system_resources()
        if not resources_ok:
            return False, msg

        # Check current processing load
        current_resources = self.monitor_processing_resources()
        if current_resources['cpu_percent'] > (100 - self.min_processing_cpu_percent):
            return False, "System is currently under heavy load"

        return True, None

    def log_performance_metrics(self, metrics: Dict[str, float]):
        """Log current performance metrics"""
        self.logger.info(
            "Performance Metrics - "
            f"CPU: {metrics['cpu_percent']}%, "
            f"Memory: {metrics['memory_percent']}%, "
            f"Disk IO: {metrics['disk_io_counters']}"
        )