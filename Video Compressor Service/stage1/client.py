# client.py
import socket
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

class VideoUploadClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.packet_size = 1400
        self.io_buffer_size = self.packet_size * 1000
        self.max_file_size = 4 * 1024**3  # 4GB limit
        self.setup_logging()

    def setup_logging(self):
        """Set up logging configuration"""
        self.logger = logging.getLogger('VideoUploadClient')
        self.logger.setLevel(logging.INFO)
        
        # ログファイルが既に存在する場合は既存のハンドラを削除
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        handler = RotatingFileHandler('client.log', maxBytes=1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def validate_file(self, filepath: str) -> int:
        """
        Validate file before upload
        
        Args:
            filepath: Path to the file to be uploaded
            
        Returns:
            int: Size of the file in bytes
            
        Raises:
            ValueError: If file validation fails
        """
        if not os.path.exists(filepath):
            raise ValueError(f"File not found: {filepath}")
        
        if not filepath.lower().endswith('.mp4'):
            raise ValueError("Only MP4 files are supported")
        
        file_size = os.path.getsize(filepath)
        if file_size > self.max_file_size:
            raise ValueError(f"File size exceeds {self.max_file_size / (1024**3)}GB limit")
        
        if file_size == 0:
            raise ValueError("File is empty")
        
        return file_size

    def calculate_checksum(self, data: bytes) -> int:
        """
        Simple checksum calculation for data verification
        
        Args:
            data: Bytes to calculate checksum for
            
        Returns:
            int: Calculated checksum
        """
        return sum(data) & 0xFFFFFFFF

    def _handle_server_response(self, response: str) -> None:
        """
        Handle server response and log appropriate messages
        
        Args:
            response: Response received from server
        """
        if response == "Upload success":
            self.logger.info("Upload completed successfully")
            print("\nUpload completed successfully!")
        else:
            error_messages = {
                "File too large": "File exceeds server's size limit",
                "Storage full": "Server storage is full",
                "Insufficient space": "Server has insufficient disk space",
                "Upload failed": "Upload failed on server side"
            }
            error_msg = error_messages.get(response, f"Unknown error: {response}")
            self.logger.error(f"Upload failed: {error_msg}")
            print(f"\nError: {error_msg}")

    def upload_file(self, filepath: str) -> bool:
        """
        Upload a file to the server
        
        Args:
            filepath: Path to the file to be uploaded
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        client_socket: Optional[socket.socket] = None
        try:
            # Validate file
            file_size = self.validate_file(filepath)
            self.logger.info(f"Starting upload of {filepath} ({file_size} bytes)")

            # Connect to server
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.host, self.port))
            self.logger.info(f"Connected to server at {self.host}:{self.port}")

            # Set socket buffer size for optimal performance
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.io_buffer_size)

            # Send file size (exactly 32 bytes)
            size_message = str(file_size).ljust(32).encode()
            client_socket.send(size_message)

            # Send file data
            sent = 0
            with open(filepath, 'rb') as f:
                while sent < file_size:
                    chunk = f.read(self.packet_size)
                    if not chunk:
                        break
                        
                    checksum = self.calculate_checksum(chunk)
                    client_socket.send(chunk)
                    sent += len(chunk)
                    
                    # Progress indication
                    progress = (sent / file_size) * 100
                    print(f"\rUploading: {progress:.1f}% ({sent}/{file_size} bytes)", end='', flush=True)

            print("\nWaiting for server response...")
            response = client_socket.recv(16).decode().strip()
            
            self._handle_server_response(response)
            return response == "Upload success"

        except ConnectionRefusedError:
            print("\nError: Could not connect to server. Please make sure the server is running.")
            self.logger.error("Connection to server refused")
            return False
            
        except Exception as e:
            print(f"\nError during upload: {e}")
            self.logger.error(f"Upload error: {e}")
            return False
            
        finally:
            if client_socket:
                client_socket.close()

def print_usage():
    print("Usage: python client.py <filepath>")
    print("Example: python client.py /path/to/video.mp4")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)

    filepath = sys.argv[1]
    client = VideoUploadClient()
    success = client.upload_file(filepath)
    sys.exit(0 if success else 1)