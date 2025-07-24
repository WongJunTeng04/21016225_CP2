# video_stream_client.py

# Imports
import threading
import cv2
import socket
import numpy as np
import time
import traceback # For debugging

class VideoStreamClient:
    def __init__(self, listen_ip="0.0.0.0", port=12345):
        self.listen_ip = listen_ip # Listen on all interfaces on the Mac
        self.port = port # Port to listen for incoming video packets
        self.client_socket = None # Socket for receiving video data
        self.is_listening = False # Flag to indicate if the client is currently listening for video packets
        self.listen_thread = None # Thread for receiving video packets
        self.latest_frame = None # Latest received video frame
        self.frame_lock = threading.Lock() # Lock to protect access to the latest_frame
        self.stop_event = threading.Event() # Event to signal the thread to stop

    def _receive_loop(self):
        """This thread's only job is to receive UDP packets and decode them."""
        print(f"CLIENT (UDP): Listening for video packets on {self.listen_ip}:{self.port}")
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set a buffer size for the socket
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        try:
            self.client_socket.bind((self.listen_ip, self.port))
        except Exception as e:
            print(f"CLIENT ERROR: Could not bind to port {self.port}: {e}")
            print("             Another application might be using this port.")
            return

        # Loop to receive packets until stop_event is set
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
                        
            # If an error occurs, print it and continue listening
            except Exception as e:
                time.sleep(0.1)

        # If we reach here, it means the stop_event was set. Program was closed.
        print("CLIENT INFO: Receive loop stopped.")
        self.client_socket.close()

    # Start receiving video packets in a separate thread.
    # This method is called by the main application to start the video stream client.
    # It initializes the socket and starts the receive loop in a new thread.
    # If the client is already listening, it does nothing.
    # If the socket cannot be created or bound, it prints an error message.
    def start_receiving(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.stop_event.clear()
        self.listen_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.listen_thread.start()

    # Stop receiving video packets and close the socket.
    # This method is called by the main application to stop the video stream client.
    # It sets the stop_event to signal the receive loop to stop and waits for the thread to finish.
    # If the client is not listening, it does nothing.
    def get_frame(self):
        """Main application calls this to get the most recent frame."""
        frame = None
        with self.frame_lock:
            if self.latest_frame is not None:
                frame = self.latest_frame.copy()
        return frame

    # Stop the video stream client.
    # This method is called by the main application to stop the video stream client.
    # It sets the stop_event to signal the receive loop to stop and waits for the thread to finish.
    # If the client is not listening, it does nothing.
    def close(self):
        print("CLIENT INFO: Closing video stream client.")
        self.stop_event.set()
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)