 # main_control_app.py
 
#Imports
import cv2
import time
import os
import pygame
import traceback
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

# --- Configuration Constants ---
LOCAL_CAMERA_ID = 0
TARGET_IP_FOR_COMMANDS = "192.168.68.105" # <<<--- CONFIRM THIS IS YOUR RPi's IP
TARGET_PORT_FOR_COMMANDS = 5005 

# --- VIDEO CONFIGURATION ---
ENABLE_ROBOT_VIDEO_STREAM = True
# The UDP server on the RPi needs to know the Mac's IP to send packets TO.
# The UDP client on the Mac just needs to know which port to LISTEN ON.
RPI_VIDEO_LISTEN_PORT = 12345 # <<<--- FIX: THIS LINE WAS MISSING
# ---------------------------

ENABLE_TTS = True
TTS_PHRASES_CONFIG_PATH = os.path.join("config", "tts_phrases.json")
ENABLE_VOICE_COMMANDS = True
ENABLE_PYGAME_VISUALIZER = True
GESTURE_CONFIRM_FRAMES = 3
CONFIG_FILE_PATH = os.path.join("config", "gestures_config.json") 
AR_ROBOT_POV_POSITION_TYPE = "CENTER"
AR_SYMBOL_SIZE = 80

# --- OpenCV Font Constants ---
FONT, FONT_SCALE, FONT_THICKNESS = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
COLOR_GREEN, COLOR_RED, COLOR_BLUE = (0, 255, 0), (0, 0, 255), (255, 0, 0)
COLOR_ORANGE, COLOR_WHITE, COLOR_YELLOW_AR = (0, 165, 255), (255, 255, 255), (0, 200, 200)

def load_tts_phrases(config_path):
    try:
        with open(config_path, 'r') as f: phrases = json.load(f)
        print(f"INFO: Loaded TTS phrases from: {config_path}"); return phrases
    except Exception as e: print(f"ERROR: Loading TTS from {config_path}: {e}"); return {}

def draw_stop_symbol(image, center_x, center_y, size):
    radius = size // 2; cv2.circle(image, (center_x, center_y), radius, COLOR_RED, -1)
    offset = int(radius * 0.6)
    cv2.line(image, (center_x - offset, center_y - offset), (center_x + offset, center_y + offset), COLOR_WHITE, 3)
    cv2.line(image, (center_x - offset, center_y + offset), (center_x + offset, center_y - offset), COLOR_WHITE, 3)
    
def draw_arrow(image, center_x, center_y, size, direction, color):
    s = size // 2
    if direction == "UP": pts = np.array([[center_x, center_y - s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y + s//2], [center_x + s//4, center_y + s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
    elif direction == "DOWN": pts = np.array([[center_x, center_y + s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y - s//2], [center_x + s//4, center_y - s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
    elif direction == "RIGHT": pts = np.array([[center_x + s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x - s//2, center_y - s//4], [center_x - s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
    elif direction == "LEFT": pts = np.array([[center_x - s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x + s//2, center_y - s//4], [center_x + s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
    else: return
    cv2.drawContours(image, [pts], 0, color, -1)

class MainApplication:
    def __init__(self):
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
        
        if self.voice_command_processor:
            self.voice_command_processor.set_command_callback(self.handle_incoming_command)
        
        self.robot_video_client = None
        if ENABLE_ROBOT_VIDEO_STREAM:
            print(f"INFO: Initializing video client to listen on UDP port {RPI_VIDEO_LISTEN_PORT}")
            self.robot_video_client = VideoStreamClient(port=RPI_VIDEO_LISTEN_PORT)
            self.robot_video_client.start_receiving()
            print("INFO: Video client receiver thread started.")
        else:
            print("INFO: Robot Video Stream is DISABLED.")
        
        # State Variables
        self.app_running = False
        self.last_confirmed_gesture_key = "NO_HAND"
        self.current_potential_gesture_key = "NO_HAND"
        self.gesture_stability_count = 0
        self.last_dispatched_robot_command = "STOP"
        self.last_announced_command_for_tts = "INIT_TTS"
        self.is_tts_active_for_vcp_suppression = False
        self.robot_pov_window_name = "Robot POV"
        print("MainApplication: Initialization complete.")

    def handle_incoming_command(self, command, source_type):
        if command is None or command == "UNKNOWN_COMMAND": return
        if command != self.last_dispatched_robot_command or source_type == "voice":
            if command == "NO_ACTION":
                command = "STOP" if self.last_dispatched_robot_command != "STOP" else "NO_ACTION"
                if command == "NO_ACTION": return
            
            # print(f"INFO: New command '{command}' from '{source_type}'. Updating state.")
            if self.tts_manager and (command != self.last_announced_command_for_tts or source_type == "voice"):
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
        
        print("INFO: Press 'q' in 'Gesture Control UX' window or close Pygame window to quit.")
        self.app_running = True
        
        if ENABLE_ROBOT_VIDEO_STREAM and self.robot_video_client:
            try: cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
            except Exception as e: print(f"ERROR: Creating Robot POV window: {e}")

        try:
            while self.app_running:
                if self.pygame_visualizer:
                    self.pygame_visualizer.handle_input()
                    if not self.pygame_visualizer.is_running: self.app_running = False; break
                
                local_frame = self.local_cam_manager.get_frame()
                if local_frame is None: self.app_running = False; break
                
                flipped_frame = cv2.flip(local_frame, 1); rgb_frame = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
                self.hand_detector.find_hands(rgb_frame)
                landmarks, handedness = self.hand_detector.get_landmarks()
                display_frame = flipped_frame.copy()
                
                current_gesture = "NO_HAND"
                if landmarks and handedness:
                    display_frame = self.hand_detector.draw_landmarks(display_frame, landmarks[0])
                    current_gesture = self.gesture_classifier.classify(landmarks[0], handedness[0].classification[0].label)
                
                if current_gesture == self.current_potential_gesture_key: self.gesture_stability_count +=1
                else: self.current_potential_gesture_key = current_gesture; self.gesture_stability_count = 1
                
                if self.gesture_stability_count >= GESTURE_CONFIRM_FRAMES and \
                   self.last_confirmed_gesture_key != self.current_potential_gesture_key:
                    self.last_confirmed_gesture_key = self.current_potential_gesture_key
                    cmd = self.action_mapper.get_command(self.last_confirmed_gesture_key)
                    self.handle_incoming_command(cmd, "gesture")

                if self.tts_manager and self.voice_command_processor and self.is_tts_active_for_vcp_suppression:
                    if not self.tts_manager.is_busy():
                        self.voice_command_processor.set_suppress(False); self.is_tts_active_for_vcp_suppression = False
                
                # Continuous Actions
                if self.pygame_visualizer: self.pygame_visualizer.update_robot_state(self.last_dispatched_robot_command)
                if self.command_sender: self.command_sender.send(self.last_dispatched_robot_command)

                # UI Rendering for Local View
                action_for_ar = self.last_dispatched_robot_command
                h_local, w_local = display_frame.shape[:2]; ar_x_local, ar_y_local = w_local // 2, h_local // 2
                if action_for_ar == "STOP": draw_stop_symbol(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE)
                elif action_for_ar in ["GO_FORWARD", "MOVE_FORWARD_CONT"]: draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "UP", COLOR_GREEN)
                elif action_for_ar == "MOVE_BACKWARD": draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "DOWN", COLOR_BLUE)
                elif action_for_ar == "TURN_RIGHT": draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "RIGHT", COLOR_YELLOW_AR)
                elif action_for_ar == "TURN_LEFT": draw_arrow(display_frame, ar_x_local, ar_y_local, AR_SYMBOL_SIZE, "LEFT", COLOR_YELLOW_AR)
                
                cv2.putText(display_frame, f"Gesture: {self.last_confirmed_gesture_key}", (10,30), FONT, FONT_SCALE, COLOR_RED, FONT_THICKNESS)
                cv2.putText(display_frame, f"Cmd: {self.last_dispatched_robot_command}", (10,60), FONT, FONT_SCALE, COLOR_ORANGE, FONT_THICKNESS)
                cv2.imshow('Gesture Control UX (Local Cam)', display_frame)
                
                # Video Stream Handling
                if self.robot_video_client:
                    pov_frame = self.robot_video_client.get_frame() 
                    if pov_frame is not None:
                        try:
                            if cv2.getWindowProperty(self.robot_pov_window_name, cv2.WND_PROP_VISIBLE) < 1:
                                cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
                        except cv2.error: cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
                        cv2.imshow(self.robot_pov_window_name, pov_frame)
                
                if self.pygame_visualizer: self.pygame_visualizer.draw(f"Sim Cmd: {self.last_dispatched_robot_command}")
                
                if cv2.waitKey(1) & 0xFF == ord('q'): self.app_running = False; break
        finally:
            self.cleanup()

    def cleanup(self):
        print("MainApplication: Cleaning up..."); 
        if self.local_cam_manager: self.local_cam_manager.release_camera()
        if self.robot_video_client: self.robot_video_client.close()
        if self.hand_detector: self.hand_detector.close()
        if self.command_sender: self.command_sender.close()
        if self.pygame_visualizer: self.pygame_visualizer.close()
        if self.tts_manager: self.tts_manager.stop()
        if self.voice_command_processor: self.voice_command_processor.stop_listening()
        cv2.destroyAllWindows()
        print("MainApplication: Cleanup complete.")

if __name__ == '__main__':
    app = MainApplication()
    app.run()
 
 
 
 
 
# import cv2
# import time
# import os
# import pygame
# import traceback
# import numpy as np
# import json

# # Project-specific imports
# from gesture_recognition.camera_manager import CameraManager
# from gesture_recognition.hand_detector import HandDetector
# from gesture_recognition.gesture_classifier import GestureClassifier
# from gesture_recognition.action_mapper import ActionMapper
# from network_communication.command_sender import CommandSender
# from pygame_visualizer import PygameVisualizer
# from video_stream_client import VideoStreamClient # This will now be the UDP version
# from tts_manager import TTSManager
# from voice_command_processor import VoiceCommandProcessor

# # --- Configuration Constants ---
# LOCAL_CAMERA_ID = 0
# TARGET_IP_FOR_COMMANDS = "192.168.68.105"
# TARGET_PORT_FOR_COMMANDS = 5005 

# # --- VIDEO CONFIGURATION CHANGE ---
# # RPI_VIDEO_SERVER_IP is NO LONGER NEEDED for the new client, but we'll define the port
# RPI_VIDEO_LISTEN_PORT = 12345 # The port the MacBook will listen on for UDP video packets
# # ------------------------------------
# ENABLE_ROBOT_VIDEO_STREAM = True
# CONFIG_FILE_PATH = os.path.join("config", "gestures_config.json") 
# ENABLE_TTS = True
# TTS_PHRASES_CONFIG_PATH = os.path.join("config", "tts_phrases.json")
# ENABLE_VOICE_COMMANDS = True
# ENABLE_PYGAME_VISUALIZER = True
# GESTURE_CONFIRM_FRAMES = 3
# AR_ROBOT_POV_POSITION_TYPE = "CENTER"
# AR_SYMBOL_SIZE = 80
# FONT, FONT_SCALE, FONT_THICKNESS = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
# COLOR_GREEN, COLOR_RED, COLOR_BLUE = (0, 255, 0), (0, 0, 255), (255, 0, 0)
# COLOR_ORANGE, COLOR_WHITE, COLOR_YELLOW_AR = (0, 165, 255), (255, 255, 255), (0, 200, 200)

# # (load_tts_phrases, draw_stop_symbol, and draw_arrow functions remain exactly the same)
# def load_tts_phrases(config_path):
#     try:
#         with open(config_path, 'r') as f: phrases = json.load(f)
#         print(f"INFO: Loaded TTS phrases from: {config_path}"); return phrases
#     except Exception as e: print(f"ERROR: Loading TTS from {config_path}: {e}"); return {}

# def draw_stop_symbol(image, center_x, center_y, size):
#     radius = size // 2; cv2.circle(image, (center_x, center_y), radius, COLOR_RED, -1)
#     offset = int(radius * 0.6)
#     cv2.line(image, (center_x - offset, center_y - offset), (center_x + offset, center_y + offset), COLOR_WHITE, 3)
#     cv2.line(image, (center_x - offset, center_y + offset), (center_x + offset, center_y - offset), COLOR_WHITE, 3)
    
# def draw_arrow(image, center_x, center_y, size, direction, color):
#     s = size // 2
#     if direction == "UP": pts = np.array([[center_x, center_y - s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y + s//2], [center_x + s//4, center_y + s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
#     elif direction == "DOWN": pts = np.array([[center_x, center_y + s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y - s//2], [center_x + s//4, center_y - s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
#     elif direction == "RIGHT": pts = np.array([[center_x + s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x - s//2, center_y - s//4], [center_x - s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
#     elif direction == "LEFT": pts = np.array([[center_x - s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x + s//2, center_y - s//4], [center_x + s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
#     else: return
#     cv2.drawContours(image, [pts], 0, color, -1)


# class MainApplication:
#     def __init__(self):
#         print("MainApplication: Initializing components...")
#         self.local_cam_manager = CameraManager(camera_id=LOCAL_CAMERA_ID)
#         self.hand_detector = HandDetector(max_hands=1)
#         self.gesture_classifier = GestureClassifier()
#         self.action_mapper = ActionMapper(config_file_path=CONFIG_FILE_PATH)
#         self.command_sender = CommandSender(target_ip=TARGET_IP_FOR_COMMANDS, target_port=TARGET_PORT_FOR_COMMANDS)
#         self.pygame_visualizer = PygameVisualizer() if ENABLE_PYGAME_VISUALIZER else None
#         self.tts_manager = TTSManager(voice="Alex", rate=190) if ENABLE_TTS else None
#         self.tts_phrases = load_tts_phrases(TTS_PHRASES_CONFIG_PATH) if ENABLE_TTS else {}
#         self.voice_command_processor = VoiceCommandProcessor() if ENABLE_VOICE_COMMANDS else None
        
#         if self.voice_command_processor:
#             self.voice_command_processor.set_command_callback(self.handle_incoming_command_from_source)
        
#         self.robot_video_client = None
#         # --- VIDEO CLIENT INITIALIZATION CHANGE ---
#         if ENABLE_ROBOT_VIDEO_STREAM:
#             print(f"INFO: Initializing video client to listen on UDP port {RPI_VIDEO_LISTEN_PORT}")
#             # The UDP client doesn't connect, it just starts listening.
#             self.robot_video_client = VideoStreamClient(port=RPI_VIDEO_LISTEN_PORT)
#             self.robot_video_client.start_receiving()
#             print("INFO: Video client receiver thread started.")
#         else:
#             print("INFO: Robot Video Stream is DISABLED.")
#         # ----------------------------------------
        
#         # State Variables
#         self.app_running = False
#         self.prev_local_frame_time = 0.0
#         self.last_confirmed_gesture_key = "NO_HAND"
#         self.current_potential_gesture_key = "NO_HAND"
#         self.gesture_stability_count = 0
#         self.last_dispatched_robot_command = "STOP"
#         self.last_announced_command_for_tts = "INIT_TTS"
#         self.is_tts_actively_speaking_for_vcp_suppression = False
#         self.robot_pov_window_name = "Robot POV"

#     # The handle_incoming_command_from_source method and run() loop logic remain
#     # exactly as you provided in your last message, as you said they were working.
#     # The only change needed is how the video frames are retrieved in run().
#     def handle_incoming_command_from_source(self, command_to_dispatch, source_type):
#         if command_to_dispatch is None or command_to_dispatch == "UNKNOWN_COMMAND": return
#         if command_to_dispatch == "NO_ACTION":
#             if self.last_dispatched_robot_command not in ["STOP", "NO_ACTION"]:
#                 command_to_dispatch = "STOP"
#             else:
#                 self.last_dispatched_robot_command = "STOP"
#                 if self.pygame_visualizer: self.pygame_visualizer.update_robot_state("STOP")
#                 return
#         if self.tts_manager and (command_to_dispatch != self.last_announced_command_for_tts or source_type == "voice"):
#             phrase = self.tts_phrases.get(command_to_dispatch)
#             if phrase:
#                 if self.voice_command_processor:
#                     self.voice_command_processor.set_suppress(True)
#                     self.is_tts_actively_speaking_for_vcp_suppression = True
#                 self.tts_manager.speak(phrase)
#             self.last_announced_command_for_tts = command_to_dispatch
#         self.last_dispatched_robot_command = command_to_dispatch

#     def run(self):
#         if not self.local_cam_manager.start_camera():
#             print("FATAL: Failed to start local camera. Exiting."); self.cleanup(); return
#         if self.voice_command_processor: self.voice_command_processor.start_listening()
        
#         print("INFO: Press 'q' in 'Gesture Control UX' window or close Pygame window to quit.")
#         self.app_running = True
#         self.prev_local_frame_time = time.time()
        
#         try:
#             while self.app_running:
#                 if self.pygame_visualizer:
#                     self.pygame_visualizer.handle_input()
#                     if not self.pygame_visualizer.is_running: self.app_running = False; break
                
#                 local_frame = self.local_cam_manager.get_frame()
#                 if local_frame is None: self.app_running = False; break
                
#                 current_time = time.time()
#                 fps = 1/(current_time - self.prev_local_frame_time) if (current_time - self.prev_local_frame_time) > 0 else 0
#                 self.prev_local_frame_time = current_time
                
#                 flipped_frame = cv2.flip(local_frame, 1); rgb_frame = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
#                 self.hand_detector.find_hands(rgb_frame)
#                 landmarks, handedness = self.hand_detector.get_landmarks()
#                 display_frame = flipped_frame.copy()
                
#                 current_gesture = "NO_HAND"
#                 if landmarks and handedness:
#                     display_frame = self.hand_detector.draw_landmarks(display_frame, landmarks[0])
#                     current_gesture = self.gesture_classifier.classify(landmarks[0], handedness[0].classification[0].label)
                
#                 if current_gesture == self.current_potential_gesture_key: self.gesture_stability_count +=1
#                 else: self.current_potential_gesture_key = current_gesture; self.gesture_stability_count = 1
                
#                 if self.gesture_stability_count >= GESTURE_CONFIRM_FRAMES and \
#                    self.last_confirmed_gesture_key != self.current_potential_gesture_key:
#                     self.last_confirmed_gesture_key = self.current_potential_gesture_key
#                     cmd = self.action_mapper.get_command(self.last_confirmed_gesture_key)
#                     self.handle_incoming_command_from_source(cmd, "gesture")

#                 if self.tts_manager and self.voice_command_processor and self.is_tts_actively_speaking_for_vcp_suppression:
#                     if not self.tts_manager.is_busy():
#                         self.voice_command_processor.set_suppress(False); self.is_tts_actively_speaking_for_vcp_suppression = False
                
#                 if self.pygame_visualizer: self.pygame_visualizer.update_robot_state(self.last_dispatched_robot_command)
                
#                 if self.command_sender: self.command_sender.send(self.last_dispatched_robot_command)

#                 cv2.putText(display_frame, f"FPS: {int(fps)}", (20,30), FONT, FONT_SCALE, COLOR_GREEN, FONT_THICKNESS)
#                 cv2.putText(display_frame, f"Gesture: {self.last_confirmed_gesture_key}", (20,60), FONT, FONT_SCALE, COLOR_RED, FONT_THICKNESS)
#                 cv2.putText(display_frame, f"Cmd: {self.last_dispatched_robot_command}", (20,90), FONT, FONT_SCALE, COLOR_ORANGE, FONT_THICKNESS)
#                 cv2.imshow('Gesture Control UX (Local Cam)', display_frame)
                
#                 # --- VIDEO STREAM HANDLING CHANGE ---
#                 if self.robot_video_client:
#                     # The new client runs in a background thread, so we just get the latest frame.
#                     # No connection checks are needed here because get_frame() will just return None if nothing is new.
#                     pov_frame = self.robot_video_client.get_frame() 
                    
#                     if pov_frame is not None:
#                         # Ensure the window exists. If user closed it, this will recreate it.
#                         try:
#                             if cv2.getWindowProperty(self.robot_pov_window_name, cv2.WND_PROP_VISIBLE) < 1:
#                                 cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
#                         except cv2.error: 
#                             cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
                        
#                         h, w = pov_frame.shape[:2]; ar_x, ar_y = w//2, h//2
                        
#                         action_for_ar = self.last_dispatched_robot_command
#                         if action_for_ar == "STOP": draw_stop_symbol(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE)
#                         elif action_for_ar == "GO_FORWARD": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "UP", COLOR_GREEN)
#                         elif action_for_ar == "MOVE_BACKWARD": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "DOWN", COLOR_BLUE)
#                         elif action_for_ar == "TURN_RIGHT": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "RIGHT", COLOR_YELLOW_AR)
#                         elif action_for_ar == "TURN_LEFT": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "LEFT", COLOR_YELLOW_AR)
                        
#                         cv2.imshow(self.robot_pov_window_name, pov_frame)
#                 # ------------------------------------
                
#                 if self.pygame_visualizer: self.pygame_visualizer.draw(f"Sim Cmd: {self.last_dispatched_robot_command}")
                
#                 if cv2.waitKey(1) & 0xFF == ord('q'): self.app_running = False; break
#         except Exception as e:
#             print(f"FATAL ERROR in MainApplication run loop: {e}"); traceback.print_exc()
#         finally:
#             self.cleanup()

#     def cleanup(self):
#         print("END: Cleaning up resources...")
#         if self.local_cam_manager: self.local_cam_manager.release_camera()
#         if self.robot_video_client: self.robot_video_client.close()
#         if self.hand_detector: self.hand_detector.close()
#         if self.command_sender: self.command_sender.close()
#         if self.pygame_visualizer: self.pygame_visualizer.close()
#         if self.tts_manager: self.tts_manager.stop()
#         if self.voice_command_processor: self.voice_command_processor.stop_listening()
#         cv2.destroyAllWindows()
#         print("END: Cleanup complete.")

# if __name__ == '__main__':
#     app = MainApplication()
#     app.run()

# # Imports 
# import cv2 # For camera
# import time # For timing and FPS calculations
# import os # For file path management
# import pygame # For Pygame visualization
# import traceback # For detailed error printing
# import numpy as np # For drawing shapes like arrows
# import json # For loading TTS phrases and modality such as gestures and voice commands

# # Project-specific imports
# from gesture_recognition.camera_manager import CameraManager
# from gesture_recognition.hand_detector import HandDetector
# from gesture_recognition.gesture_classifier import GestureClassifier
# from gesture_recognition.action_mapper import ActionMapper
# from network_communication.command_sender import CommandSender
# from pygame_visualizer import PygameVisualizer
# from video_stream_client import VideoStreamClient
# from tts_manager import TTSManager
# from voice_command_processor import VoiceCommandProcessor

# # --- Configuration Constants ---
# LOCAL_CAMERA_ID = 0 # Macbook Camera's ID
# TARGET_IP_FOR_COMMANDS = "192.168.68.105" # IP of the Raspberry Pi
# TARGET_PORT_FOR_COMMANDS = 5005 

# RPI_VIDEO_SERVER_IP = "192.168.68.105" # IP of the Raspberry Pi 
# RPI_VIDEO_SERVER_PORT = 8485 
# ENABLE_ROBOT_VIDEO_STREAM = False # Set True to view robot's camera feed
# CONFIG_FILE_PATH = os.path.join("config", "gestures_config.json") 

# ENABLE_TTS = True # Set True to enable Text-to-Speech
# TTS_PHRASES_CONFIG_PATH = os.path.join("config", "tts_phrases.json")

# ENABLE_VOICE_COMMANDS = True # Set True to enable voice control
# ENABLE_PYGAME_VISUALIZER = True # Set True to enable Pygame visualizer for dummy robot

# GESTURE_CONFIRM_FRAMES = 3

# # Customizable AR Overlay Configuration for Robot's POV
# AR_ROBOT_POV_POSITION_TYPE = "CENTER"
# AR_SYMBOL_SIZE = 80

# # --- OpenCV Font Constants ---
# FONT, FONT_SCALE, FONT_THICKNESS = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
# COLOR_GREEN, COLOR_RED, COLOR_BLUE = (0, 255, 0), (0, 0, 255), (255, 0, 0)
# COLOR_ORANGE, COLOR_WHITE, COLOR_YELLOW_AR = (0, 165, 255), (255, 255, 255), (0, 200, 200)

# # --- Function to Load TTS Phrases from JSON ---
# def load_tts_phrases(config_path):
#     try:
#         with open(config_path, 'r') as f: phrases = json.load(f)
#         print(f"INFO: Loaded TTS phrases from: {config_path}"); return phrases
#     except Exception as e: print(f"ERROR: Loading TTS from {config_path}: {e}"); return {}

# # --- AR Drawing Functions ---
# # Draws a stop symbol (red circle with white cross) at the specified center and size
# def draw_stop_symbol(image, center_x, center_y, size):
#     radius = size // 2; cv2.circle(image, (center_x, center_y), radius, COLOR_RED, -1)
#     offset = int(radius * 0.6)
#     cv2.line(image, (center_x - offset, center_y - offset), (center_x + offset, center_y + offset), COLOR_WHITE, 3)
#     cv2.line(image, (center_x - offset, center_y + offset), (center_x + offset, center_y - offset), COLOR_WHITE, 3)
    
# # Draws an arrow in the specified direction with the given size and color
# # Directions: "UP", "DOWN", "LEFT", "RIGHT"
# def draw_arrow(image, center_x, center_y, size, direction, color):
#     s = size // 2
#     if direction == "UP": pts = np.array([[center_x, center_y - s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y + s//2], [center_x + s//4, center_y + s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
#     elif direction == "DOWN": pts = np.array([[center_x, center_y + s], [center_x - s//2, center_y], [center_x - s//4, center_y], [center_x - s//4, center_y - s//2], [center_x + s//4, center_y - s//2], [center_x + s//4, center_y], [center_x + s//2, center_y]], np.int32)
#     elif direction == "RIGHT": pts = np.array([[center_x + s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x - s//2, center_y - s//4], [center_x - s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
#     elif direction == "LEFT": pts = np.array([[center_x - s, center_y], [center_x, center_y - s//2], [center_x, center_y - s//4], [center_x + s//2, center_y - s//4], [center_x + s//2, center_y + s//4], [center_x, center_y + s//4], [center_x, center_y + s//2]], np.int32)
#     else: return
#     cv2.drawContours(image, [pts], 0, color, -1)

# # MainApplication class that initializes and runs the application
# # It manages the camera, gesture detection, command sending, and Pygame visualization.
# # It also handles TTS and voice commands if enabled.
# class MainApplication:
#     def __init__(self):
#         # --- Component Initialization ---
#         # This is the main initialization method for the application.
#         # It sets up all the components needed for gesture recognition, command sending, and visualization.
#         # It also initializes the TTS manager and voice command processor if enabled.
#         # It also sets up the robot video client if the video stream is enabled.
#         print("MainApplication: Initializing components...")
#         self.local_cam_manager = CameraManager(camera_id=LOCAL_CAMERA_ID)
#         self.hand_detector = HandDetector(max_hands=1)
#         self.gesture_classifier = GestureClassifier()
#         self.action_mapper = ActionMapper(config_file_path=CONFIG_FILE_PATH)
#         self.command_sender = CommandSender(target_ip=TARGET_IP_FOR_COMMANDS, target_port=TARGET_PORT_FOR_COMMANDS)
#         self.pygame_visualizer = PygameVisualizer() if ENABLE_PYGAME_VISUALIZER else None
#         self.tts_manager = TTSManager(voice="Alex", rate=190) if ENABLE_TTS else None
#         self.tts_phrases = load_tts_phrases(TTS_PHRASES_CONFIG_PATH) if ENABLE_TTS else {}
#         self.voice_command_processor = VoiceCommandProcessor() if ENABLE_VOICE_COMMANDS else None
        
#         if self.voice_command_processor:
#             self.voice_command_processor.set_command_callback(self.handle_incoming_command_from_source)
#         self.robot_video_client = None
#         # If the robot video stream is enabled, we attempt to connect to the video server.
#         # If the connection fails, we log a warning but continue running the application.
#         # If the connection is successful, we log an info message.
#         # If the video stream is disabled, we log an info message.
#         if ENABLE_ROBOT_VIDEO_STREAM:
#             print(f"INFO: Attempting connection to video server at {RPI_VIDEO_SERVER_IP}:{RPI_VIDEO_SERVER_PORT}")
#             self.robot_video_client = VideoStreamClient(host_ip=RPI_VIDEO_SERVER_IP, port=RPI_VIDEO_SERVER_PORT)
#             if not self.robot_video_client.connect(): print("CAMERA: Initial video stream connection failed.")
#             else: print("CAMERA: Video stream connection successful.")
#         else: print("CAMERA: Robot Video Stream is DISABLED.")
        
#         # --- State Variables ---
#         # These variables track the state of the application, including whether it is running,
#         # the last confirmed gesture, the current potential gesture, and the stability count for gestures.
#         # They also track the last dispatched robot command and the last announced command for TTS.
#         # The TTS suppression state is also tracked to manage voice command processing during TTS announcements
#         self.app_running = False
#         self.prev_local_frame_time = 0.0
#         self.last_confirmed_gesture_key = "NO_HAND"
#         self.current_potential_gesture_key = "NO_HAND"
#         self.gesture_stability_count = 0
#         self.last_dispatched_robot_command = "STOP"
#         self.last_announced_command_for_tts = "INIT_TTS"
#         self.is_tts_actively_speaking_for_vcp_suppression = False
        
#         self.robot_pov_window_name = "Robot POV"
#         # End of initialisation section

#     def handle_incoming_command_from_source(self, command_to_dispatch, source_type):
#         # This method is correct from the last version. No changes needed here.
#         if command_to_dispatch is None or command_to_dispatch == "UNKNOWN_COMMAND": return
#         if command_to_dispatch == "NO_ACTION":
#             if self.last_dispatched_robot_command not in ["STOP", "NO_ACTION"]:
#                 command_to_dispatch = "STOP"
#             else:
#                 self.last_dispatched_robot_command = "STOP"
#                 if self.pygame_visualizer: self.pygame_visualizer.update_robot_state("STOP")
#                 return
        
#         if self.tts_manager and (command_to_dispatch != self.last_announced_command_for_tts or source_type == "voice"):
#             phrase = self.tts_phrases.get(command_to_dispatch)
#             if phrase:
#                 if self.voice_command_processor:
#                     self.voice_command_processor.set_suppress(True)
#                     self.is_tts_actively_speaking_for_vcp_suppression = True
#                 self.tts_manager.speak(phrase)
#             self.last_announced_command_for_tts = command_to_dispatch
        
#         # Update the state. The main loop will handle sending and simulation.
#         self.last_dispatched_robot_command = command_to_dispatch

#     def run(self):
#         if not self.local_cam_manager.start_camera():
#             print("FATAL: Failed to start local camera. Exiting."); self.cleanup(); return
#         if self.voice_command_processor: self.voice_command_processor.start_listening()
        
#         print("INFO: Press 'q' in 'Gesture Control UX' window or close Pygame window to quit.")
#         self.app_running = True
#         self.prev_local_frame_time = time.time()
        
#         # If the robot video client is connected, we create a window for the robot's POV.
#         # If the window creation fails, we log an error but continue running the application.
#         # If the robot video client is not connected, we log an info message.
#         # If the robot video stream is disabled, we do not create the window.
#         # This allows the application to run without the robot video stream if it is not enabled.
#         if self.robot_video_client and self.robot_video_client.is_connected:
#             try: cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
#             except Exception as e: print(f"ERROR: Creating Robot POV window: {e}")

#         try:
#             # Main application loop
#             # This loop runs until the application is stopped, either by user input or an error.
#             # It handles input from the Pygame visualizer, processes the local camera frame for gesture recognition,
#             # classifies gestures, updates the Pygame visualizer, and sends commands to the robot.
#             # It also displays the local camera frame with gesture information and the robot's POV with AR overlays.
#             # The loop also handles quitting the application when the user presses 'q' or closes the Pygame window.
#             while self.app_running:
#                 if self.pygame_visualizer:
#                     self.pygame_visualizer.handle_input()
#                     if not self.pygame_visualizer.is_running: self.app_running = False; break
                
#                 # Get the local camera frame for gesture recognition
#                 local_frame = self.local_cam_manager.get_frame()
#                 if local_frame is None: self.app_running = False; break
                
#                 # Calculate FPS for the local camera frame
#                 # This is done by measuring the time taken to process the previous frame.
#                 # If the time difference is zero or negative, we set FPS to 0 to avoid division by zero.
#                 # We then update the previous frame time to the current time for the next iteration.
#                 # The FPS is displayed on the local camera frame for user feedback.
#                 # The local frame is flipped horizontally for a mirror effect and converted to RGB for MediaPipe
#                 # Then, the hand detector processes the frame to find hands and landmarks.
#                 current_time = time.time()
#                 fps = 1/(current_time - self.prev_local_frame_time) if (current_time - self.prev_local_frame_time) > 0 else 0
#                 self.prev_local_frame_time = current_time
                
#                 # Flip the frame for mirror effect
#                 flipped_frame = cv2.flip(local_frame, 1); rgb_frame = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
#                 self.hand_detector.find_hands(rgb_frame)
#                 landmarks, handedness = self.hand_detector.get_landmarks()
#                 display_frame = flipped_frame.copy()
                
#                 # Initialize the current gesture key
#                 # If landmarks and handedness are detected, we draw the landmarks on the display frame
#                 # and classify the gesture using the gesture classifier.
#                 # The classified gesture is compared with the current potential gesture key.
#                 # If they match, we increment the gesture stability count.
#                 # If they do not match, we update the current potential gesture key and reset the stability count.
#                 # If the gesture stability count reaches the confirmation threshold, we confirm the gesture
#                 # and dispatch the corresponding command using the action mapper.
#                 current_gesture = "NO_HAND"
#                 if landmarks and handedness:
#                     display_frame = self.hand_detector.draw_landmarks(display_frame, landmarks[0])
#                     current_gesture = self.gesture_classifier.classify(landmarks[0], handedness[0].classification[0].label)
                
#                 if current_gesture == self.current_potential_gesture_key: self.gesture_stability_count +=1
#                 else: self.current_potential_gesture_key = current_gesture; self.gesture_stability_count = 1
                
#                 if self.gesture_stability_count >= GESTURE_CONFIRM_FRAMES and \
#                    self.last_confirmed_gesture_key != self.current_potential_gesture_key:
#                     self.last_confirmed_gesture_key = self.current_potential_gesture_key
#                     cmd = self.action_mapper.get_command(self.last_confirmed_gesture_key)
#                     self.handle_incoming_command_from_source(cmd, "gesture")

#                 if self.tts_manager and self.voice_command_processor and self.is_tts_actively_speaking_for_vcp_suppression:
#                     if not self.tts_manager.is_busy():
#                         self.voice_command_processor.set_suppress(False); self.is_tts_actively_speaking_for_vcp_suppression = False
                
#                 if self.pygame_visualizer: self.pygame_visualizer.update_robot_state(self.last_dispatched_robot_command)
                
#                 if self.command_sender: self.command_sender.send(self.last_dispatched_robot_command)

#                 # --- UI Updates (Local Camera View) ---
#                 # This section updates the local camera view with FPS, gesture, and command information.
#                 # It uses OpenCV to draw text on the display frame.
#                 # The FPS is displayed in green, the gesture in red, and the command in orange
#                 cv2.putText(display_frame, f"FPS: {int(fps)}", (20,30), FONT, FONT_SCALE, COLOR_GREEN, FONT_THICKNESS)
#                 cv2.putText(display_frame, f"Gesture: {self.last_confirmed_gesture_key}", (20,60), FONT, FONT_SCALE, COLOR_RED, FONT_THICKNESS)
#                 cv2.putText(display_frame, f"Cmd: {self.last_dispatched_robot_command}", (20,90), FONT, FONT_SCALE, COLOR_ORANGE, FONT_THICKNESS)
#                 cv2.imshow('Gesture Control UX (Local Cam)', display_frame)
                
#                 # --- Robot Video Stream and AR Overlays ---
#                 # This section handles the robot's video stream if it is enabled.
#                 # If the robot video stream is enabled, we receive frames from the robot's POV
#                 # and draw AR symbols based on the last dispatched command.
#                 # The AR symbols are drawn at the center of the frame or at a specified position.
#                 # If the robot video client is not connected, we attempt to reconnect every 5 seconds
#                 # and log the connection status.
#                 # If the robot video client is connected, we display the POV frame with AR symbols.
#                 # If the POV frame is None, we log a message indicating that the POV is disconnected
#                 if self.robot_video_client:
#                     if self.robot_video_client.is_connected:
#                         pov_frame = self.robot_video_client.receive_frame()
#                         if pov_frame is not None:
#                             try:
#                                 if cv2.getWindowProperty(self.robot_pov_window_name, cv2.WND_PROP_VISIBLE) < 1:
#                                     cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
#                             except cv2.error: cv2.namedWindow(self.robot_pov_window_name, cv2.WINDOW_NORMAL)
                            
#                             h, w = pov_frame.shape[:2]; ar_x, ar_y = w//2, h//2
                            
#                             action_for_ar = self.last_dispatched_robot_command
#                             if action_for_ar == "STOP": draw_stop_symbol(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE)
#                             elif action_for_ar == "GO_FORWARD": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "UP", COLOR_GREEN)
#                             elif action_for_ar == "MOVE_BACKWARD": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "DOWN", COLOR_BLUE)
#                             elif action_for_ar == "TURN_RIGHT": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "RIGHT", COLOR_YELLOW_AR)
#                             elif action_for_ar == "TURN_LEFT": draw_arrow(pov_frame, ar_x, ar_y, AR_SYMBOL_SIZE, "LEFT", COLOR_YELLOW_AR)
                            
#                             cv2.imshow(self.robot_pov_window_name, pov_frame)
#                         elif not self.robot_video_client.is_connected: print("INFO: Robot POV disconnected.")
#                     else:
#                         if time.time() % 5 < 0.1: 
#                             if self.robot_video_client.connect(): print("INFO: Robot POV reconnected.")
                
#                 if self.pygame_visualizer: self.pygame_visualizer.draw(f"Sim Cmd: {self.last_dispatched_robot_command}")
                
#                 if cv2.waitKey(1) & 0xFF == ord('q'): self.app_running = False; break
#         except Exception as e:
#             print(f"FATAL ERROR in MainApplication run loop: {e}"); traceback.print_exc()
#         finally:
#             self.cleanup()

#         # This method is called when the application is stopped.
#         # It cleans up all resources, including the local camera, robot video client, hand detector,
#         # command sender, Pygame visualizer, TTS manager, and voice command processor.
#         # It also destroys all OpenCV windows to ensure a clean exit.
#         # It logs a message indicating that the cleanup is complete.
#         # This ensures that all resources are properly released and the application exits cleanly.
#     def cleanup(self):
#         print("END: Cleaning up resources...")
#         if self.local_cam_manager: self.local_cam_manager.release_camera()
#         if self.robot_video_client: self.robot_video_client.close()
#         if self.hand_detector: self.hand_detector.close()
#         if self.command_sender: self.command_sender.close()
#         if self.pygame_visualizer: self.pygame_visualizer.close()
#         if self.tts_manager: self.tts_manager.stop()
#         if self.voice_command_processor: self.voice_command_processor.stop_listening()
#         cv2.destroyAllWindows()
#         print("END: Cleanup complete.")

# if __name__ == '__main__':
#     app = MainApplication()
#     app.run()
    
#------------------------------------------------------END!----------------------------------------------------------------------------
