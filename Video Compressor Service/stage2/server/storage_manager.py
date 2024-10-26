# storage_manager.py

import os
import shutil
import threading
import logging
from typing import Optional, Tuple, List, Dict
from common.logging_config import LogConfig
from datetime import datetime, timedelta

class StorageManager:
    """Manages storage limits and temporary file handling"""
    
    def __init__(self, work_dir: str, max_storage_bytes: int = 4 * 1024**4):
        self.work_dir = work_dir
        self.max_storage = max_storage_bytes
        self.lock = threading.Lock()
        self.file_registry: Dict[str, Dict] = {}
        self.logger = LogConfig.get_component_logger("StorageManager")
        
        if not os.path.exists(work_dir):
            os.makedirs(work_dir)
            
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start background thread for periodic cleanup"""
        def cleanup_worker():
            while True:
                try:
                    self.cleanup_expired_files()
                    threading.Event().wait(300)  # Run every 5 minutes
                except Exception as e:
                    self.logger.error(f"Cleanup worker error: {e}")

        self.cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self.cleanup_thread.start()

    def get_current_usage(self) -> int:
        """
        Get current storage usage in bytes
        
        Returns:
            int: Total bytes used
        """
        total = 0
        for root, _, files in os.walk(self.work_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total += os.path.getsize(file_path)
                except OSError as e:
                    self.logger.error(f"Error getting file size for {file_path}: {e}")
        return total

    def check_storage_available(self, required_bytes: int) -> Tuple[bool, str]:
        """
        Check if there's enough storage available
        
        Args:
            required_bytes: Number of bytes needed
            
        Returns:
            Tuple[bool, str]: (is available, message)
        """
        current_usage = self.get_current_usage()
        available = self.max_storage - current_usage
        
        if required_bytes > available:
            return False, f"Insufficient storage. Need {required_bytes}, but only {available} available"
            
        # Also check actual filesystem
        stats = shutil.disk_usage(self.work_dir)
        if required_bytes > stats.free:
            return False, f"Insufficient disk space. Need {required_bytes}, but only {stats.free} free"
            
        return True, "Storage available"

    def register_file(self, file_path: str, task_id: str, 
                     expiry_hours: int = 24) -> Optional[str]:
        """
        Register a file for tracking
        
        Args:
            file_path: Path to the file
            task_id: Associated task ID
            expiry_hours: Hours until file expires
            
        Returns:
            Optional[str]: File ID if successful
        """
        try:
            file_size = os.path.getsize(file_path)
            storage_available, msg = self.check_storage_available(file_size)
            
            if not storage_available:
                self.logger.error(f"Storage check failed: {msg}")
                return None
                
            file_id = f"{task_id}_{os.path.basename(file_path)}"
            expiry_time = datetime.now() + timedelta(hours=expiry_hours)
            
            with self.lock:
                self.file_registry[file_id] = {
                    'path': file_path,
                    'size': file_size,
                    'task_id': task_id,
                    'created_at': datetime.now(),
                    'expires_at': expiry_time
                }
                
            self.logger.info(f"Registered file {file_id} of size {file_size}")
            return file_id
            
        except Exception as e:
            self.logger.error(f"Error registering file: {e}")
            return None

    def remove_file(self, file_id: str) -> bool:
        """
        Remove a file and its registration
        
        Args:
            file_id: File identifier
            
        Returns:
            bool: Success status
        """
        with self.lock:
            file_info = self.file_registry.get(file_id)
            if not file_info:
                return False
                
            try:
                file_path = file_info['path']
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.file_registry[file_id]
                self.logger.info(f"Removed file {file_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error removing file {file_id}: {e}")
                return False

    def cleanup_expired_files(self) -> int:
        """
        Remove expired files
        
        Returns:
            int: Number of files cleaned up
        """
        current_time = datetime.now()
        cleaned_count = 0
        
        with self.lock:
            file_ids = list(self.file_registry.keys())
            for file_id in file_ids:
                file_info = self.file_registry[file_id]
                if current_time > file_info['expires_at']:
                    if self.remove_file(file_id):
                        cleaned_count += 1
                        
        self.logger.info(f"Cleaned up {cleaned_count} expired files")
        return cleaned_count

    def cleanup_task_files(self, task_id: str) -> int:
        """
        Remove all files associated with a task
        
        Args:
            task_id: Task identifier
            
        Returns:
            int: Number of files cleaned up
        """
        cleaned_count = 0
        
        with self.lock:
            file_ids = [fid for fid, info in self.file_registry.items() 
                       if info['task_id'] == task_id]
            for file_id in file_ids:
                if self.remove_file(file_id):
                    cleaned_count += 1
                    
        return cleaned_count

    def get_storage_stats(self) -> Dict:
        """
        Get storage statistics
        
        Returns:
            Dict containing storage statistics
        """
        current_usage = self.get_current_usage()
        disk_stats = shutil.disk_usage(self.work_dir)
        
        return {
            'total_capacity': self.max_storage,
            'current_usage': current_usage,
            'available_storage': self.max_storage - current_usage,
            'usage_percent': (current_usage / self.max_storage) * 100,
            'file_count': len(self.file_registry),
            'disk_total': disk_stats.total,
            'disk_used': disk_stats.used,
            'disk_free': disk_stats.free
        }

    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """
        Get information about a registered file
        
        Args:
            file_id: File identifier
            
        Returns:
            Optional[Dict]: File information if found
        """
        with self.lock:
            file_info = self.file_registry.get(file_id)
            if file_info:
                return {
                    'path': file_info['path'],
                    'size': file_info['size'],
                    'task_id': file_info['task_id'],
                    'created_at': file_info['created_at'].isoformat(),
                    'expires_at': file_info['expires_at'].isoformat()
                }
        return None

    def extend_file_expiry(self, file_id: str, additional_hours: int) -> bool:
        """
        Extend the expiry time of a file
        
        Args:
            file_id: File identifier
            additional_hours: Hours to add to expiry time
            
        Returns:
            bool: Success status
        """
        with self.lock:
            file_info = self.file_registry.get(file_id)
            if file_info:
                file_info['expires_at'] += timedelta(hours=additional_hours)
                self.logger.info(f"Extended expiry for {file_id} by {additional_hours} hours")
                return True
        return False

    def get_expired_files(self) -> List[str]:
        """
        Get list of expired file IDs
        
        Returns:
            List[str]: List of expired file IDs
        """
        current_time = datetime.now()
        with self.lock:
            return [
                file_id for file_id, info in self.file_registry.items()
                if current_time > info['expires_at']
            ]

    def emergency_cleanup(self, required_bytes: int) -> Tuple[bool, int]:
        """
        Perform emergency cleanup to free up space
        
        Args:
            required_bytes: Number of bytes needed
            
        Returns:
            Tuple[bool, int]: (success status, bytes freed)
        """
        freed_bytes = 0
        
        # First, cleanup all expired files
        expired_files = self.get_expired_files()
        for file_id in expired_files:
            if self.remove_file(file_id):
                freed_bytes += self.file_registry[file_id]['size']
                
        # If still need more space, remove oldest files
        if freed_bytes < required_bytes:
            with self.lock:
                files = sorted(
                    self.file_registry.items(),
                    key=lambda x: x[1]['created_at']
                )
                for file_id, info in files:
                    if self.remove_file(file_id):
                        freed_bytes += info['size']
                    if freed_bytes >= required_bytes:
                        break
                        
        return freed_bytes >= required_bytes, freed_bytes