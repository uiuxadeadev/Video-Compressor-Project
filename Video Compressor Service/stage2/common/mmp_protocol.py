# mmp_protocol.py
import json
import struct
from typing import Tuple, Dict, Any, Optional
from .logging_config import LogConfig

class MMPProtocol:
    """Multiple Media Protocol (MMP) implementation"""
    
    # Protocol constants
    HEADER_SIZE = 8  # 64 bits = 8 bytes
    JSON_SIZE_BYTES = 2  # 2 bytes for JSON size
    MEDIA_TYPE_SIZE_BYTES = 1  # 1 byte for media type size
    PAYLOAD_SIZE_BYTES = 5  # 5 bytes for payload size
    
    MAX_JSON_SIZE = 65536  # 2 bytes = 64 KB
    MAX_MEDIA_TYPE_SIZE = 255  # 1 byte
    MAX_PAYLOAD_SIZE = 1099511627776  # 5 bytes = 1TB
    
    def __init__(self):
        """Initialize protocol handler with logging"""
        self.logger = LogConfig.get_component_logger("MMPProtocol")

    @staticmethod
    def create_header(json_size: int, media_type_size: int, payload_size: int) -> bytes:
        """
        Create MMP header
        
        Args:
            json_size: Size of JSON data in bytes
            media_type_size: Size of media type string in bytes
            payload_size: Size of payload in bytes
            
        Returns:
            bytes: Packed header
            
        Raises:
            ValueError: If any size exceeds its maximum allowed value
        """
        if json_size > MMPProtocol.MAX_JSON_SIZE:
            raise ValueError(f"JSON size exceeds maximum of {MMPProtocol.MAX_JSON_SIZE} bytes")
            
        if media_type_size > MMPProtocol.MAX_MEDIA_TYPE_SIZE:
            raise ValueError(f"Media type size exceeds maximum of {MMPProtocol.MAX_MEDIA_TYPE_SIZE} bytes")
            
        if payload_size > MMPProtocol.MAX_PAYLOAD_SIZE:
            raise ValueError(f"Payload size exceeds maximum of {MMPProtocol.MAX_PAYLOAD_SIZE} bytes")

        # Pack sizes into header following protocol specification
        # Format: 2 bytes JSON size + 1 byte media type size + 5 bytes payload size
        header = bytearray(MMPProtocol.HEADER_SIZE)
        
        # Pack JSON size (2 bytes)
        header[0:2] = json_size.to_bytes(2, byteorder='big')
        
        # Pack media type size (1 byte)
        header[2] = media_type_size
        
        # Pack payload size (5 bytes)
        header[3:8] = payload_size.to_bytes(5, byteorder='big')
        
        return bytes(header)

    @staticmethod
    def parse_header(header: bytes) -> Tuple[int, int, int]:
        """
        Parse MMP header
        
        Args:
            header: Header bytes to parse
            
        Returns:
            Tuple[int, int, int]: (JSON size, media type size, payload size)
            
        Raises:
            ValueError: If header is invalid
        """
        if len(header) != MMPProtocol.HEADER_SIZE:
            raise ValueError(f"Invalid header size: {len(header)} bytes")

        json_size = int.from_bytes(header[0:2], byteorder='big')
        media_type_size = header[2]
        payload_size = int.from_bytes(header[3:8], byteorder='big')

        return json_size, media_type_size, payload_size

    @staticmethod
    def create_error_response(error_code: int, description: str, solution: str) -> Dict[str, Any]:
        """
        Create standardized error response
        
        Args:
            error_code: Numeric error code
            description: Error description
            solution: Suggested solution
            
        Returns:
            Dict containing error information
        """
        return {
            'error': {
                'code': error_code,
                'description': description,
                'solution': solution
            }
        }

    def send_message(self, sock, json_data: Optional[Dict] = None, 
                    media_type: Optional[str] = None, payload: Optional[bytes] = None) -> bool:
        """
        Send a message following the MMP protocol
        
        Args:
            sock: Socket to send through
            json_data: Optional JSON data to send
            media_type: Optional media type string
            payload: Optional payload bytes
            
        Returns:
            bool: True if send was successful
        """
        try:
            # Convert JSON to bytes if provided
            json_bytes = json.dumps(json_data).encode() if json_data else b''
            json_size = len(json_bytes)

            # Get media type bytes if provided
            media_type_bytes = media_type.encode() if media_type else b''
            media_type_size = len(media_type_bytes)

            # Get payload size
            payload_size = len(payload) if payload else 0

            # Create and send header
            header = self.create_header(json_size, media_type_size, payload_size)
            sock.sendall(header)

            # Send JSON if present
            if json_size > 0:
                sock.sendall(json_bytes)

            # Send media type if present
            if media_type_size > 0:
                sock.sendall(media_type_bytes)

            # Send payload if present
            if payload_size > 0:
                sock.sendall(payload)

            return True

        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return False

    def receive_message(self, sock) -> Tuple[Optional[Dict], Optional[str], Optional[bytes]]:
        """
        Receive a message following the MMP protocol
        
        Args:
            sock: Socket to receive from
            
        Returns:
            Tuple[Optional[Dict], Optional[str], Optional[bytes]]: 
            (JSON data, media type, payload)
        """
        try:
            # Receive and parse header
            header = sock.recv(self.HEADER_SIZE)
            if not header or len(header) != self.HEADER_SIZE:
                raise ConnectionError("Failed to receive complete header")

            json_size, media_type_size, payload_size = self.parse_header(header)

            # Receive JSON if present
            json_data = None
            if json_size > 0:
                json_bytes = sock.recv(json_size)
                if len(json_bytes) != json_size:
                    raise ConnectionError("Failed to receive complete JSON data")
                json_data = json.loads(json_bytes)

            # Receive media type if present
            media_type = None
            if media_type_size > 0:
                media_type_bytes = sock.recv(media_type_size)
                if len(media_type_bytes) != media_type_size:
                    raise ConnectionError("Failed to receive complete media type")
                media_type = media_type_bytes.decode()

            # Receive payload if present
            payload = None
            if payload_size > 0:
                payload = b''
                remaining = payload_size
                while remaining > 0:
                    chunk = sock.recv(min(8192, remaining))
                    if not chunk:
                        raise ConnectionError("Connection lost while receiving payload")
                    payload += chunk
                    remaining -= len(chunk)

            return json_data, media_type, payload

        except Exception as e:
            self.logger.error(f"Error receiving message: {e}")
            return None, None, None

    def send_error(self, sock, error_code: int, description: str, solution: str) -> bool:
        """
        Send an error message
        
        Args:
            sock: Socket to send through
            error_code: Numeric error code
            description: Error description
            solution: Suggested solution
            
        Returns:
            bool: True if send was successful
        """
        error_response = self.create_error_response(error_code, description, solution)
        return self.send_message(sock, json_data=error_response)