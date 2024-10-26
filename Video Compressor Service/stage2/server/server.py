# server.py

import os
import signal
import logging
import socket
import threading
from typing import Dict, Any, Optional
from common.logging_config import LogConfig
import argparse

from common.mmp_protocol import MMPProtocol
from performance_manager import PerformanceManager
from video_processor import VideoProcessor
from task_processor import TaskProcessor
from storage_manager import StorageManager

class VideoProcessingServer:
    """Main video processing server implementation"""
    
    def __init__(self, host: str = 'localhost', port: int = 9999, work_dir: str = 'work'):
        """
        Initialize server with all components
        
        Args:
            host: Server host address
            port: Server port number
            work_dir: Working directory for temporary files
        """
        self.host = host
        self.port = port
        self.work_dir = work_dir
        self.running = False
        self.server_socket = None
        
        # Ensure work directory exists
        os.makedirs(work_dir, exist_ok=True)
        
        # Initialize components
        self.logger = LogConfig.get_component_logger("VideoServer")
        self.setup_components()
        self.setup_signal_handlers()

    def setup_components(self):
        """Initialize all server components"""
        try:
            # Initialize core components
            self.protocol = MMPProtocol()
            self.performance_manager = PerformanceManager(self.work_dir)
            self.storage_manager = StorageManager(self.work_dir)
            self.video_processor = VideoProcessor(self.work_dir)
            self.task_processor = TaskProcessor(
                self.video_processor,
                self.performance_manager
            )
            
            # Verify system requirements
            self._verify_system_requirements()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize server components: {e}")
            raise

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def _verify_system_requirements(self):
        """Verify system meets all requirements"""
        # Check performance requirements
        ok, msg = self.performance_manager.check_system_resources()
        if not ok:
            raise RuntimeError(f"System does not meet performance requirements: {msg}")
            
        # Check storage requirements
        space_ok, space_msg = self.storage_manager.check_storage_available(1024**3)  # Test with 1GB
        if not space_ok:
            raise RuntimeError(f"Storage system check failed: {space_msg}")
            
        # Check FFmpeg installation
        try:
            self.video_processor._verify_ffmpeg()
        except RuntimeError as e:
            raise RuntimeError(f"FFmpeg check failed: {e}")

    def start(self):
        """Start the server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            self.logger.info(f"Server started on {self.host}:{self.port}")
            print(f"Server is running on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    self.logger.info(f"New connection from {address}")
                    
                    # Start client handler in new thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address[0])
                    )
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        self.logger.error(f"Socket error: {e}")
                        
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            self.shutdown()

    def handle_client(self, client_socket: socket.socket, client_ip: str):
        """
        Handle client connection
        
        Args:
            client_socket: Client socket
            client_ip: Client IP address
        """
        try:
            # Receive request using MMP protocol
            json_data, media_type, payload = self.protocol.receive_message(client_socket)
            
            if not json_data:
                self.logger.error("Failed to receive request")
                self._send_error(client_socket, "Invalid request")
                return
                
            # Process request based on action
            if json_data.get('action') == 'upload':
                self._handle_upload(client_socket, json_data, media_type, payload, client_ip)
            elif json_data.get('action') == 'status':
                self._handle_status(client_socket, json_data)
            elif json_data.get('action') == 'download':
                self._handle_download(client_socket, json_data)
            else:
                self._send_error(client_socket, "Unknown action")
                
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
            self._send_error(client_socket, str(e))
            
        finally:
            client_socket.close()

    def _handle_upload(self, client_socket: socket.socket, request: Dict[str, Any],
                      media_type: str, payload: bytes, client_ip: str):
        """Handle file upload and processing request"""
        try:
            # Verify storage availability
            if not payload:
                raise ValueError("No file data received")
                
            storage_ok, msg = self.storage_manager.check_storage_available(len(payload))
            if not storage_ok:
                raise ValueError(f"Storage check failed: {msg}")
                
            # Save input file
            input_path = os.path.join(self.work_dir, f"input_{media_type}")
            with open(input_path, 'wb') as f:
                f.write(payload)
                
            # Register file with storage manager
            file_id = self.storage_manager.register_file(input_path, "temp")
            if not file_id:
                raise RuntimeError("Failed to register input file")
                
            # Create output path
            output_ext = self._get_output_extension(request['type'])
            output_path = os.path.join(self.work_dir, f"output_{output_ext}")
            
            # Add task to processor
            task_id = self.task_processor.add_task(
                client_ip,
                request['type'],
                input_path,
                output_path,
                request.get('parameters', {})
            )
            
            if not task_id:
                raise RuntimeError("Failed to create processing task")
                
            # Send success response
            response = {
                'status': 'accepted',
                'task_id': task_id,
                'message': 'File uploaded and processing started'
            }
            self.protocol.send_message(client_socket, json_data=response)
            
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            self._send_error(client_socket, str(e))
            # Cleanup any created files
            if 'input_path' in locals():
                self.storage_manager.remove_file(file_id)

    def _handle_status(self, client_socket: socket.socket, request: Dict[str, Any]):
        """Handle task status request"""
        task_id = request.get('task_id')
        if not task_id:
            self._send_error(client_socket, "Task ID required")
            return
            
        status = self.task_processor.get_task_status(task_id)
        if not status:
            self._send_error(client_socket, "Task not found")
            return
            
        self.protocol.send_message(client_socket, json_data=status)

    def _handle_download(self, client_socket: socket.socket, request: Dict[str, Any]):
        """Handle processed file download request"""
        task_id = request.get('task_id')
        if not task_id:
            self._send_error(client_socket, "Task ID required")
            return
            
        task_status = self.task_processor.get_task_status(task_id)
        if not task_status or task_status['status'] != 'completed':
            self._send_error(client_socket, "Task not completed or not found")
            return
            
        try:
            # Get task and verify output file
            task = self.task_processor.tasks[task_id]
            if not task.output_path or not os.path.exists(task.output_path):
                raise FileNotFoundError(f"Output file not found: {task.output_path}")
                
            # Verify file is not empty
            if os.path.getsize(task.output_path) == 0:
                raise ValueError("Output file is empty")

            # Read file data
            with open(task.output_path, 'rb') as f:
                file_data = f.read()
                
            # Get media type from task
            media_type = task.output_media_type or os.path.splitext(task.output_path)[1][1:]
            
            # Send file
            self.protocol.send_message(
                client_socket,
                media_type=media_type,
                payload=file_data
            )
            
            # Log success
            self.logger.info(f"Successfully sent output file for task {task_id}")
            
            # Clean up task files
            try:
                self.storage_manager.cleanup_task_files(task_id)
            except Exception as e:
                self.logger.warning(f"Error cleaning up task files: {e}")
            
        except Exception as e:
            error_msg = f"Download error: {str(e)}"
            self.logger.error(error_msg)
            self._send_error(client_socket, str(e))

    def _send_error(self, client_socket: socket.socket, error_message: str):
        """Send error response to client"""
        self.protocol.send_error(
            client_socket,
            1,
            error_message,
            "Please check your request and try again"
        )

    def _get_output_extension(self, task_type: str) -> str:
        """Get appropriate file extension for task type"""
        extensions = {
            'compress': 'mp4',
            'resolution': 'mp4',
            'aspect_ratio': 'mp4',
            'extract_audio': 'mp3',
            'gif': 'gif',
            'webm': 'webm'
        }
        return extensions.get(task_type, 'mp4')

    def shutdown(self, signum=None, frame=None):
        """Gracefully shutdown the server"""
        if not self.running:
            return
            
        self.logger.info("Shutting down server...")
        print("\nServer shutdown initiated...")
        
        self.running = False
        
        # Stop task processor
        if hasattr(self, 'task_processor'):
            self.task_processor.shutdown()
            
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
            
        # Final cleanup
        if hasattr(self, 'storage_manager'):
            self.storage_manager.cleanup_expired_files()
            
        self.logger.info("Server shutdown complete")
        print("Server shutdown complete")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Video Processing Server')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=9999, help='Server port')
    parser.add_argument('--work-dir', default='work', help='Working directory')
    
    args = parser.parse_args()
    
    try:
        server = VideoProcessingServer(args.host, args.port, args.work_dir)
        server.start()
    except Exception as e:
        print(f"Failed to start server: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())