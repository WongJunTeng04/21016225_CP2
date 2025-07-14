# voice_command_processor.py
# Import necessary libraries
import speech_recognition as sr
import threading
import time
import traceback

# The VoiceCommandProcessor class handles voice command recognition using the SpeechRecognition library.
# It listens for voice commands through the microphone, processes them, and calls a callback function with
# the recognized command. It supports dynamic energy threshold adjustment, phrase time limits, and
# suppression of recognition based on external conditions.

class VoiceCommandProcessor:
    # Initializes the VoiceCommandProcessor with default parameters.
    # Parameters:
    # language: Language code for speech recognition (default "en-US")
    # energy_threshold: Initial energy threshold for recognizing speech (default 400)
    # pause_threshold: Duration of silence that indicates the end of a phrase (default 0.8 seconds)
    # phrase_time_limit: Maximum duration of a phrase to listen for (default 5 seconds)
    # Initializes the recognizer, microphone, and various settings for speech recognition.
    def __init__(self, language="en-US", energy_threshold=400, pause_threshold=0.8, phrase_time_limit=5):
        self.recognizer = sr.Recognizer()
        self.microphone = None # Initialize as None, will be set in start_listening
        self.language = language
        
        # Recognizer settings
        self.recognizer.energy_threshold = energy_threshold # Initial threshold
        self.recognizer.pause_threshold = pause_threshold   # How long a silence indicates end of phrase
        self.recognizer.dynamic_energy_threshold = True     # Adapts to ambient noise
        self.phrase_time_limit = phrase_time_limit         # Max duration of a phrase to listen for

        self.is_listening = False
        self.listen_thread = None
        self.command_callback = None

        self.suppress_recognition = False
        self.suppress_lock = threading.Lock()
        # print("VCP INFO: VoiceCommandProcessor initialized.")

    def set_command_callback(self, callback_function):
        self.command_callback = callback_function

    def set_suppress(self, should_suppress):
        with self.suppress_lock:
            if self.suppress_recognition != should_suppress:
                 # print(f"VCP INFO: Suppression set to {should_suppress}") # Optional: for debugging suppression
                 pass
            self.suppress_recognition = should_suppress

    def _listen_and_process(self):
        # print("VCP INFO: _listen_and_process thread started.")
        
        while self.is_listening:
            with self.suppress_lock:
                if self.suppress_recognition:
                    time.sleep(0.1) # Yield if suppressed
                    continue
            
            # Check if microphone is initialized
            # Debug code
            if not self.microphone:
                # print("VCP ERROR: Microphone instance is not available in listening loop.")
                time.sleep(1) # Wait before retrying to initialize
                if self.is_listening: # Only try to re-init if still supposed to be listening
                    self._initialize_microphone_and_calibrate() # Try to re-init
                continue

            audio_data = None
            try:
                with self.microphone as source:
                    # print("VCP INFO: Listening for a voice command...") # Can be noisy
                    audio_data = self.recognizer.listen(
                        source, 
                        timeout=2.0, # How long to wait for speech to start before giving up for this cycle
                        phrase_time_limit=self.phrase_time_limit
                    )
            except sr.WaitTimeoutError:
                # This is expected if no speech occurs
                pass 
            except AttributeError as ae:
                # print(f"VCP ERROR: AttributeError during listen (microphone issue?): {ae}")
                self.microphone = None # Mark microphone as needing re-initialization
                time.sleep(0.5)
            except Exception as e:
                # print(f"VCP ERROR: Unexpected error during sr.listen: {e}")
                # traceback.print_exc() # Uncomment for full details if needed
                time.sleep(0.5) # Pause if errors occur

            if not self.is_listening: # Check if stop_listening was called during listen()
                break

            if audio_data:
                with self.suppress_lock: # Check suppression again before network call
                    if self.suppress_recognition:
                        continue
                try:
                    # print("VCP INFO: Audio captured, sending to Google for recognition...") # Can be noisy
                    recognized_text = self.recognizer.recognize_google(
                        audio_data, 
                        language=self.language
                    )
                    recognized_text = recognized_text.lower()
                    print(f"VCP INFO: Voice detected -> '{recognized_text}'")
                    
                    command_to_send = self._parse_command(recognized_text)
                    if command_to_send:
                        if self.command_callback:
                            self.command_callback(command_to_send, "voice")
                        else:
                            print(f"VCP WARNING: Command '{command_to_send}' parsed but no callback set.")
                    # else:
                        # print(f"VCP INFO: No specific command parsed from '{recognized_text}'.")

                except sr.UnknownValueError:
                    # print("VCP INFO: Google Speech Recognition could not understand audio.")
                    pass # Common, just means speech wasn't clear or wasn't understood
                except sr.RequestError as e:
                    print(f"VCP ERROR: Google STT request failed; {e}.")
                except Exception as e:
                    print(f"VCP ERROR: Unexpected error processing recognized text: {e}")
                    # traceback.print_exc()
            
            time.sleep(0.02) # Small sleep to yield CPU, especially if listen times out quickly

        # print("VCP INFO: _listen_and_process thread finished.")

    def _initialize_microphone_and_calibrate(self):
        # print("VCP INFO: Attempting to initialize microphone and calibrate...")
        mic_initialized = False
        try:
            # Always create a new Microphone instance if needed or re-calibrating
            self.microphone = sr.Microphone() 
            with self.microphone as source:
                # print("VCP INFO: Calibrating for ambient noise (0.7s)... Please be quiet.")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.7)
            # print("VCP INFO: Microphone calibrated.")
            mic_initialized = True
        except AttributeError as ae: # Common if sr.Microphone() itself fails due to PortAudio issues
            #  print(f"VCP ERROR: AttributeError during microphone init/calibration: {ae}")
             # traceback.print_exc()
             self.microphone = None # Ensure it's None if failed
        except Exception as e:
            print(f"VCP ERROR: Microphone initialization/calibration failed: {e}")
            # traceback.print_exc()
            self.microphone = None
        return mic_initialized

    # Starts the listening thread if not already running.
    # This method initializes the microphone and calibrates it for ambient noise.
    # It sets the suppress flag to False to ensure recognition is active.
    # If the microphone initialization fails, it logs an error and does not start the thread.
    # This method is thread-safe and can be called from any thread.
    # It also handles cases where the thread might not have been started or is already running.
    # If the thread is already running, it does nothing.
    # If the microphone is None, it attempts to initialize it.
    # If the microphone initialization fails, it logs an error and does not start the thread.
    def start_listening(self):
        if self.is_listening:
            # print("VCP INFO: Already listening.")
            return
        
        if not self._initialize_microphone_and_calibrate():
            print("VCP ERROR: Failed to initialize microphone. Voice commands will not work.")
            return # Don't start listening thread if mic failed

        self.is_listening = True
        self.set_suppress(False) # Ensure suppression is off when starting
        
        if self.listen_thread is None or not self.listen_thread.is_alive():
            self.listen_thread = threading.Thread(target=self._listen_and_process, daemon=True)
            self.listen_thread.start()
            print("VCP INFO: Listening thread started.")
        else:
            # This state should ideally not be reached if logic is correct
            print("VCP WARNING: start_listening called but thread already alive and is_listening was false.")


    # Stops the listening thread and releases the microphone.
    # This method ensures that the thread is stopped cleanly and the microphone is released.
    # It waits for the thread to finish before returning.
    # If the thread does not stop in a reasonable time, it logs a warning.
    # If the microphone is None, it does nothing.
    # This method is thread-safe and can be called from any thread.
    # It also handles cases where the thread might not have been started or is already stopped.
    def stop_listening(self):
        # print("VCP INFO: stop_listening called.")
        if not self.is_listening and not (self.listen_thread and self.listen_thread.is_alive()):
            return # Not listening or thread already gone
        
        self.is_listening = False 
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2.0) # Increased timeout for listen() to complete
            if self.listen_thread.is_alive():
                print("VCP WARNING: Listener thread did not stop cleanly in time.")
        self.microphone = None # Release microphone instance explicitly
        # print("VCP INFO: Stopped listening.")

    # Parses the recognized text to determine the command.
    # This method looks for specific keywords in the text to identify commands.
    # It returns a command string that can be used by the callback function.
    # If no command is recognized, it returns None.
    # This method is case-insensitive and handles variations in phrasing.
    # It supports commands like "forward", "backward", "left", "right",
    # "stop".
    def _parse_command(self, text):
        # print(f"VCP DEBUG: Parsing text: '{text}'") # Keep for specific parsing debug
        if "forward" in text or \
           ("go" in text and not any(x in text for x in ["backward","left","right","stop"])) or \
           ("move" in text and "front" in text):
            return "GO_FORWARD"
        elif "backward" in text or "back up" in text or "reverse" in text:
            return "MOVE_BACKWARD"
        elif "left" in text: # "turn left" or just "left"
            return "TURN_LEFT"
        elif "right" in text: # "turn right" or just "right"
            return "TURN_RIGHT"
        elif "stop" in text or "halt" in text or "stay" in text:
            return "STOP"
        
        # elif "follow me" in text or "track hand" in text or "start following" in text:
        #     return "START_FOLLOW_PERSON"
        # elif "stop following" in text or "manual mode" in text or "cancel follow" in text:
        #     return "STOP_AUTONOMOUS"  # Example for autonomous mode
        return None

# Standalone test for the VoiceCommandProcessor class.
# This test initializes the processor, sets a callback function, and starts listening for commands.
# It prints recognized commands to the console.
# The test runs until interrupted by the user (Ctrl+C).
# It can be used to verify that the voice command recognition works independently of other components.
if __name__ == '__main__':
    def test_callback(command, source):
        print(f"--- Standalone Test Callback: Cmd='{command}', Src='{source}' ---")

    vcp_test = VoiceCommandProcessor(energy_threshold=400) # Try adjusting threshold
    vcp_test.set_command_callback(test_callback)
    
    print("Starting VCP standalone test. Say commands. Press Ctrl+C to quit.")
    vcp_test.start_listening()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStandalone Test: KeyboardInterrupt received.")
    finally:
        print("Standalone Test: Stopping VCP...")
        vcp_test.stop_listening()
        print("Standalone Test: Finished.")
        
        
# # voice_command_processor.py
# # Import necessary libraries
# import speech_recognition as sr
# import threading
# import time
# import traceback

# # The VoiceCommandProcessor class handles voice command recognition using the SpeechRecognition library.
# # It listens for voice commands through the microphone, processes them, and calls a callback function with
# # the recognized command. It supports dynamic energy threshold adjustment, phrase time limits, and
# # suppression of recognition based on external conditions.

# class VoiceCommandProcessor:
#     # Initializes the VoiceCommandProcessor with default parameters.
#     # Parameters:
#     # language: Language code for speech recognition (default "en-US")
#     # energy_threshold: Initial energy threshold for recognizing speech (default 400)
#     # pause_threshold: Duration of silence that indicates the end of a phrase (default 0.8 seconds)
#     # phrase_time_limit: Maximum duration of a phrase to listen for (default 5 seconds)
#     # Initializes the recognizer, microphone, and various settings for speech recognition.
#     def __init__(self, language="en-US", energy_threshold=400, pause_threshold=0.8, phrase_time_limit=5):
#         self.recognizer = sr.Recognizer()
#         self.microphone = None # Initialize as None, will be set in start_listening
#         self.language = language
        
#         # Recognizer settings
#         self.recognizer.energy_threshold = energy_threshold # Initial threshold
#         self.recognizer.pause_threshold = pause_threshold   # How long a silence indicates end of phrase
#         self.recognizer.dynamic_energy_threshold = True     # Adapts to ambient noise
#         self.phrase_time_limit = phrase_time_limit         # Max duration of a phrase to listen for

#         self.is_listening = False
#         self.listen_thread = None
#         self.command_callback = None

#         self.suppress_recognition = False
#         self.suppress_lock = threading.Lock()
#         # print("VCP INFO: VoiceCommandProcessor initialized.")

#     def set_command_callback(self, callback_function):
#         self.command_callback = callback_function

#     def set_suppress(self, should_suppress):
#         with self.suppress_lock:
#             if self.suppress_recognition != should_suppress:
#                  # print(f"VCP INFO: Suppression set to {should_suppress}") # Optional: for debugging suppression
#                  pass
#             self.suppress_recognition = should_suppress

#     def _listen_and_process(self):
#         # print("VCP INFO: _listen_and_process thread started.")
        
#         while self.is_listening:
#             with self.suppress_lock:
#                 if self.suppress_recognition:
#                     time.sleep(0.1) # Yield if suppressed
#                     continue
            
#             # Check if microphone is initialized
#             # Debug code
#             if not self.microphone:
#                 # print("VCP ERROR: Microphone instance is not available in listening loop.")
#                 time.sleep(1) # Wait before retrying to initialize
#                 if self.is_listening: # Only try to re-init if still supposed to be listening
#                     self._initialize_microphone_and_calibrate() # Try to re-init
#                 continue

#             audio_data = None
#             try:
#                 with self.microphone as source:
#                     # print("VCP INFO: Listening for a voice command...") # Can be noisy
#                     audio_data = self.recognizer.listen(
#                         source, 
#                         timeout=2.0, # How long to wait for speech to start before giving up for this cycle
#                         phrase_time_limit=self.phrase_time_limit
#                     )
#             except sr.WaitTimeoutError:
#                 # This is expected if no speech occurs
#                 pass 
#             except AttributeError as ae:
#                 # print(f"VCP ERROR: AttributeError during listen (microphone issue?): {ae}")
#                 self.microphone = None # Mark microphone as needing re-initialization
#                 time.sleep(0.5)
#             except Exception as e:
#                 # print(f"VCP ERROR: Unexpected error during sr.listen: {e}")
#                 # traceback.print_exc() # Uncomment for full details if needed
#                 time.sleep(0.5) # Pause if errors occur

#             if not self.is_listening: # Check if stop_listening was called during listen()
#                 break

#             if audio_data:
#                 with self.suppress_lock: # Check suppression again before network call
#                     if self.suppress_recognition:
#                         continue
#                 try:
#                     # print("VCP INFO: Audio captured, sending to Google for recognition...") # Can be noisy
#                     recognized_text = self.recognizer.recognize_google(
#                         audio_data, 
#                         language=self.language
#                     )
#                     recognized_text = recognized_text.lower()
#                     print(f"VCP INFO: Voice detected -> '{recognized_text}'")
                    
#                     command_to_send = self._parse_command(recognized_text)
#                     if command_to_send:
#                         if self.command_callback:
#                             self.command_callback(command_to_send, "voice")
#                         else:
#                             print(f"VCP WARNING: Command '{command_to_send}' parsed but no callback set.")
#                     # else:
#                         # print(f"VCP INFO: No specific command parsed from '{recognized_text}'.")

#                 except sr.UnknownValueError:
#                     # print("VCP INFO: Google Speech Recognition could not understand audio.")
#                     pass # Common, just means speech wasn't clear or wasn't understood
#                 except sr.RequestError as e:
#                     print(f"VCP ERROR: Google STT request failed; {e}.")
#                 except Exception as e:
#                     print(f"VCP ERROR: Unexpected error processing recognized text: {e}")
#                     # traceback.print_exc()
            
#             time.sleep(0.02) # Small sleep to yield CPU, especially if listen times out quickly

#         # print("VCP INFO: _listen_and_process thread finished.")

#     def _initialize_microphone_and_calibrate(self):
#         # print("VCP INFO: Attempting to initialize microphone and calibrate...")
#         mic_initialized = False
#         try:
#             # Always create a new Microphone instance if needed or re-calibrating
#             self.microphone = sr.Microphone() 
#             with self.microphone as source:
#                 # print("VCP INFO: Calibrating for ambient noise (0.7s)... Please be quiet.")
#                 self.recognizer.adjust_for_ambient_noise(source, duration=0.7)
#             # print("VCP INFO: Microphone calibrated.")
#             mic_initialized = True
#         except AttributeError as ae: # Common if sr.Microphone() itself fails due to PortAudio issues
#             #  print(f"VCP ERROR: AttributeError during microphone init/calibration: {ae}")
#              # traceback.print_exc()
#              self.microphone = None # Ensure it's None if failed
#         except Exception as e:
#             print(f"VCP ERROR: Microphone initialization/calibration failed: {e}")
#             # traceback.print_exc()
#             self.microphone = None
#         return mic_initialized

#     # Starts the listening thread if not already running.
#     # This method initializes the microphone and calibrates it for ambient noise.
#     # It sets the suppress flag to False to ensure recognition is active.
#     # If the microphone initialization fails, it logs an error and does not start the thread.
#     # This method is thread-safe and can be called from any thread.
#     # It also handles cases where the thread might not have been started or is already running.
#     # If the thread is already running, it does nothing.
#     # If the microphone is None, it attempts to initialize it.
#     # If the microphone initialization fails, it logs an error and does not start the thread.
#     def start_listening(self):
#         if self.is_listening:
#             # print("VCP INFO: Already listening.")
#             return
        
#         if not self._initialize_microphone_and_calibrate():
#             print("VCP ERROR: Failed to initialize microphone. Voice commands will not work.")
#             return # Don't start listening thread if mic failed

#         self.is_listening = True
#         self.set_suppress(False) # Ensure suppression is off when starting
        
#         if self.listen_thread is None or not self.listen_thread.is_alive():
#             self.listen_thread = threading.Thread(target=self._listen_and_process, daemon=True)
#             self.listen_thread.start()
#             print("VCP INFO: Listening thread started.")
#         else:
#             # This state should ideally not be reached if logic is correct
#             print("VCP WARNING: start_listening called but thread already alive and is_listening was false.")


#     # Stops the listening thread and releases the microphone.
#     # This method ensures that the thread is stopped cleanly and the microphone is released.
#     # It waits for the thread to finish before returning.
#     # If the thread does not stop in a reasonable time, it logs a warning.
#     # If the microphone is None, it does nothing.
#     # This method is thread-safe and can be called from any thread.
#     # It also handles cases where the thread might not have been started or is already stopped.
#     def stop_listening(self):
#         # print("VCP INFO: stop_listening called.")
#         if not self.is_listening and not (self.listen_thread and self.listen_thread.is_alive()):
#             return # Not listening or thread already gone
        
#         self.is_listening = False 
#         if self.listen_thread and self.listen_thread.is_alive():
#             self.listen_thread.join(timeout=2.0) # Increased timeout for listen() to complete
#             if self.listen_thread.is_alive():
#                 print("VCP WARNING: Listener thread did not stop cleanly in time.")
#         self.microphone = None # Release microphone instance explicitly
#         # print("VCP INFO: Stopped listening.")

#     # Parses the recognized text to determine the command.
#     # This method looks for specific keywords in the text to identify commands.
#     # It returns a command string that can be used by the callback function.
#     # If no command is recognized, it returns None.
#     # This method is case-insensitive and handles variations in phrasing.
#     # It supports commands like "forward", "backward", "left", "right",
#     # "stop".
#     def _parse_command(self, text):
#         # print(f"VCP DEBUG: Parsing text: '{text}'") # Keep for specific parsing debug
#         if "forward" in text or \
#            ("go" in text and not any(x in text for x in ["backward","left","right","stop"])) or \
#            ("move" in text and "front" in text):
#             return "MOVE_FORWARD_CONT"
#         elif "backward" in text or "back up" in text or "reverse" in text:
#             return "MOVE_BACKWARD"
#         elif "left" in text: # "turn left" or just "left"
#             return "TURN_LEFT"
#         elif "right" in text: # "turn right" or just "right"
#             return "TURN_RIGHT"
#         elif "stop" in text or "halt" in text or "stay" in text:
#             return "STOP"
        
#         # elif "follow me" in text or "track hand" in text or "start following" in text:
#         #     return "START_FOLLOW_PERSON"
#         # elif "stop following" in text or "manual mode" in text or "cancel follow" in text:
#         #     return "STOP_AUTONOMOUS"  # Example for autonomous mode
#         return None

# # Standalone test for the VoiceCommandProcessor class.
# # This test initializes the processor, sets a callback function, and starts listening for commands.
# # It prints recognized commands to the console.
# # The test runs until interrupted by the user (Ctrl+C).
# # It can be used to verify that the voice command recognition works independently of other components.
# if __name__ == '__main__':
#     def test_callback(command, source):
#         print(f"--- Standalone Test Callback: Cmd='{command}', Src='{source}' ---")

#     vcp_test = VoiceCommandProcessor(energy_threshold=400) # Try adjusting threshold
#     vcp_test.set_command_callback(test_callback)
    
#     print("Starting VCP standalone test. Say commands. Press Ctrl+C to quit.")
#     vcp_test.start_listening()
    
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\nStandalone Test: KeyboardInterrupt received.")
#     finally:
#         print("Standalone Test: Stopping VCP...")
#         vcp_test.stop_listening()
#         print("Standalone Test: Finished.")