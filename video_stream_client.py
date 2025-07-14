# # video_stream_client.py
# # Import necessary libraries
# import cv2
# import socket
# import struct
# import pickle
# import numpy as np
# import time

# # VideoStreamClient class for receiving video frames from a server
# # This class handles the connection to a video server, receives frames, decodes them,
# # and displays the video feed in a window.
# # It also calculates and displays the frames per second (FPS) of the video stream.
# class VideoStreamClient:
#     # Intialises the parameters for the video stream client.
#     # Parameters:
#     # host_ip: IP address of the video server (default is required)
#     # port: Port number of the video server (default is 8485)
#     # Initializes the socket, payload size for frame size, data buffer, connection status,
#     # and timing variables for FPS calculation.
#     # Sets the display FPS interval to 2 seconds for periodic updates.
#     def __init__(self, host_ip, port=8485):
#         self.host_ip = host_ip
#         self.port = port
#         self.client_socket = None
#         self.payload_size = struct.calcsize(">L") # Size of the packed frame size (unsigned long)
#         self.data_buffer = b""
#         self.is_connected = False
#         self.last_frame_time = time.time()
#         self.frames_received_interval = 0
#         self.display_fps_interval = 2 # seconds

#     def connect(self):
#         try:
#             # print(f"Attempting to create socket for {self.host_ip}:{self.port}")
#             self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             self.client_socket.settimeout(5) # Set a timeout for the connect attempt (e.g., 5 seconds)
#             # print(f"Socket created. Attempting to connect to {self.host_ip}:{self.port}...")
#             self.client_socket.connect((self.host_ip, self.port)) # This is the blocking call
#             self.is_connected = True
#             print(f"Successfully connected to video server at {self.host_ip}:{self.port}")
#             self.client_socket.settimeout(None) # Remove timeout after connection for normal operation
#             return True
        
#         except socket.timeout:
#             print(f"Connection attempt to {self.host_ip}:{self.port} timed out after 5 seconds.")
#             self.is_connected = False
#             if self.client_socket: self.client_socket.close() # Close socket on timeout
#             self.client_socket = None
#             return False
        
#         except socket.error as e:
#             print(f"Socket error during connect to {self.host_ip}:{self.port}: {e}")
#             self.is_connected = False
#             if self.client_socket: self.client_socket.close()
#             self.client_socket = None
#             return False
        
#         except Exception as e:
#             print(f"An unexpected error occurred during connect: {e}")
#             self.is_connected = False
#             if self.client_socket: self.client_socket.close()
#             self.client_socket = None
#             return False

#     def receive_frame(self):
#         if not self.is_connected:
#             return None

#         try:
#             # Retrieve message size
#             while len(self.data_buffer) < self.payload_size:
#                 packet = self.client_socket.recv(4*1024) # 4K buffer size
#                 if not packet:
#                     print("Connection lost while receiving payload size.")
#                     self.is_connected = False
#                     return None
#                 self.data_buffer += packet
            
#             packed_msg_size = self.data_buffer[:self.payload_size]
#             self.data_buffer = self.data_buffer[self.payload_size:]
#             msg_size = struct.unpack(">L", packed_msg_size)[0]

#             # Retrieve data based on message size
#             while len(self.data_buffer) < msg_size:
#                 packet = self.client_socket.recv(4*1024)
#                 if not packet:
#                     print("Connection lost while receiving frame data.")
#                     self.is_connected = False
#                     return None
#                 self.data_buffer += packet
            
#             frame_data = self.data_buffer[:msg_size]
#             self.data_buffer = self.data_buffer[msg_size:]

#             # Deserialize and decode frame
#             encoded_frame = pickle.loads(frame_data, fix_imports=True, encoding="bytes")
#             frame = cv2.imdecode(encoded_frame, cv2.IMREAD_COLOR)
            
#             self.frames_received_interval += 1
#             current_time = time.time()
#             if current_time - self.last_frame_time > self.display_fps_interval:
#                 fps = self.frames_received_interval / (current_time - self.last_frame_time)
#                 print(f"Receiving Video FPS: {fps:.2f}")
#                 self.frames_received_interval = 0
#                 self.last_frame_time = current_time

#             return frame

#         except (socket.error, struct.error, pickle.UnpicklingError, ConnectionResetError, BrokenPipeError) as e:
#             print(f"Error receiving/processing frame: {e}")
#             self.is_connected = False
#             return None
        
#         except Exception as e:
#             print(f"An unexpected error occurred in receive_frame: {e}")
#             self.is_connected = False
#             return None

#     def close(self):
#         if self.client_socket:
#             self.client_socket.close()
#         self.is_connected = False
#         print("Video client connection closed.")

# # --- Standalone test for video_stream_client.py ---
# if __name__ == '__main__':
#     RPI_IP_ADDRESS = "192.168.68.105"
    
#     video_client = VideoStreamClient(host_ip=RPI_IP_ADDRESS)
    
#     if not video_client.connect():
#         print("Exiting test.")
#         exit()

#     cv2.namedWindow("Robot Video Feed", cv2.WINDOW_NORMAL)

#     try:
#         while True:
#             frame = video_client.receive_frame()
#             if frame is not None:
#                 cv2.imshow("Robot Video Feed", frame)
#             elif not video_client.is_connected:
#                 print("Disconnected. Attempting to reconnect...")
#                 time.sleep(2) # Wait before retrying
#                 if not video_client.connect():
#                     print("Reconnect failed. Exiting.")
#                     break # Exit if reconnect fails immediately

#             key = cv2.waitKey(1) & 0xFF
#             if key == ord('q'):
#                 break
#     finally:
#         video_client.close()
#         cv2.destroyAllWindows()


# # video_stream_client.py (Corrected for Low Latency - NO PICKLE)
# import cv2
# import socket
# import struct
# import numpy as np
# import time

# class VideoStreamClient:
#     def __init__(self, host_ip, port=8485):
#         self.host_ip = host_ip; self.port = port; self.client_socket = None
#         self.payload_size = struct.calcsize(">L"); self.data_buffer = b""
#         self.is_connected = False
    
#     def connect(self):
#         try:
#             self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
#             self.client_socket.settimeout(3.0)
#             self.client_socket.connect((self.host_ip, self.port))
#             self.client_socket.settimeout(None)
#             self.is_connected = True; return True
#         except (socket.timeout, socket.error) as e:
#             # print(f"Connection to {self.host_ip}:{self.port} failed: {e}")
#             self.is_connected = False; self.client_socket = None; return False

#     def receive_frame(self):
#         if not self.is_connected or not self.client_socket: return None
#         try:
#             while len(self.data_buffer) < self.payload_size:
#                 packet = self.client_socket.recv(4096)
#                 if not packet: self.is_connected = False; return None
#                 self.data_buffer += packet
            
#             packed_msg_size = self.data_buffer[:self.payload_size]
#             self.data_buffer = self.data_buffer[self.payload_size:]
#             msg_size = struct.unpack(">L", packed_msg_size)[0]

#             while len(self.data_buffer) < msg_size:
#                 packet = self.client_socket.recv(4096)
#                 if not packet: self.is_connected = False; return None
#                 self.data_buffer += packet
            
#             frame_data_bytes = self.data_buffer[:msg_size]
#             self.data_buffer = self.data_buffer[msg_size:]

#             # *** THE FIX: Decode raw JPEG bytes, no pickle ***
#             frame_as_np = np.frombuffer(frame_data_bytes, dtype=np.uint8)
#             frame = cv2.imdecode(frame_as_np, cv2.IMREAD_COLOR)
            
#             if frame is None:
#                 # print("WARNING: cv2.imdecode failed, received corrupted frame.")
#                 return None
#             return frame
#         except (socket.error, struct.error, ConnectionResetError, BrokenPipeError, cv2.error):
#             self.is_connected = False; return None
#         except Exception:
#             self.is_connected = False; return None

#     def close(self):
#         if self.client_socket: self.client_socket.close()
#         self.is_connected = False; self.client_socket = None
#         print("Video client connection closed.")


# video_stream_client.py (UDP Receiver Version)

import threading
import cv2
import socket
import numpy as np
import time
import traceback

class VideoStreamClient:
    def __init__(self, listen_ip="0.0.0.0", port=12345):
        self.listen_ip = listen_ip # Listen on all interfaces on the Mac
        self.port = port
        self.client_socket = None
        self.is_listening = False
        self.listen_thread = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.stop_event = threading.Event()

    def _receive_loop(self):
        """This thread's only job is to receive UDP packets and decode them."""
        print(f"CLIENT (UDP): Listening for video packets on {self.listen_ip}:{self.port}")
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set a buffer size for the socket
        # If your network is lossy, a larger buffer might help, but can increase latency.
        # Let's keep it reasonable.
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        try:
            self.client_socket.bind((self.listen_ip, self.port))
        except Exception as e:
            print(f"CLIENT ERROR: Could not bind to port {self.port}: {e}")
            print("             Another application might be using this port.")
            return

        while not self.stop_event.is_set():
            try:
                # Receive a packet. The buffer size should be large enough for one frame.
                data, _ = self.client_socket.recvfrom(65536)
                
                # Decode the raw JPEG bytes
                frame_as_np = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(frame_as_np, cv2.IMREAD_COLOR)

                # If decoding is successful, update the latest_frame
                if frame is not None:
                    with self.frame_lock:
                        self.latest_frame = frame
                # else: # This is where glitches come from - a corrupted packet
                    # print("CLIENT WARNING: Received corrupted frame packet.")

            except Exception as e:
                # print(f"CLIENT ERROR in receive loop: {e}")
                # traceback.print_exc()
                time.sleep(0.1)

        print("CLIENT INFO: Receive loop stopped.")
        self.client_socket.close()

    def start_receiving(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.stop_event.clear()
        self.listen_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.listen_thread.start()

    def get_frame(self):
        """Main application calls this to get the most recent frame."""
        frame = None
        with self.frame_lock:
            if self.latest_frame is not None:
                frame = self.latest_frame.copy()
        return frame

    def close(self):
        print("CLIENT INFO: Closing video stream client.")
        self.stop_event.set()
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)