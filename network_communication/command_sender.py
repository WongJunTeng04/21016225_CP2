# command_sender.py

# Imports
import socket
import time

class CommandSender:
    def __init__(self, target_ip="127.0.0.1", target_port=5005):
        self.target_ip = target_ip # IP address of the target robot or server
        self.target_port = target_port # Port to send commands to
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.last_sent_command = None
        self.last_sent_time = 0
        self.send_interval = 0.3 # seconds, to avoid spamming the robot with commands

        print(f"CommandSender initialized to send to {self.target_ip}:{self.target_port}")

    # Send a command to the target robot or server.
    def send(self, command):
        current_time = time.time()
        # Only send if command is new or interval has passed for continuous commands
        if command != self.last_sent_command or \
           (current_time - self.last_sent_time > self.send_interval) or \
           command == "STOP": # Always send STOP immediately if it's new
            
            if command != "NO_ACTION" and command != "UNKNOWN_COMMAND": # Don't send these
                try:
                    self.sock.sendto(command.encode(), (self.target_ip, self.target_port))
                    # print(f"Sent command: {command}") # Optional: for debugging
                    self.last_sent_command = command
                    self.last_sent_time = current_time
                except Exception as e:
                    print(f"Error sending command '{command}': {e}")
            elif command == "NO_ACTION" and self.last_sent_command != "STOP" and self.last_sent_command is not None:
                # If current gesture is "no action" and robot wasn't already stopped, send STOP
                # This behavior is UX dependent
                # self.send("STOP") # Uncomment if you want this behavior
                pass


    def close(self):
        self.sock.close()
        print("CommandSender socket closed.")