# task_processor.py

import threading
import queue
import logging
import time
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from common.logging_config import LogConfig

@dataclass
class Task:
    """Task data structure"""
    id: str
    type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    input_path: str
    output_path: str
    ip_address: str
    parameters: Dict[str, Any]
    error: Optional[str] = None
    output_media_type: Optional[str] = None

class TaskProcessor:
    """Manages video processing tasks and their status"""
    
    def __init__(self, video_processor, performance_manager, max_queue_size: int = 100):
        """
        Initialize task processor
        
        Args:
            video_processor: VideoProcessor instance
            performance_manager: PerformanceManager instance
            max_queue_size: Maximum tasks in queue
        """
        self.video_processor = video_processor
        self.performance_manager = performance_manager
        self.task_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.tasks: Dict[str, Task] = {}
        self.active_tasks: Dict[str, str] = {}  # IP -> Task ID mapping
        self.lock = threading.Lock()
        self.shutdown_flag = threading.Event()
        self.logger = LogConfig.get_component_logger("TaskProcessor")
        self._start_worker()

    def _start_worker(self):
        """Start worker thread for processing tasks"""
        def worker():
            while not self.shutdown_flag.is_set():
                try:
                    # Get task with timeout to check shutdown flag periodically
                    priority, task_id = self.task_queue.get(timeout=1.0)
                    task = self.tasks[task_id]
                    
                    # Process task
                    self._process_task(task)
                    
                    # Clean up IP restriction
                    with self.lock:
                        if task.ip_address in self.active_tasks:
                            del self.active_tasks[task.ip_address]
                    
                    self.task_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Worker error: {e}")

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _process_task(self, task: Task):
        """Process a single task"""
        self.logger.info(f"Processing task {task.id} of type {task.type}")
        task.status = 'processing'
        task.started_at = datetime.now()

        try:
            # Check system resources
            can_process, error_msg = self.performance_manager.can_process_new_task()
            if not can_process:
                raise RuntimeError(f"Insufficient resources: {error_msg}")

            # Generate output path with correct extension
            output_ext = self._get_output_extension(task.type)
            task.output_path = os.path.join(
                os.path.dirname(task.output_path),
                f"output_{task.id}.{output_ext}"
            )
            task.output_media_type = output_ext

            # Process based on task type
            success = False
            if task.type == 'compress':
                success = self.video_processor.compress_video(
                    task.input_path, task.output_path
                )
            elif task.type == 'resolution':
                success = self.video_processor.change_resolution(
                    task.input_path, task.output_path,
                    task.parameters['width'],
                    task.parameters['height']
                )
            elif task.type == 'aspect_ratio':
                success = self.video_processor.change_aspect_ratio(
                    task.input_path, task.output_path,
                    task.parameters['aspect_ratio']
                )
            elif task.type == 'extract_audio':
                success = self.video_processor.extract_audio(
                    task.input_path, task.output_path
                )
            elif task.type in ['gif', 'webm']:
                method = (self.video_processor.create_gif 
                         if task.type == 'gif' 
                         else self.video_processor.create_webm)
                success = method(
                    task.input_path, task.output_path,
                    task.parameters['start_time'],
                    task.parameters['duration']
                )
            else:
                raise ValueError(f"Unknown task type: {task.type}")

            if success:
                # Verify file exists and is not empty
                if not os.path.exists(task.output_path):
                    raise RuntimeError("Output file was not created")
                if os.path.getsize(task.output_path) == 0:
                    raise RuntimeError("Output file is empty")
                
                task.status = 'completed'
                self.logger.info(f"Task {task.id} completed successfully")
            else:
                raise RuntimeError("Processing failed")

        except Exception as e:
            task.status = 'failed'
            task.error = str(e)
            self.logger.error(f"Task {task.id} failed: {e}")

        finally:
            task.completed_at = datetime.now()

    def add_task(self, ip_address: str, task_type: str, input_path: str, 
                 output_path: str, parameters: Dict[str, Any] = None) -> Optional[str]:
        """
        Add a new task to the queue
        
        Args:
            ip_address: Client IP address
            task_type: Type of processing task
            input_path: Input file path
            output_path: Output file path
            parameters: Additional parameters for the task
            
        Returns:
            Optional[str]: Task ID if successful, None if failed
        """
        try:
            with self.lock:
                # Check if IP already has an active task
                if ip_address in self.active_tasks:
                    self.logger.warning(f"IP {ip_address} already has an active task")
                    return None

                # Create new task
                task_id = str(uuid.uuid4())
                task = Task(
                    id=task_id,
                    type=task_type,
                    status='queued',
                    created_at=datetime.now(),
                    started_at=None,
                    completed_at=None,
                    input_path=input_path,
                    output_path=output_path,
                    ip_address=ip_address,
                    parameters=parameters or {}
                )

                # Add to tracking collections
                self.tasks[task_id] = task
                self.active_tasks[ip_address] = task_id

                # Add to processing queue with priority based on task type
                priority = self._get_task_priority(task_type)
                self.task_queue.put((priority, task_id))

                self.logger.info(f"Added task {task_id} for IP {ip_address}")
                return task_id

        except Exception as e:
            self.logger.error(f"Error adding task: {e}")
            return None

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a task
        
        Args:
            task_id: Task identifier
            
        Returns:
            Optional[Dict]: Task status information
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            'status': task.status,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'type': task.type,
            'error': task.error
        }

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status
        
        Returns:
            Dict containing queue statistics
        """
        with self.lock:
            return {
                'queue_size': self.task_queue.qsize(),
                'active_tasks': len(self.active_tasks),
                'total_tasks': len(self.tasks)
            }

    def get_active_tasks_by_ip(self) -> Dict[str, List[str]]:
        """
        Get currently active tasks grouped by IP
        
        Returns:
            Dict mapping IP addresses to lists of task IDs
        """
        with self.lock:
            tasks_by_ip = {}
            for ip, task_id in self.active_tasks.items():
                if task_id not in tasks_by_ip:
                    tasks_by_ip[ip] = []
                tasks_by_ip[ip].append(task_id)
            return tasks_by_ip

    def _get_task_priority(self, task_type: str) -> int:
        """
        Get priority level for task type
        Lower number = higher priority
        
        Args:
            task_type: Type of task
            
        Returns:
            int: Priority level
        """
        priorities = {
            'compress': 1,
            'extract_audio': 2,
            'resolution': 3,
            'aspect_ratio': 3,
            'gif': 4,
            'webm': 4
        }
        return priorities.get(task_type, 10)

    def _get_output_extension(self, task_type: str) -> str:
        """
        Get appropriate file extension for task type
        
        Args:
            task_type: Type of task
            
        Returns:
            str: File extension
        """
        extensions = {
            'compress': 'mp4',
            'resolution': 'mp4',
            'aspect_ratio': 'mp4',
            'extract_audio': 'mp3',
            'gif': 'gif',
            'webm': 'webm'
        }
        return extensions.get(task_type, 'mp4')

    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """
        Clean up old completed or failed tasks
        
        Args:
            max_age_hours: Maximum age of completed tasks to keep
        """
        current_time = datetime.now()
        with self.lock:
            task_ids = list(self.tasks.keys())
            for task_id in task_ids:
                task = self.tasks[task_id]
                if task.completed_at:
                    age = current_time - task.completed_at
                    if age.total_seconds() > max_age_hours * 3600:
                        del self.tasks[task_id]

    def shutdown(self):
        """Gracefully shutdown the task processor"""
        self.logger.info("Shutting down task processor...")
        self.shutdown_flag.set()
        if hasattr(self, 'worker_thread'):
            self.worker_thread.join()
        self.logger.info("Task processor shutdown complete")
