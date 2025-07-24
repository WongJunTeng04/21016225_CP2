# main_control_app.py

# Imports
import cv2
import os
import numpy as np
import json

# Project-specific imports
from gesture_recognition.camera_manager import CameraManager
from gesture_recognition.hand_detector import HandDetector
from gesture_recognition.gesture_classifier import GestureClassifier
from gesture_recognition.action_mapper import ActionMapper
from network_communication.command_sender import CommandSender
from pygame_visualizer import PygameVisualizer
from video_stream_client import VideoStreamClient
from tts_manager import TTSManager
from voice_command_processor import VoiceCommandProcessor

# Configuration Constants
LOCAL_CAMERA_ID = 0 # 0 is typically the built-in camera, can change if using an external camera
TARGET_IP_FOR_COMMANDS = "172.20.10.10" # IP of the Raspberry Pi

# Network ports
TARGET_PORT_FOR_COMMANDS = 5005 # Port the RPi's command listener is using, this are arbitrary and can be changed.
RPI_VIDEO_LISTEN_PORT = 12345 # Port Mac listens on for UDP video, also arbitrary and can be changed.

# Enable/Disable features
ENABLE_ROBOT_VIDEO_STREAM = True # True to show the robot's camera feed, False to disable it
ENABLE_TTS = False; # Enable Text-to-Speech for command announcements. For demo purposes, this is set to False.
ENABLE_VOICE_COMMANDS = True # Enable voice command processing
ENABLE_PYGAME_VISUALIZER = True # Enable Pygame visualizer for simulating robot movement

# Configuration paths
TTS_PHRASES_CONFIG_PATH = os.path.join("config", "tts_phrases.json") # Path to the TTS phrases configuration file
CONFIG_FILE_PATH = os.path.join("config", "gestures_config.json") # Path to the gestures configuration file

# Gesture Recognition Tuning
GESTURE_CONFIRM_FRAMES = 3; # How many frames a gesture must be stable to be confirmed as an action. More frames = more stable but slower response.

# Augmented Reality (AR) Overlay Configuration
AR_ROBOT_POV_POSITION_TYPE = "CENTER"; # Position of the AR overlay on the Robot POV window, can be "CENTER" or "TOP_LEFT"
AR_SYMBOL_SIZE = 80 # Size of the AR symbols in pixels
FONT, FONT_SCALE, FONT_THICKNESS = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2 # Font settings for text overlays
COLOR_GREEN, COLOR_RED, COLOR_BLUE = (0, 255, 0), (0, 0, 255), (255, 0, 0) # Colors for AR symbols (For STOP, GO_FORWARD, and MOVE_BACKWARD)
COLOR_ORANGE, COLOR_WHITE, COLOR_YELLOW_AR = (0, 165, 255), (255, 255, 255), (0, 200, 200) # Yellow color for AR arrows (For TURN_LEFT and TURN_RIGHT)

# Function to load TTS phrases from a JSON file. This is for TTS announcements. When a command is detected,
# TTS manager will look up the phrase in this file.
def load_tts_phrases(config_path):
    try:
        with open(config_path, 'r') as f: phrases = json.load(f) # Load phrases from JSON file
        print(f"INFO: Loaded TTS phrases from: {config_path}"); # Ensure the file exists and is a valid JSON
        return phrases # Return the loaded phrases dictionary
    except Exception as e: print(f"ERROR: Loading TTS from {config_path}: {e}"); # If there's an error, return an empty dictionary
    return {}

# Function to draw symbols for the AR overlay on the local camera frame.
# This function draws a stop symbol or an arrow based on the command.
def draw_stop_symbol(image, center_x, center_y, size): 
    radius = size // 2; cv2.circle(image, (center_x, center_y), radius, COLOR_RED, -1) # Draw a filled circle for the stop symbol
    offset = int(radius * 0.6) 
    cv2.line(image, (center_x - offset, center_y - offset), (center_x + offset, center_y + offset), COLOR_WHITE, 3)
    cv2.line(image, (center_x - offset, center_y + offset), (center_x + offset, center_y - offset), COLOR_WHITE, 3)

# Function to draw arrows for the AR overlay on the local camera frame.
# This function draws arrows pointing in the direction of the command.
def draw_arrow(image, center_x, center_y, size, direction, color):
    s = size // 2 # Size of the arrow
    # Depending on the direction, calculate the points for the arrow shape. Since view is flipped, we adjust the coordinates accordingly.
    if direction == "UP": pts = np.array([[center_x, center_y - s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y + s//2], [center_x + s//4, center_y + s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
    elif direction == "DOWN": pts = np.array([[center_x, center_y + s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y - s//2], [center_x + s//4, center_y - s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
    elif direction == "RIGHT": pts = np.array([[center_x + s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x - s//2, center_y - s//4], [center_x - s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
    elif direction == "LEFT": pts = np.array([[center_x - s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x + s//2, center_y - s//4], [center_x + s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
    else: return
    cv2.drawContours(image, [pts], 0, color, -1) # Draw the filled arrow shape on the image
class MainApplication:
    def __init__(self):
        # Constructor for the main application.
        # This method initializes all the necessary components and sets up the application's initial state.
        print("MainApplication: Initializing components...")
        self.local_cam_manager = CameraManager(camera_id=LOCAL_CAMERA_ID)
        self.hand_detector = HandDetector(max_hands=1)
        self.gesture_classifier = GestureClassifier()
        self.action_mapper = ActionMapper(config_file_path=CONFIG_FILE_PATH)
        self.command_sender = CommandSender(target_ip=TARGET_IP_FOR_COMMANDS, target_port=TARGET_PORT_FOR_COMMANDS)
        self.pygame_visualizer = PygameVisualizer() if ENABLE_PYGAME_VISUALIZER else None
        self.tts_manager = TTSManager(voice="Alex", rate=190) if ENABLE_TTS else None
        self.tts_phrases = load_tts_phrases(TTS_PHRASES_CONFIG_PATH) if ENABLE_TTS else {}
        self.voice_command_processor = VoiceCommandProcessor() if ENABLE_VOICE_COMMANDS else None
        
        # Set up the voice command processor if enabled
        # This is a crucial link. We tell the voice processor: "When you have a command, call my handler method."
        if self.voice_command_processor:
            self.voice_command_processor.set_command_callback(self.handle_incoming_command)
        self.robot_video_client = None
        
        # If video stream is enabled, initialize the VideoStreamClient
        if ENABLE_ROBOT_VIDEO_STREAM:
            self.robot_video_client = VideoStreamClient(port=RPI_VIDEO_LISTEN_PORT)
            self.robot_video_client.start_receiving() # This starts the background thread for receiving video
        
        # State Variables
        self.app_running = True 
        self.last_confirmed_gesture_key = "NO_HAND"
        self.current_potential_gesture_key = "NO_HAND"
        self.gesture_stability_count = 0
        self.last_dispatched_robot_command = "STOP"
        self.last_announced_command_for_tts = "INIT_TTS"
        self.is_tts_active_for_vcp_suppression = False
        self.robot_pov_window_name = "Robot POV"

    # This is the central hub for all user commands, whether from gestures or voice.
    def handle_incoming_command(self, command, source_type):
        if command is None or command == "UNKNOWN_COMMAND": return 
        # This condition is key: we only process a command if it's different from the last one,
         # However, we ALWAYS process a voice command to provide immediate feedback.
        if command != self.last_dispatched_robot_command or source_type == "voice":
            if command == "NO_ACTION": # If the command is "NO_ACTION", we don't dispatch it.
                command = "STOP" if self.last_dispatched_robot_command != "STOP" else "NO_ACTION"
                if command == "NO_ACTION": return
            
            # Announce the command via TTS if enabled and if it's a new command or a voice command.
            if self.tts_manager and (command != self.last_announced_command_for_tts or source_type == "voice"):
                # The voice commmand is muted while TTS is active to avoid overlapping speech.
                # This is a UX decision to prevent confusion.
                phrase = self.tts_phrases.get(command)
                if phrase:
                    if self.voice_command_processor:
                        self.voice_command_processor.set_suppress(True)
                        self.is_tts_active_for_vcp_suppression = True
                    self.tts_manager.speak(phrase)
                self.last_announced_command_for_tts = command
            self.last_dispatched_robot_command = command

    def run(self):
        if not self.local_cam_manager.start_camera(): self.cleanup(); return
        if self.voice_command_processor: self.voice_command_processor.start_listening()
        
        if self.robot_video_client:
            try: cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
            except Exception as e: print(f"ERROR: Creating Robot POV window: {e}")

        try:
            while self.app_running:
                 # Get user input from Pygame window (like when you press "Q" on it to quit).
                if self.pygame_visualizer:
                    self.pygame_visualizer.handle_input()
                    if not self.pygame_visualizer.is_running: self.app_running = False; break
                
                 # Get the latest image from the MacBook camera
                local_frame = self.local_cam_manager.get_frame()
                if local_frame is None: self.app_running = False; break
                
                # Process the local camera frame for gesture recognition
                # This includes flipping the frame for a mirror effect, converting to RGB, detecting hands,
                # and drawing landmarks if hands are detected.
                flipped_frame = cv2.flip(local_frame, 1); rgb_frame = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
                self.hand_detector.find_hands(rgb_frame)
                landmarks, _ = self.hand_detector.get_landmarks() 
                display_frame = flipped_frame.copy()
                
                # If hands are detected, classify the gesture and handle the command
                # If no hands are detected, we set the current gesture to "NO_HAND".
                # This is important for the gesture recognition logic to know when to stop recognizing gestures.
                current_gesture = "NO_HAND"
                if landmarks:
                    display_frame = self.hand_detector.draw_landmarks(display_frame, landmarks[0])
                    
                    current_gesture = self.gesture_classifier.classify(landmarks[0])
                   
                # If the current gesture is different from the last confirmed gesture, we reset the stability count.
                # If the gesture is stable for a certain number of frames, we confirm it and dispatch
                if current_gesture == self.current_potential_gesture_key: self.gesture_stability_count +=1
                else: self.current_potential_gesture_key = current_gesture; self.gesture_stability_count = 1
                
                # Debounce the gesture: check if it's been stable for GESTURE_CONFIRM_FRAMES
                if self.gesture_stability_count >= GESTURE_CONFIRM_FRAMES and \
                   self.last_confirmed_gesture_key != self.current_potential_gesture_key:
                    self.last_confirmed_gesture_key = self.current_potential_gesture_key
                    # If a new stable gesture is found, convert it to a command and send it to the central handler
                    cmd = self.action_mapper.get_command(self.last_confirmed_gesture_key)
                    self.handle_incoming_command(cmd, "gesture")

                # Check if TTS has finished, and if so, "un-mute" the voice recognizer
                if self.tts_manager and self.voice_command_processor and self.is_tts_active_for_vcp_suppression:
                    if not self.tts_manager.is_busy():
                        self.voice_command_processor.set_suppress(False); self.is_tts_active_for_vcp_suppression = False
                
                # Update the Pygame simulator's position based on the last command
                if self.pygame_visualizer: self.pygame_visualizer.update_robot_state(self.last_dispatched_robot_command)
                if self.command_sender: self.command_sender.send(self.last_dispatched_robot_command)

                 # Draw AR symbols on the local camera view, to show the direction of the robot's movement. Shows for 
                # when either gesture or voice commands are used.
                action_for_ar = self.last_dispatched_robot_command
                h_local, w_local = display_frame.shape[:2]; ar_x_local, ar_y_local = w_local // 2, h_local // 2
                if action_for_ar == "STOP": draw_stop_symbol(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE)
                elif action_for_ar in ["GO_FORWARD", "GO_FORWARD_VOICE"]: draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "UP", COLOR_GREEN)
                elif action_for_ar in ["MOVE_BACKWARD", "MOVE_BACKWARD_VOICE"]: draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "DOWN", COLOR_BLUE)
                elif action_for_ar in ["TURN_RIGHT", "TURN_RIGHT_VOICE"]: draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "RIGHT", COLOR_YELLOW_AR)
                elif action_for_ar in ["TURN_LEFT","TURN_LEFT_VOICE"] : draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "LEFT", COLOR_YELLOW_AR)
                
                # Display the local camera frame with gesture and command overlays
                cv2.putText(display_frame, f"Gesture: {self.last_confirmed_gesture_key}", (10,30), FONT, FONT_SCALE, COLOR_RED, FONT_THICKNESS)
                cv2.putText(display_frame, f"Cmd: {self.last_dispatched_robot_command}", (10,60), FONT, FONT_SCALE, COLOR_ORANGE, FONT_THICKNESS)
                cv2.imshow('Gesture Control UX (Local Cam)', display_frame)
                
                # Get the robot's camera frame and display it
                if self.robot_video_client:
                    pov_frame = self.robot_video_client.get_frame() 
                    if pov_frame is not None:
                        
                        cv2.imshow(self.robot_pov_window_name, pov_frame)
                        
                 # Draw the updated state of the Pygame simulator
                if self.pygame_visualizer: self.pygame_visualizer.draw(f"Sim Cmd: {self.last_dispatched_robot_command}")
                
                # Listen for the 'Q','q' key to quit
                if cv2.waitKey(1) & 0xFF == ord('q'): self.app_running = False; break
        finally:
            self.cleanup()

    # Ensures all resources are properly closed when the app exits.
    def cleanup(self):
        if self.local_cam_manager: self.local_cam_manager.release_camera()
        if self.robot_video_client: self.robot_video_client.close()
        if self.hand_detector: self.hand_detector.close()
        if self.command_sender: self.command_sender.close()
        if self.pygame_visualizer: self.pygame_visualizer.close()
        if self.tts_manager: self.tts_manager.stop()
        if self.voice_command_processor: self.voice_command_processor.stop_listening()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    app = MainApplication()
    app.run()