# voice_command_processor.py

# Imports
from vosk import Model, KaldiRecognizer
import pyaudio
import json
import threading
import time
import os
import re

class VoiceCommandProcessor:
    def __init__(self, model_path="models/vosk-model-small-en-us-0.15"): # Path to the Vosk model
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at: {model_path}") # No path found error

        self.model = Model(model_path) # Load the Language model by Vosk
        self.recognizer = KaldiRecognizer(self.model, 16000) # Initialize recognizer with the model and sample rate
        self.audio_interface = pyaudio.PyAudio() # Initialize PyAudio
        self.stream = None # Audio stream for capturing microphone input
        self.command_callback = None # The function to call in the main app when a command is found
        self.is_listening = False # A flag to control the background listening thread
        self.listen_thread = None # The background thread object
        self.suppress_recognition = False # A "mute" flag, used when TTS is speaking
        self.last_command = None # Remembers the last command to prevent spamming
        self.last_trigger_time = 0
        self.command_throttle_sec = 0.75  # prevent spamming

    # Allows the main application to provide a function to be called with recognized commands
    def set_command_callback(self, callback_function):
        self.command_callback = callback_function

    # Suppress speech recognition when TTS is speaking
    def set_suppress(self, should_suppress):
        self.suppress_recognition = should_suppress

    # Start listening for voice commands
    def start_listening(self):
        if self.is_listening:
            return
        try:
            # Accesses the microphone hardware on your device
            # with the default sample rate of 16000 Hz and 8000 of audio frames per buffer
            self.stream = self.audio_interface.open(format=pyaudio.paInt16,
                                                    channels=1,
                                                    rate=16000,
                                                    input=True,
                                                    frames_per_buffer=8000)
            self.stream.start_stream() # Starts the flow of data from the mic
            self.is_listening = True # Set the flag to indicate that we are listening
            
            # This shows that the actual listening happens in a separate
            # "daemon" thread. So, the main application doesn't freeze while waiting for user to speak.
            self.listen_thread = threading.Thread(target=self._listen_and_process, daemon=True)
            self.listen_thread.start()
            print("VCP (Vosk): Listening started.")
        except Exception as e:
            print(f"VCP (Vosk) ERROR: Could not start audio stream: {e}")
            self.stream = None
            self.is_listening = False

    # Stops the listening thread and cleanly closes all audio resources.
    def stop_listening(self):
        self.is_listening = False
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2.0)
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        # Terminate PyAudio instance on stop to release system resources
        if self.audio_interface:
            self.audio_interface.terminate() # Release audio system resources
        print("VCP (Vosk): Listening stopped and resources released.")

    # Runs continuously in a separate thread to listen for voice commands
    def _listen_and_process(self):
        while self.is_listening:
            if self.suppress_recognition:
                time.sleep(0.01)
                continue
            
            try:
                # Read a small chunk of raw audio data from the microphone.
                data = self.stream.read(4000, exception_on_overflow=False)

                # Fast command detection with partial result
                # `AcceptWaveform` returns TRUE only when it detects a pause (end of a sentence).
                if self.recognizer.AcceptWaveform(data):
                    # Use full result when a pause is detected
                    # At this point, we get the FINAL, most accurate transcription.
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip().lower()
                else:
                    # Use partial result for immediate feedback
                    # But if it returns FALSE, it means user is still speaking.
                    # We can get the PARTIAL transcription of what user said so far.
                    # This is for better responsiveness.
                    partial_result = json.loads(self.recognizer.PartialResult())
                    text = partial_result.get("partial", "").strip().lower()
                
                # If any transcribed text (partial or full) was recognized
                if text:
                    command = self._parse_command(text) # Translate the text to a robot command
                    self._trigger_command(command, text) # If a valid command was found, trigger it

            # Error handling
            except (IOError, OSError) as e:
                print(f"VCP (Vosk) ERROR: Audio stream read failed: {e}. Stopping listener.")
                self.is_listening = False # Stop the loop on stream error
                break
            except Exception as e:
                print(f"VCP (Vosk) ERROR: Unexpected error in listen loop: {e}")
                
            time.sleep(0.005)

    # This is a "spam filter". It decides if a recognized command should actually be sent.
    def _trigger_command(self, command, source_text):
        current_time = time.time()
        # Trigger if the command is valid AND it's different from the last one OR enough time has passed
        if command and (command != self.last_command or current_time - self.last_trigger_time > self.command_throttle_sec):
            print(f"VCP (Vosk): Matched '{command}' from '{source_text}'")
            self.last_command = command
            self.last_trigger_time = current_time
            if self.command_callback:
                self.command_callback(command, "voice")

    # Parses the recognized text into a standardized robot command string.
    # It uses a dictionary to map keywords to commands and adds a '_VOICE' suffix
    # so the robot can use a different speed than the one in gestures.
    def _parse_command(self, text):
        command_mappings = {
            # Universal commands that don't need different speeds
            "STOP": ["stop", "halt", "pause", "stay", "cease"],
            
            # Python Dictionary to map phrases to commands
            # Movement commands that will get a "_VOICE" suffix
            "TURN_LEFT_VOICE": ["turn left", "go left", "left turn", "move left", "left"],
            "TURN_RIGHT_VOICE": ["turn right", "go right", "right turn", "move right", "right"],
            "MOVE_BACKWARD_VOICE": ["move backward", "go backward", "backward", "back up", "reverse", "backwards", "back"],
            "GO_FORWARD_VOICE": ["go forward", "move forward", "forward", "go", "move", "ahead", "straight"]
        }

        # Iterate through the dictionary to find a matching command
        for command, phrases in command_mappings.items():
            # Sort phrases by length (descending) to match longer phrases first (e.g., "turn left" before "left")
            for phrase in sorted(phrases, key=len, reverse=True):
                # Use a regular expression to match whole words only.
                # Use word boundaries (\b) to prevent partial matches (e.g., "leftover" matching "left")
                pattern = r'\b' + re.escape(phrase) + r'\b'
                if re.search(pattern, text):
                    # If a match is found, return the standardized command immediately.
                    return command

        # If no keywords were found in the recognized text, return nothing.
        return None