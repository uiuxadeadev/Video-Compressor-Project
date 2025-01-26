import socket
import threading
import asyncio
import signal
import sys

# Constants for the TCP and UDP ports, and buffer size for data transmission
SERVER_TCP_PORT = 9001  # Port for TCP connections
SERVER_UDP_PORT = 9002  # Port for UDP communications
BUFFER_SIZE = 4096  # Buffer size for receiving data

# Dictionaries to hold chat room information and client connections
chat_rooms = {}  # Maps room names to their members
clients = {}  # Maps client addresses to their connection details
shutdown_event = threading.Event()  # Event to signal server shutdown

"""
chat_rooms = {
    "room1": [
        (b"host_192.168.1.100", ("192.168.1.100", 54321)),
        (b"guest_192.168.1.101_1", ("192.168.1.101", 54322))
    ],
    "game_room": [
        (b"host_192.168.1.200", ("192.168.1.200", 54323)),
        (b"guest_192.168.1.201_1", ("192.168.1.201", 54324)),
        (b"guest_192.168.1.202_2", ("192.168.1.202", 54325))
    ]
}
"""
"""
clients = {
    b"host_192.168.1.100": {
        "room": "room1",
        "join_time": "2024-10-25 14:30:00",
        "is_host": True
    },
    b"guest_192.168.1.101_1": {
        "room": "room1",
        "join_time": "2024-10-25 14:35:00",
        "is_host": False
    }
}
"""

def create_tcp_socket():
    """Create and configure a TCP socket with proper options."""
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP socket
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
    try:
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # Allow port reuse if supported
    except AttributeError:
        pass  # Ignore if the platform does not support SO_REUSEPORT
    return tcp_sock  # Return the configured TCP socket

def create_udp_socket():
    """Create and configure a UDP socket with proper options."""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
    try:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # Allow port reuse if supported
    except AttributeError:
        pass  # Ignore if the platform does not support SO_REUSEPORT
    return udp_sock  # Return the configured UDP socket

async def udp_chat_handler():
    """Handle incoming UDP chat messages and manage member communications."""
    udp_sock = create_udp_socket()  # Create a UDP socket
    try:
        # Bind the UDP socket to all interfaces on the specified port
        udp_sock.bind(('0.0.0.0', SERVER_UDP_PORT))  
        print(f"UDP server listening on port {SERVER_UDP_PORT}")  # Notify that the server is listening
        
        while not shutdown_event.is_set():  # Loop until a shutdown event is signaled
            udp_sock.settimeout(1.0)  # Set a timeout for receiving data
            try:
                # Receive messages sent to the UDP socket
                data, addr = udp_sock.recvfrom(BUFFER_SIZE)  # Blocking call to receive data
                
                # Parse the received packet
                room_name_size = data[0]  # First byte: size of the room name
                token_size = data[1]  # Second byte: size of the sender's token
                room_name = data[2:2 + room_name_size].decode('utf-8')  # Extract room name
                sender_token = data[2 + room_name_size:2 + room_name_size + token_size]  # Extract sender's token
                message = data[2 + room_name_size + token_size:].decode('utf-8')  # Extract message

                print(f"\nReceived message in room {room_name}")  # Notify of the received message
                print(f"From: {sender_token.decode('utf-8')} at {addr}")  # Display sender's token and address
                print(f"Message: {message}")  # Display the message content

                # Check if the room exists in the chat_rooms dictionary
                if room_name in chat_rooms:
                    members = chat_rooms[room_name]  # Get members of the chat room
                    print(f"Room members: {[token[0].decode('utf-8') for token in members]}")  # List current members
                    
                    # Prepare the packet to send to all room members
                    packet = (
                        bytes([len(room_name)]) +  # Room name length
                        bytes([len(sender_token)]) +  # Sender token length
                        room_name.encode('utf-8') +  # Room name as bytes
                        sender_token +  # Sender's token
                        message.encode('utf-8')  # Message content as bytes
                    )
                    
                    # Send the message packet to all members in the room
                    for member_token, member_addr in members:
                        try:
                            print(f"Sending to {member_token.decode('utf-8')} at {member_addr}")  # Notify where message is sent
                            udp_sock.sendto(packet, member_addr)  # Send the message packet
                        except Exception as e:
                            print(f"Error sending to {member_token.decode('utf-8')}: {e}")  # Handle errors during sending
                else:
                    print(f"Room {room_name} not found")  # Notify if room does not exist
                    udp_sock.sendto(b"Room not found", addr)  # Send error message back to sender
                    
            except socket.timeout:
                continue  # Ignore timeout and continue waiting for messages
            except Exception as e:
                if not shutdown_event.is_set():  # Check if shutdown is not signaled
                    print(f"Error in UDP handler: {e}")  # Print any error encountered
    finally:
        udp_sock.close()  # Ensure the UDP socket is closed upon exit

def handle_tcp_connection(conn, addr):
    """Handle a new TCP connection and manage room creation or joining."""
    print(f"New TCP connection from {addr}")  # Notify of a new TCP connection
    try:
        data = conn.recv(BUFFER_SIZE)  # Receive data from the client
        if not data:
            return  # If no data is received, exit the function
        
        # Parse data from the client
        room_name_size = data[0]      # Length of the room name (first byte)
        operation_code = data[1]      # Operation code (1: create, 2: join; second byte)
        state_code = data[2]          # State code (unused; third byte)
        room_name = data[3:3 + room_name_size].decode('utf-8')  # Extract the room name
        
        print(f"Room: {room_name}, Operation: {operation_code}")  # Display parsed room and operation info
        
        if operation_code == 1:  # Create room
            # Check if the room already exists
            if room_name not in chat_rooms:
                # Create the room if it doesn't exist
                chat_rooms[room_name] = []  # Initialize room with an empty list of members
                token = f"host_{addr[0]}".encode('utf-8')  # Create a token for the host
                chat_rooms[room_name].append((token, addr))  # Add the host to the room's member list
                print(f"Created room {room_name} with host {token.decode('utf-8')}")  # Notify room creation
                conn.sendall(b"Room created " + token)  # Send confirmation to the client
            else:
                conn.sendall(b"Room already exists")  # Notify if room already exists

        elif operation_code == 2:  # Join room
            # Check if the room exists for joining
            if room_name in chat_rooms:
                # Create a token for the new guest
                token = f"guest_{addr[0]}_{len(chat_rooms[room_name])}".encode('utf-8')
                chat_rooms[room_name].append((token, addr))  # Add the new guest to the room
                print(f"Client {token.decode('utf-8')} joined room {room_name}")  # Notify of the new member
                print(f"Current room members: {[t[0].decode('utf-8') for t in chat_rooms[room_name]]}")  # List current members
                conn.sendall(b"Joined room " + token)  # Send confirmation with the new token
            else:
                conn.sendall(b"Room not found")  # Notify if the room to join does not exist
    except Exception as e:
        print(f"Error handling TCP connection: {e}")  # Handle errors that occur during TCP handling
    finally:
        conn.close()  # Ensure the connection is closed upon exit

def cleanup_server(tcp_sock):
    """Cleanup server resources on shutdown."""
    print("\nShutting down server...")  # Notify shutdown process
    shutdown_event.set()  # Signal all threads to shut down
    tcp_sock.close()  # Close the TCP socket
    chat_rooms.clear()  # Clear the chat rooms dictionary
    clients.clear()  # Clear the clients dictionary
    sys.exit(0)  # Exit the program

def start_server():
    """Start the server with proper signal handling and cleanup."""
    tcp_sock = create_tcp_socket()  # Create a TCP socket
    
    try:
        # Configure the TCP socket and bind it to the specified port
        tcp_sock.bind(('0.0.0.0', SERVER_TCP_PORT))  # Bind to all interfaces
        tcp_sock.listen(5)  # Listen for incoming connections
        print(f"Server started on TCP port {SERVER_TCP_PORT} and UDP port {SERVER_UDP_PORT}")  # Notify server status

        # Set up signal handlers for graceful shutdown (e.g., on Ctrl+C)
        signal.signal(signal.SIGINT, lambda s, f: cleanup_server(tcp_sock))
        signal.signal(signal.SIGTERM, lambda s, f: cleanup_server(tcp_sock))

        # Start the UDP handler in a separate thread
        udp_thread = threading.Thread(target=lambda: asyncio.run(udp_chat_handler()))
        udp_thread.start()

        # Main loop for accepting TCP connections
        while not shutdown_event.is_set():
            try:
                tcp_sock.settimeout(1.0)  # Set timeout for accept()
                conn, addr = tcp_sock.accept()  # Wait for incoming connections
                # Handle each TCP connection in a separate thread
                client_thread = threading.Thread(target=handle_tcp_connection, args=(conn, addr))
                client_thread.start()
            except socket.timeout:
                continue  # Timeout occurred, check shutdown flag
            except Exception as e:
                if not shutdown_event.is_set():
                    print(f"Error accepting connection: {e}")

    except Exception as e:
        print(f"Server error: {e}")
    finally:
        cleanup_server(tcp_sock)

if __name__ == '__main__':
    try:
        start_server()
    except KeyboardInterrupt:
        print("\nServer shutdown requested...")
