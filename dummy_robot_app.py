import socket

# If you want to make network_communication.command_receiver.py a class:
# from network_communication.command_receiver import CommandReceiver

LISTEN_IP = "127.0.0.1"
LISTEN_PORT = 5005

def run_dummy_robot():
    sock_listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock_listen.bind((LISTEN_IP, LISTEN_PORT))
        print(f"Dummy Robot listening on {LISTEN_IP}:{LISTEN_PORT}")
        print("Waiting for commands... Press Ctrl+C to stop.")

        while True:
            data, addr = sock_listen.recvfrom(1024) # buffer size
            command = data.decode()
            print(f"Received command: '{command}' from {addr}")
            # On a real robot, you'd parse 'command' and control motors here
            # e.g., if command == "FORWARD": robot.move_forward()
    except OSError as e:
        if e.errno == 48: # Address already in use
            print(f"Error: Address {LISTEN_IP}:{LISTEN_PORT} already in use. Is another instance running?")
        else:
            print(f"Socket error: {e}")
    except KeyboardInterrupt:
        print("\nDummy Robot stopping.")
    finally:
        sock_listen.close()
        print("Dummy Robot socket closed.")

if __name__ == '__main__':
    run_dummy_robot()