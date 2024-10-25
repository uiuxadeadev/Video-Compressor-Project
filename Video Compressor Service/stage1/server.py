import socket
import os
import sys
import daemon
from daemon import pidfile  # Add this separate import
import signal
import logging
import io
import threading
import psutil
from logging.handlers import RotatingFileHandler
from datetime import datetime
from queue import Queue, Empty
from threading import Event
from performance_check import FilesystemPerformanceChecker

class BufferedFileWriter:
    def __init__(self, filename, buffer_size=1024*1024):  # 1MB buffer
        """Initialize the BufferedFileWriter with a filename and buffer size.

        Args:
            filename (str): The name of the file to write to.
            buffer_size (int): The size of the buffer (default is 1MB).
        """
        self.filename = filename  # Save the name of the file to write to
        self.buffer_size = buffer_size  # Store the size of the buffer
        self.buffer = io.BytesIO()  # Buffer to temporarily hold data to be written
        self.total_written = 0  # Variable to count the number of bytes written
        # Open the file in binary write mode, specifying the buffer size.
        self.file = open(filename, 'wb', buffering=buffer_size)

    def write(self, data):
        """Write data to the file and update the total written byte count.

        Args:
            data (bytes): The data to write to the file.
        """
        self.file.write(data)  # Write the data to the file
        self.total_written += len(data)  # Increment the count of bytes written

    def close(self):
        """Flush and close the file, ensuring data is written to disk."""
        self.file.flush()  # Write buffered data to disk
        os.fsync(self.file.fileno())  # Ensure the data is physically written to disk
        self.file.close()  # Close the file

class PacketProcessor:
    def __init__(self, max_packets_per_second=20000):
        """Initialize with a packet processing rate and create a queue and event."""
        self.max_packets_per_second = max_packets_per_second  # Maximum number of packets to process per second
        self.packet_queue = Queue(maxsize=max_packets_per_second)  # Queue to hold packets for processing
        self.stop_event = Event()  # Event to signal when to stop processing
        self.processor_thread = None  # Thread for processing packets

    def start(self):
        """Start a thread to process packets from the queue."""
        self.processor_thread = threading.Thread(target=self._process_packets)  # Create a thread for packet processing
        self.processor_thread.start()  # Start the processing thread

    def stop(self):
        """Stop the packet processing thread."""
        self.stop_event.set()  # Signal the thread to stop processing
        if self.processor_thread:
            self.processor_thread.join()  # Wait for the thread to finish

    def _process_packets(self):
        """Continuously process packets from the queue unless stopped."""
        while not self.stop_event.is_set():  # Continue processing until the stop event is set
            try:
                packet, writer = self.packet_queue.get(timeout=0.1)  # Get a packet from the queue with a timeout
                writer.write(packet)  # Write the packet using the writer
                self.packet_queue.task_done()  # Mark the task as done
            except Empty:
                continue  # If the queue is empty, continue the loop

    def process_packet(self, packet, writer):
        """Attempt to add a packet to the queue for processing."""
        try:
            self.packet_queue.put((packet, writer), timeout=0.001)  # 1ms timeout to add packet to the queue
            return True  # Successfully added the packet to the queue
        except Empty:
            return False  # Failed to add the packet due to queue being full

class VideoUploadServer:
    def __init__(self, host='localhost', port=9999):
        """Initialize the server with storage limits, buffer size, and logging setup"""
        self.host = host
        self.port = port
        self.max_storage = 4 * 1024**4  # 4TB
        self.max_file_size = 4 * 1024**3  # 4GB
        self.packet_size = 1400
        self.upload_dir = 'uploads'
        self.pid_file = '/tmp/video_upload_server.pid'
        self.running = True
        self.server_socket = None
        
        self.packet_processor = PacketProcessor(max_packets_per_second=20000)
        self.io_buffer_size = self.packet_size * 20000  # Approx. 28MB

        self.setup_logging()
        
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

        # Initialize and run performance checker
        self.perf_checker = FilesystemPerformanceChecker(
            upload_dir=self.upload_dir,
            packet_size=self.packet_size,
            target_packets_per_sec=20000,
            buffer_size=self.io_buffer_size
        )
        
        packets_per_sec, meets_requirement = self.perf_checker.run_performance_test()
        if not meets_requirement:
            self.logger.warning("System may not meet performance requirements")

    def setup_logging(self):
        """Configure logging for the server"""
        self.logger = logging.getLogger('VideoUploadServer')
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler('server.log', maxBytes=1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def get_total_storage_used(self):
        """Calculate the current used storage in the upload directory"""
        total = 0
        for filename in os.listdir(self.upload_dir):
            filepath = os.path.join(self.upload_dir, filename)
            if os.path.isfile(filepath):
                total += os.path.getsize(filepath)
        return total

    def shutdown(self, signum=None, frame=None):
        """Gracefully shut down the server and clean up resources"""
        self.logger.info("Shutting down server...")
        print("\nServer shutdown initiated. Cleaning up...")
        
        self.running = False
        if self.packet_processor:
            self.packet_processor.stop()
            print("Packet processor stopped")
        
        if self.server_socket:
            self.server_socket.close()
            print("Server socket closed")
        
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
            print("PID file removed")
            
        self.logger.info("Server shutdown complete")
        print("Server shutdown complete. Goodbye!")

    def start(self):
        """Set up signal handlers and start the server socket"""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
        self.packet_processor.start()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.io_buffer_size)
        
        self.logger.info(f"Server started on {self.host}:{self.port}")
        print(f"Server is running on {self.host}:{self.port}")

        try:
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    self.logger.info(f"Connection from {address}")
                    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.io_buffer_size)
                    
                    try:
                        self.handle_client(client_socket)
                    except Exception as e:
                        self.logger.error(f"Error handling client: {e}")
                    finally:
                        client_socket.close()
                except socket.error:
                    if self.running:
                        self.logger.error("Socket error occurred")
        finally:
            if self.running:
                self.shutdown()

    def handle_client(self, client_socket):
        """Handle a single client upload, managing file storage and packet processing"""
        
        # Phase 1: Client Upload Processing
        file_writer = None
        filepath = None
        
        try:
            # Receive the file size in 32 bytes from the client and convert it to an integer
            file_size_bytes = client_socket.recv(32)
            file_size = int(file_size_bytes.decode().strip())
            
            # Check if the file size exceeds the server's maximum allowable size
            if file_size > self.max_file_size:
                self._send_response(client_socket, "File too large")  # If too large, send an error message
                return
            
            # Check if adding this file will exceed the server's maximum storage capacity
            if self.get_total_storage_used() + file_size > self.max_storage:
                self._send_response(client_socket, "Storage full")  # If storage is insufficient, send an error message
                return

            # Verify if there is enough disk space available; if not, send an error message
            if not self.perf_checker.check_disk_space(file_size):
                self._send_response(client_socket, "Insufficient space")
                return

            # Phase 2: File Saving
            # Generate a unique file name using the current timestamp and set the file path for saving
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}.mp4"
            filepath = os.path.join(self.upload_dir, filename)
            
            # Create a BufferedFileWriter object to write the file, and initialize a variable to track data received
            file_writer = BufferedFileWriter(filepath, self.io_buffer_size)
            received = 0  # Tracks the bytes received from the client

            # Loop until the total file size is received
            while received < file_size:
                # Calculate the size of data to receive: use either the packet size or remaining file size, whichever is smaller
                remaining = min(self.packet_size, file_size - received)
                chunk = client_socket.recv(remaining)  # Receive data
                
                # If receiving fails, terminate the process with an error
                if not chunk:
                    raise ConnectionError("Connection lost during transfer")
                
                # Process the received data as a packet. Raise an error if processing fails
                if not self.packet_processor.process_packet(chunk, file_writer):
                    raise IOError("Failed to process packet in time")
                
                received += len(chunk)  # Update the count of bytes received

            # Wait until packet processing is complete and then close the file
            self.packet_processor.packet_queue.join()
            file_writer.close()
            
            # Phase 3: Upload Completion Verification
            # Verify if the saved file size matches the specified size
            actual_size = os.path.getsize(filepath)
            if actual_size != file_size:
                raise ValueError(f"Size mismatch: expected {file_size}, got {actual_size}")
            
            # Send a success message to the client and log the successful upload
            self._send_response(client_socket, "Upload success")
            self.logger.info(f"File saved: {filename} ({actual_size} bytes)")

        except Exception as e:
            # If an error occurs, send an error message to the client and delete the file
            self.logger.error(f"Upload failed: {e}")
            self._send_response(client_socket, "Upload failed")
            if file_writer:
                file_writer.close()
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)  # Delete incomplete file on error
                
    def _send_response(self, client_socket, message):
        """Send a 16-byte response message to the client"""
        response = message.ljust(16).encode()
        client_socket.send(response)

def stop_server():
    """Stop the running server process"""
    pid_file = '/tmp/video_upload_server.pid'

    # ロガーの設定
    logger = logging.getLogger('VideoUploadServer')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler('server.log', maxBytes=1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if not os.path.exists(pid_file):
        print("Server is not running")
        logger.info("Server is not running or already stopped")
        return

    try:
        # PIDファイルの読み取りと検証
        with open(pid_file, 'r') as f:
            pid_str = f.read().strip()

        if not pid_str:
            print("Invalid PID file (empty). Cleaning up...")
            logger.warning("PID file is empty. Removing invalid PID file.")
            os.remove(pid_file)
            return

        try:
            pid = int(pid_str)
        except ValueError:
            print(f"Invalid PID format: '{pid_str}'. Cleaning up...")
            logger.warning(f"PID file contains invalid data: '{pid_str}'. Removing PID file.")
            os.remove(pid_file)
            return

        # プロセスの存在確認
        if not psutil.pid_exists(pid):
            print("Server process not found. Cleaning up PID file...")
            logger.info("Server process not found. Removing outdated PID file.")
            os.remove(pid_file)
            return

        # プロセスの終了
        try:
            process = psutil.Process(pid)

            if "python" not in process.name().lower():
                print(f"Process {pid} exists but is not a Python process. Cleaning up...")
                logger.warning(f"Process {pid} is not a Python process. Removing PID file.")
                os.remove(pid_file)
                return

            print(f"Shutting down server process (PID: {pid})...")
            logger.info(f"Shutting down server process (PID: {pid})...")
            process.terminate()

            try:
                process.wait(timeout=5)
                print("Server shutdown complete.")
                logger.info("Server shutdown completed successfully.")
            except psutil.TimeoutExpired:
                print("Server did not respond to termination signal. Forcing shutdown...")
                process.kill()
                print("Server forcefully stopped.")
                logger.warning("Server did not respond to termination signal. Forced shutdown executed.")

        except psutil.NoSuchProcess:
            print("Process terminated before we could stop it. Cleaning up...")
            logger.info("Process terminated unexpectedly before stopping. Cleaning up PID file.")

    except Exception as e:
        print(f"Error stopping server: {e}")
        logger.error(f"Error stopping server: {e}")
        print("Cleaning up PID file...")

    finally:
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                print("PID file removed.")
                logger.info("PID file removed after stopping server.")
        except Exception as e:
            print(f"Error removing PID file: {e}")
            logger.error(f"Error removing PID file: {e}")


def run_server():
    """Run the server as a daemon process"""
    pid_file = '/tmp/video_upload_server.pid'
    
    # Check if server is already running
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid_str = f.read().strip()
                
            if pid_str and psutil.pid_exists(int(pid_str)):
                print("Server is already running")
                sys.exit(1)
            else:
                os.remove(pid_file)
        except (ValueError, OSError):
            os.remove(pid_file)

    # Create proper pidfile instance
    pid = pidfile.TimeoutPIDLockFile(pid_file)
    
    # Create daemon context with the correct pidfile configuration
    context = daemon.DaemonContext(
        working_directory='.',
        umask=0o002,
        pidfile=pid,
        files_preserve=[sys.stdout, sys.stderr]  # Preserve file descriptors for logging
    )

    # Start server in daemon context
    with context:
        server = VideoUploadServer()
        server.start()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '--foreground':
            server = VideoUploadServer()
            server.start()
        elif sys.argv[1] == '--stop':
            stop_server()
        else:
            print("Unknown option. Use --foreground to run in foreground or --stop to stop the server")
    else:
        run_server()