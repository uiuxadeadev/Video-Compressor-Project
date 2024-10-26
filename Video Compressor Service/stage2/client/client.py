# client.py

import os
import time
import logging
import socket
import argparse
from typing import Dict, Any, Optional, Tuple
from common.logging_config import LogConfig
from common.mmp_protocol import MMPProtocol

class VideoProcessingClient:
    """Client for video processing service"""
    
    def __init__(self, host: str = 'localhost', port: int = 9999):
        """
        Initialize client
        
        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.protocol = MMPProtocol()
        self.logger = LogConfig.get_component_logger("VideoClient")

    def _connect(self) -> socket.socket:
        """Create connection to server"""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.host, self.port))
            return client_socket
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            raise

    def upload_and_process(self, filepath: str, task_type: str, 
                          parameters: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Upload file and request processing
        
        Args:
            filepath: Path to input file
            task_type: Type of processing to perform
            parameters: Additional parameters for processing
            
        Returns:
            Optional[str]: Task ID if successful
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
            
        try:
            # Prepare request
            request = {
                'action': 'upload',
                'type': task_type,
                'parameters': parameters or {}
            }
            
            # Read file
            with open(filepath, 'rb') as f:
                file_data = f.read()
                
            # Get media type
            media_type = os.path.splitext(filepath)[1][1:]
            
            # Connect and send request
            client_socket = self._connect()
            
            try:
                # Send request
                self.protocol.send_message(
                    client_socket,
                    json_data=request,
                    media_type=media_type,
                    payload=file_data
                )
                
                # Get response
                response, _, _ = self.protocol.receive_message(client_socket)
                
                if response and response.get('status') == 'accepted':
                    self.logger.info(f"Upload successful. Task ID: {response['task_id']}")
                    return response['task_id']
                else:
                    error_msg = response.get('error', 'Unknown error') if response else 'No response'
                    self.logger.error(f"Upload failed: {error_msg}")
                    return None
                    
            finally:
                client_socket.close()
                
        except Exception as e:
            self.logger.error(f"Error in upload_and_process: {e}")
            raise

    def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check status of processing task
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict containing task status
        """
        try:
            client_socket = self._connect()
            
            try:
                # Send status request
                request = {
                    'action': 'status',
                    'task_id': task_id
                }
                self.protocol.send_message(client_socket, json_data=request)
                
                # Get response
                response, _, _ = self.protocol.receive_message(client_socket)
                
                if not response:
                    raise RuntimeError("No response from server")
                    
                return response
                
            finally:
                client_socket.close()
                
        except Exception as e:
            self.logger.error(f"Error checking status: {e}")
            raise

    def download_result(self, task_id: str, output_path: str) -> bool:
        """
        Download processed file
        
        Args:
            task_id: Task identifier
            output_path: Path to save output file
            
        Returns:
            bool: Success status
        """
        try:
            client_socket = self._connect()
            
            try:
                # Send download request
                request = {
                    'action': 'download',
                    'task_id': task_id
                }
                self.protocol.send_message(client_socket, json_data=request)
                
                # Get response
                json_data, media_type, payload = self.protocol.receive_message(client_socket)
                
                if not payload:
                    if json_data and 'error' in json_data:
                        self.logger.error(f"Server returned an error: {json_data['error']}")
                        raise RuntimeError(json_data['error'])
                    raise RuntimeError("No data received")
                    
                # Update output path with correct extension if needed
                if media_type:
                    base, _ = os.path.splitext(output_path)
                    output_path = f"{base}.{media_type}"
                    
                # Save file
                with open(output_path, 'wb') as f:
                    f.write(payload)
                    
                self.logger.info(f"File downloaded successfully to {output_path}")
                return True
                
            finally:
                client_socket.close()
                
        except Exception as e:
            self.logger.error(f"Error downloading result: {e}")
            raise

    def process_and_wait(self, filepath: str, task_type: str,
                        parameters: Optional[Dict[str, Any]] = None,
                        output_path: Optional[str] = None,
                        check_interval: int = 60,
                        max_wait_time: int = 3600) -> bool:
        """
        Upload, process, and download result with status checking
        
        Args:
            filepath: Input file path
            task_type: Type of processing
            parameters: Processing parameters
            output_path: Output file path
            check_interval: Status check interval in seconds
            max_wait_time: Maximum wait time in seconds
            
        Returns:
            bool: Success status
        """
        try:
            # Upload and start processing
            task_id = self.upload_and_process(filepath, task_type, parameters)
            if not task_id:
                return False
                
            print(f"Processing started. Task ID: {task_id}")
            
            # Generate default output path if not provided
            if not output_path:
                base, ext = os.path.splitext(filepath)
                output_path = f"{base}_processed{ext}"
                
            # Wait for processing to complete
            start_time = time.time()
            while True:
                if time.time() - start_time > max_wait_time:
                    print("Maximum wait time exceeded")
                    return False
                    
                status = self.check_status(task_id)
                print(f"Status: {status['status']}")
                
                if status['status'] == 'completed':
                    break
                elif status['status'] == 'failed':
                    error_msg = status.get('error', 'Unknown error')
                    print(f"Processing failed: {error_msg}")
                    return False
                    
                time.sleep(check_interval)
                
            # Download result
            print("Processing completed. Downloading result...")
            return self.download_result(task_id, output_path)
            
        except Exception as e:
            print(f"Error: {e}")
            return False

def main():
    """
    Video Processing Client Command Line Interface

    Basic Usage:
        python3 client.py <input_file> --type <process_type> [options]

    Process Types and Required Options:
    1. Compress Video:
        python3 client.py video.mp4 --type compress
        Optional: --output compressed.mp4

    2. Change Resolution (requires width and height):
        python3 client.py video.mp4 --type resolution --width 1280 --height 720
        Example: Convert to 720p:
            python3 client.py video.mp4 --type resolution --width 1280 --height 720
        Example: Convert to 480p:
            python3 client.py video.mp4 --type resolution --width 854 --height 480

    3. Change Aspect Ratio (requires aspect-ratio):
        python3 client.py video.mp4 --type aspect_ratio --aspect-ratio "16:9"
        Example: Convert to 16:9:
            python3 client.py video.mp4 --type aspect_ratio --aspect-ratio "16:9"
        Example: Convert to 4:3:
            python3 client.py video.mp4 --type aspect_ratio --aspect-ratio "4:3"

    4. Extract Audio:
        python3 client.py video.mp4 --type extract_audio
        Optional: --output audio.mp3

    5. Create GIF (requires start-time and duration):
        python3 client.py video.mp4 --type gif --start-time 0 --duration 5
        Example: Convert first 5 seconds:
            python3 client.py video.mp4 --type gif --start-time 0 --duration 5
        Example: Convert 10-13 seconds:
            python3 client.py video.mp4 --type gif --start-time 10 --duration 3

    6. Create WebM (requires start-time and duration):
        python3 client.py video.mp4 --type webm --start-time 0 --duration 10
        Example: Convert first 10 seconds:
            python3 client.py video.mp4 --type webm --start-time 0 --duration 10
        Example: Convert specific segment:
            python3 client.py video.mp4 --type webm --start-time 30 --duration 5

    Additional Options:
        --output           : Specify output file path (default: auto-generated)
        --host            : Server hostname (default: localhost)
        --port            : Server port number (default: 9999)
        --check-interval  : Progress check interval in seconds (default: 60)
        --max-wait-time   : Maximum wait time in seconds (default: 3600)

    Examples:
        Basic compression:
            python3 client.py video.mp4 --type compress

        720p conversion with custom output:
            python3 client.py video.mp4 --type resolution --width 1280 --height 720 --output hd_video.mp4

        Extract audio to MP3:
            python3 client.py video.mp4 --type extract_audio --output soundtrack.mp3

        Create GIF with custom interval:
            python3 client.py video.mp4 --type gif --start-time 5 --duration 3 --check-interval 10

    Error Troubleshooting:
        - For resolution change: Both --width and --height are required
        - For GIF/WebM: Both --start-time and --duration are required
        - For aspect ratio: Use quotes around ratio (e.g., "16:9")
    """
    parser = argparse.ArgumentParser(
        description='Video Processing Client',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=main.__doc__
    )
    
    parser.add_argument('file', help='Input video file')
    parser.add_argument('--type', required=True,
                       choices=['compress', 'resolution', 'aspect_ratio',
                              'extract_audio', 'gif', 'webm'],
                       help='Type of processing')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--host', default='localhost',
                       help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=9999,
                       help='Server port (default: 9999)')
    
    # Task-specific parameters
    parser.add_argument('--width', type=int,
                       help='Output width for resolution change')
    parser.add_argument('--height', type=int,
                       help='Output height for resolution change')
    parser.add_argument('--aspect-ratio',
                       help='Target aspect ratio (e.g., "16:9")')
    parser.add_argument('--start-time', type=float,
                       help='Start time in seconds for GIF/WebM')
    parser.add_argument('--duration', type=float,
                       help='Duration in seconds for GIF/WebM')
    parser.add_argument('--check-interval', type=int, default=60,
                       help='Status check interval in seconds (default: 60)')
    parser.add_argument('--max-wait-time', type=int, default=3600,
                       help='Maximum wait time in seconds (default: 3600)')
    
    args = parser.parse_args()
    
    # Parameter validation with helpful error messages
    parameters = {}
    if args.type == 'resolution':
        if not args.width or not args.height:
            parser.error(
                "Resolution change requires both --width and --height arguments.\n"
                "Example: --width 1280 --height 720 for 720p"
            )
        parameters = {'width': args.width, 'height': args.height}
    elif args.type == 'aspect_ratio':
        if not args.aspect_ratio:
            parser.error(
                "Aspect ratio change requires --aspect-ratio argument.\n"
                'Example: --aspect-ratio "16:9"'
            )
        parameters = {'aspect_ratio': args.aspect_ratio}
    elif args.type in ['gif', 'webm']:
        if not (args.start_time is not None and args.duration):
            parser.error(
                f"{args.type.upper()} creation requires both --start-time and --duration arguments.\n"
                "Example: --start-time 0 --duration 5"
            )
        parameters = {
            'start_time': args.start_time,
            'duration': args.duration
        }
    
    # Process video
    print(f"Processing {args.file} with type: {args.type}")
    if parameters:
        print(f"Parameters: {parameters}")
    
    client = VideoProcessingClient(args.host, args.port)
    success = client.process_and_wait(
        args.file,
        args.type,
        parameters,
        args.output,
        args.check_interval,
        args.max_wait_time
    )
    
    if success:
        print("\nProcessing completed successfully!")
    else:
        print("\nProcessing failed. Check the error messages above.")
    
    exit(0 if success else 1)

if __name__ == '__main__':
    main()