import socket
import threading
import asyncio
import signal
import sys

# Constants for buffer size and port numbers
BUFFER_SIZE = 4096
SERVER_TCP_PORT = 9001
SERVER_UDP_PORT = 9002
shutdown_event = threading.Event()  # Event for signaling shutdown across threads

def create_udp_socket():
    """Create and configure a UDP socket with proper options."""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of the address
    try:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # Allow reuse of the port (if supported)
    except AttributeError:
        pass  # Ignore if the platform does not support SO_REUSEPORT
    return udp_sock

def tcp_connect(server_address, room_name, operation):
    """Create or join a chat room via TCP.

    Args:
        server_address (str): The address of the server to connect to.
        room_name (str): The name of the chat room to create or join.
        operation (int): The operation code (1 for create, 2 for join).

    Returns:
        tuple: A token for the user and the local port number if successful, else (None, None).
    """
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP socket
    tcp_sock.settimeout(5)  # Set a timeout for the connection attempt
    
    try:
        # Attempt to connect to the server at the specified address and port
        tcp_sock.connect((server_address, SERVER_TCP_PORT))
        print(f"Connected to server at {server_address}:{SERVER_TCP_PORT}")
    except socket.timeout:
        print("Connection timed out.")
        return None, None  # Return None if connection fails
    except socket.error as e:
        print(f"Error connecting to server: {e}")
        return None, None
    
    try:
        # Prepare the packet to send to the server
        room_name_bytes = room_name.encode('utf-8')  # Encode room name to bytes
        room_name_size = len(room_name_bytes)  # Get the size of the room name
        # Create a packet with room name size, operation code, a placeholder byte, and the room name
        packet = bytes([room_name_size]) + bytes([operation]) + bytes([0]) + room_name_bytes
        tcp_sock.sendall(packet)  # Send the packet to the server
        
        response = tcp_sock.recv(BUFFER_SIZE)  # Receive the server's response
        response_str = response.decode('utf-8')  # Decode response to string
        print(response_str)  # Print the server response
        
        # Check if the response indicates success
        if "Room created" in response_str or "Joined room" in response_str:
            token = response_str.split()[-1].encode('utf-8')  # Extract the token from the response
            return token, tcp_sock.getsockname()[1]  # Return token and local port number
        
        return None, None  # Return None if room creation/joining fails
    finally:
        tcp_sock.close()  # Ensure the TCP socket is closed

async def udp_chat(server_address, token, room_name, local_port):
    """Send and receive messages via UDP.

    Args:
        server_address (str): The address of the server.
        token (bytes): The user's token for identification.
        room_name (str): The name of the chat room.
        local_port (int): The local port to bind the UDP socket to.
    """
    udp_sock = create_udp_socket()  # Create a UDP socket
    
    try:
        # Bind the UDP socket to the specified local port
        udp_sock.bind(('', local_port))  # Bind to the provided local port
        print(f"UDP bound to port {local_port}")
    except OSError as e:
        print(f"Could not bind to port {local_port}, using any available port")
        udp_sock.bind(('', 0))  # Bind to any available port if the specified port fails
        print(f"UDP bound to port {udp_sock.getsockname()[1]}")

    async def receive_messages():
        """Asynchronously receive messages from the UDP socket."""
        while not shutdown_event.is_set():  # Loop until shutdown is signaled
            try:
                # Use an executor to receive messages in a non-blocking way
                data = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: udp_sock.recv(BUFFER_SIZE)
                )
                
                if data:
                    # Extract room name size, token size, room name, token, and message from the received data
                    room_name_size = data[0]
                    token_size = data[1]
                    room_name_received = data[2:2 + room_name_size].decode('utf-8')
                    token_received = data[2 + room_name_size:2 + room_name_size + token_size]
                    message = data[2 + room_name_size + token_size:].decode('utf-8')
                    
                    # Skip displaying messages from self
                    if token_received != token:
                        print(f"\r[{room_name_received}] {token_received.decode('utf-8')}: {message}")  # Print received message
                        print("Message: ", end='', flush=True)  # Prompt for the next message input
            except Exception as e:
                if not shutdown_event.is_set():
                    print(f"\nError receiving message: {e}")

    receive_task = asyncio.create_task(receive_messages())  # Start receiving messages asynchronously

    try:
        while not shutdown_event.is_set():  # Loop until shutdown is signaled
            try:
                # Use an executor to get user input in a non-blocking way
                message = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: input("Message: ")
                )
                
                if message.lower() == '/quit':  # Check for quit command
                    break  # Exit the loop if quit is requested
                    
                # Prepare the packet to send to the server
                room_name_bytes = room_name.encode('utf-8')  # Encode room name to bytes
                token_size = len(token)  # Get the size of the token
                
                packet = (
                    bytes([len(room_name_bytes)]) +  # Room name length
                    bytes([token_size]) +  # Token length
                    room_name_bytes +  # Room name
                    token +  # User token
                    message.encode('utf-8')  # Message content
                )
                
                udp_sock.sendto(packet, (server_address, SERVER_UDP_PORT))  # Send the packet to the server
            except Exception as e:
                if not shutdown_event.is_set():
                    print(f"\nError sending message: {e}")
    finally:
        shutdown_event.set()  # Signal shutdown
        receive_task.cancel()  # Cancel the receiving task
        try:
            await receive_task  # Wait for the receiving task to finish
        except asyncio.CancelledError:
            pass
        udp_sock.close()  # Close the UDP socket

def cleanup_client():
    """Cleanup client resources."""
    print("\nShutting down client...")  # Notify that the client is shutting down
    shutdown_event.set()  # Signal shutdown
    sys.exit(0)  # Exit the program

async def start_client():
    """Start the client and handle user input for room creation/joining."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda s, f: cleanup_client())
    signal.signal(signal.SIGTERM, lambda s, f: cleanup_client())

    # Prompt user for server address, room name, and operation type
    server_address = input("Enter server address (default '127.0.0.1'): ") or '127.0.0.1'
    room_name = input("Enter room name: ")
    operation = int(input("1: Create room, 2: Join room: "))
    
    # Connect to the server using TCP
    token, local_port = tcp_connect(server_address, room_name, operation)
    
    if token:
        try:
            await udp_chat(server_address, token, room_name, local_port)  # Start UDP chat if connected successfully
        except Exception as e:
            print(f"Error in chat: {e}")  # Handle any errors that occur during chat
    else:
        print("Failed to connect to room.")  # Notify if connection to room failed

if __name__ == '__main__':
    try:
        asyncio.run(start_client())  # Start the client
    except KeyboardInterrupt:
        cleanup_client()  # Handle keyboard interrupt for graceful shutdown
