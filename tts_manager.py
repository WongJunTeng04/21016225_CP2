# tts_manager.py
# Imports
import subprocess
import threading
import time
import shlex 
import traceback

class TTSManager:
    # Initialization parameters:
    # voice: str - The voice to use for speech (e.g., "Alex", "Samantha"). Alex used in this case.
    # rate: int - The speech rate in words per minute (default is 180).
    # This class manages text-to-speech using the macOS 'say' command.
    # It handles queuing phrases, debouncing repeated phrases, and running a background thread to process the queue.
    # It also provides methods to check if TTS is busy and to stop the TTS processing.
    def __init__(self, voice=None, rate=180):
        self.voice = voice
        self.rate = rate
        self.last_spoken_phrase = None
        self.last_spoken_time = 0
        self.debounce_interval = 1.5
        self.queue = []
        self.queue_lock = threading.Lock()
        self.speak_thread = None
        self.stop_thread_event = threading.Event()
        self._processing_thread_is_active = False
        self._current_speak_process = None

    def _mark_processing_thread_status(self, is_active):
        """Safely sets the processing thread active status and clears Popen object if inactive."""
        with self.queue_lock:
            self._processing_thread_is_active = is_active
            if not is_active:
                self._current_speak_process = None 

    def _process_queue_say(self):
        self._mark_processing_thread_status(True) # Thread is now active

        try:
            while not self.stop_thread_event.is_set():
                phrase_to_say = None
                with self.queue_lock:
                    if self.queue:
                        phrase_to_say = self.queue.pop(0)
                    elif not self.stop_thread_event.is_set():
                        # Queue is empty, this thread's current batch of work is done.
                        # It will exit the loop naturally now.
                        break 
                
                if phrase_to_say:
                    current_process_for_phrase = None
                    try:
                        command = ["say"]
                        if self.voice: command.extend(["-v", self.voice])
                        if self.rate: command.extend(["-r", str(self.rate)])
                        command.append(phrase_to_say)
                        
                        current_process_for_phrase = subprocess.Popen(command)
                        with self.queue_lock: self._current_speak_process = current_process_for_phrase
                        
                        current_process_for_phrase.wait()

                    except FileNotFoundError:
                        print("TTS ERROR: Command not found.")
                        self.stop_thread_event.set() # Stop further processing
                    except Exception as e:
                        print(f"TTS ERROR: Executing 'say' for '{phrase_to_say}': {e}")
                        # traceback.print_exc() # Keep for deeper debug if needed
                    finally:
                        with self.queue_lock:
                            if self._current_speak_process == current_process_for_phrase:
                                self._current_speak_process = None
                # If phrase_to_say was None (because queue became empty and break was hit), loop terminates.

        finally: # Ensure this is always called when the thread function exits
            self._mark_processing_thread_status(False) # Thread is no longer active

    # Speak method queues a phrase to be spoken.
    # If the same phrase is spoken within the debounce interval, it will not be queued again
    # unless force_speak is True.
    # This method starts a background thread to process the queue if it is not already running.
    def speak(self, phrase, force_speak=False):
        with self.queue_lock: 
            current_time = time.time()
            if not force_speak and phrase == self.last_spoken_phrase and \
               (current_time - self.last_spoken_time < self.debounce_interval):
                return

            self.queue.append(phrase)
            self.last_spoken_phrase = phrase
            self.last_spoken_time = current_time
            
            # Start the processing thread only if our flag indicates it's not currently active
            if not self._processing_thread_is_active:
                if self.speak_thread is not None and self.speak_thread.is_alive():
                    # This means the thread object exists but our flag is false.
                    # This state implies the previous thread might not have cleaned up its flag properly.
                    # We should wait for it to fully terminate.
                    print("TTS WARNING: Old speak_thread object found alive but processing flag was false. Joining.")
                    self.stop_thread_event.set() # Signal any lingering thread to stop
                    self.speak_thread.join(timeout=0.5) # Try to join, short timeout
                    if self.speak_thread.is_alive():
                        print("TTS ERROR: Old speak_thread is stuck and could not be joined. New TTS may fail.")
                        return # Avoid starting a new thread on top of a stuck one.
                
                self.stop_thread_event.clear() 
                self.speak_thread = threading.Thread(target=self._process_queue_say, daemon=True)
                # The thread itself will call _mark_processing_thread_status(True)
                self.speak_thread.start()
                # print(f"TTS INFO: New speak_thread started for phrase: '{phrase}'")
                
    def is_busy(self):
        with self.queue_lock:
            # A Popen object is stored in self._current_speak_process while 'say' is running for an utterance
            is_subprocess_running = False
            if self._current_speak_process:
                is_subprocess_running = self._current_speak_process.poll() is None
            
            # The thread is active if its main loop is running (even if queue is temporarily empty between phrases)
            # The queue having items also means it's busy.
            busy = len(self.queue) > 0 or is_subprocess_running or self._processing_thread_is_active
            # print(f"TTS DEBUG is_busy: {busy} (Q:{len(self.queue)}, SubprocLive:{is_subprocess_running}, ThreadActive:{self._processing_thread_is_active})")
            return busy

    def stop(self):
        # print("TTS INFO: Stop requested.")
        self.stop_thread_event.set() 

        process_to_terminate = None
        with self.queue_lock: 
            self.queue.clear()
            process_to_terminate = self._current_speak_process
            self._current_speak_process = None 

        if process_to_terminate and process_to_terminate.poll() is None:
            try:
                process_to_terminate.terminate()
                process_to_terminate.wait(timeout=0.1)
                if process_to_terminate.poll() is None: process_to_terminate.kill(); process_to_terminate.wait(timeout=0.1)
            except Exception as e: print(f"TTS ERROR: Stopping 'say' process: {e}")
        
        if self.speak_thread and self.speak_thread.is_alive():
            self.speak_thread.join(timeout=0.5) 
            if self.speak_thread.is_alive(): print("TTS WARNING: Speak thread did not join cleanly on stop.")
        
        self._mark_processing_thread_status(False) # Ensure flag is false
        # print("TTS INFO: Stop process completed.")

# Standalone test
if __name__ == '__main__':
    tts_say = TTSManager(voice="Alex", rate=190)
    
    print("TTSManager (macOS 'say' command) Test Suite...")
    
    phrases_to_test = [
        "Hello from the macOS say command.",
        "This is a second test, spoken by Alex.",
        "This is for debouncing.", 
        "This is for debouncing.", 
        "A new phrase after waiting.",
        "Short.", 
        "Another short one.",
        "A slightly longer phrase to see timing."
    ]

    estimated_speech_time = 0
    for i, phrase in enumerate(phrases_to_test):
        print(f"\nMain Test: Speaking phrase {i+1}/{len(phrases_to_test)}: '{phrase}'")
        tts_say.speak(phrase)
        estimated_speech_time += (len(phrase) / 15) + 0.5 
        
        if phrase == phrases_to_test[2]: 
            time.sleep(0.1) 
        elif phrase == phrases_to_test[3]: 
             time.sleep(tts_say.debounce_interval + 0.2)
             print(f"Main Test: (Debounce Test) Attempting to speak '{phrase}' again (should speak now).")
             tts_say.speak(phrase) 
             estimated_speech_time += (len(phrase) / 15) + 0.5
             time.sleep(1.0 + len(phrase) * 0.05) 
        else:
            time.sleep(0.1)


    print(f"\nMain Test: All phrases queued. Est. time: ~{estimated_speech_time:.1f}s. Waiting...")
    count = 0
    max_wait_loops = int((estimated_speech_time + 5) / 0.2) 

    while tts_say.is_busy() and count < max_wait_loops:
        time.sleep(0.2)
        count += 1
        if count % 25 == 0: 
            print(f"  Main Test: Still waiting... (Loop {count})")


    if not tts_say.is_busy():
        print("\nMain Test: TTS successfully reported not busy after all phrases.")
    else:
        print("\nMain Test: TIMEOUT or ERROR - TTS still reports busy after waiting.")
        with tts_say.queue_lock: 
            print(f"  Final state - Queue size: {len(tts_say.queue)}")
            current_proc = tts_say._current_speak_process # Renamed
            print(f"  Final state - Current Popen obj: {current_proc}")
            if current_proc: print(f"  Final state - Popen obj poll: {current_proc.poll()}")
            print(f"  Final state - Processing thread active flag: {tts_say._processing_thread_is_active}") #Renamed

    print("\nMain Test: Calling stop() for final cleanup.")
    tts_say.stop()
    print("Main Test: Done.")
    
    
    
# # tts_manager.py (using macOS 'say' command)
# import subprocess
# import threading
# import time
# import shlex # For safely quoting arguments if needed, though 'say' is often robust
# import traceback # For debugging

# class TTSManager:
#     def __init__(self, voice=None, rate=175): # Rate for 'say' is words per minute
#         self.voice = voice  # e.g., "Alex", "Samantha", "Daniel" (UK English)
#                             # To see available voices: open Terminal and type `say -v ?`
#         self.rate = rate
        
#         self.last_spoken_phrase = None
#         self.last_spoken_time = 0
#         self.debounce_interval = 1.5  # Seconds to wait before repeating the same phrase
        
#         self.queue = []
#         self.speak_thread = None
#         self.current_speak_process = None # To store the Popen object for 'say'
#         self.lock = threading.Lock()
#         self._is_processing_queue_flag = False # To indicate if the processing thread is active

#         print(f"TTSManager (say command) initialized. Voice: {self.voice or 'Default'}, Rate: {self.rate}")

#     def _process_queue(self):
#         # This flag is set True when this thread starts and False when it's about to exit
#         with self.lock:
#             self._is_processing_queue_flag = True

#         try:
#             while True:
#                 phrase_to_say = None
#                 with self.lock:
#                     if self.queue:
#                         phrase_to_say = self.queue.pop(0) # Get the oldest phrase
#                     else:
#                         # No more items, thread will exit
#                         break 

#                 if phrase_to_say:
#                     command = ["say"]
#                     if self.voice:
#                         command.extend(["-v", self.voice])
#                     if self.rate:
#                         command.extend(["-r", str(self.rate)])
                    
#                     # For simple phrases, direct append is usually fine.
#                     # If phrases could contain shell metacharacters, use shlex.quote
#                     command.append(phrase_to_say)
                    
#                     # print(f"TTS (say) Thread: Executing {command}") # For debugging
#                     try:
#                         # Store the process so it can potentially be stopped
#                         with self.lock:
#                             self.current_speak_process = subprocess.Popen(command)
                        
#                         # .wait() makes this part blocking until 'say' finishes for the current phrase
#                         # This ensures phrases are spoken sequentially.
#                         return_code = self.current_speak_process.wait() 
                        
#                         # if return_code != 0: # Optional: check if 'say' command had an error
#                         #     print(f"TTS (say) Thread: 'say' command exited with code {return_code} for phrase: '{phrase_to_say}'")

#                     except FileNotFoundError:
#                         print("TTS (say) Thread: CRITICAL ERROR - 'say' command not found. This should not happen on macOS.")
#                         # If 'say' is not found, there's a big system issue. Stop processing.
#                         with self.lock:
#                             self.queue.clear() # Clear queue as we can't process
#                         break 
#                     except Exception as e_speech:
#                         print(f"TTS (say) Thread: Error during 'say' execution for '{phrase_to_say}': {e_speech}")
#                         traceback.print_exc()
#                     finally:
#                         # Clear the process reference once it's done (or tried)
#                         with self.lock:
#                             self.current_speak_process = None
                
#                 # Brief sleep to allow other threads/main loop to run, especially if queue was briefly empty
#                 time.sleep(0.01) 

#         except Exception as e_thread:
#             print(f"TTS (say) THREAD: FATAL UNHANDLED ERROR in _process_queue: {e_thread}")
#             traceback.print_exc()
#         finally:
#             with self.lock:
#                 self._is_processing_queue_flag = False # Thread is exiting
#             print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
#             print("TTS (say) THREAD: _process_queue FINISHED/EXITED (Normal or Error).")
#             print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

#     def speak(self, phrase, force_speak=False):
#         with self.lock:
#             current_time = time.time()

#             if phrase == self.last_spoken_phrase and \
#                (current_time - self.last_spoken_time < self.debounce_interval) and \
#                not force_speak:
#                 # print(f"TTS (say): Debounced '{phrase}'") # For debugging
#                 return

#             self.queue.append(phrase)
#             # print(f"TTS (say): Queued '{phrase}'. Queue size: {len(self.queue)}") # Debug
#             self.last_spoken_phrase = phrase
#             self.last_spoken_time = current_time
            
#             # Start the processing thread only if it's not already running
#             # and there isn't one already alive from a previous quick succession of calls
#             if not self._is_processing_queue_flag and \
#                (self.speak_thread is None or not self.speak_thread.is_alive()):
#                 # print("TTS (say): Starting speak_thread.") # Debug
#                 self.speak_thread = threading.Thread(target=self._process_queue, daemon=True)
#                 self.speak_thread.name = "SayCommandTTSThread"
#                 self.speak_thread.start()
                
#     def is_busy(self):
#         with self.lock:
#             # Considered busy if the processing flag is set (thread is active) 
#             # OR if there are items in the queue (thread might have just exited but will restart)
#             # OR if a 'say' process is currently active.
#             is_thread_active = self._is_processing_queue_flag or \
#                                (self.speak_thread is not None and self.speak_thread.is_alive())
#             return is_thread_active or len(self.queue) > 0 or \
#                    (self.current_speak_process is not None and self.current_speak_process.poll() is None)

#     def stop(self): # Attempt to stop current speech and clear queue
#         print("TTS (say): stop() called.") # Debug
#         with self.lock:
#             self.queue.clear() # Clear pending phrases
#             process_to_stop = self.current_speak_process # Get current process under lock
            
#         if process_to_stop and process_to_stop.poll() is None: # If 'say' is running
#             print("TTS (say): Attempting to terminate active 'say' process...")
#             try:
#                 process_to_stop.terminate() # Send SIGTERM
#                 process_to_stop.wait(timeout=0.5) # Wait a bit for it to terminate
#                 if process_to_stop.poll() is None: # If still running
#                     print("TTS (say): 'say' process did not terminate with SIGTERM, sending SIGKILL.")
#                     process_to_stop.kill() # Force kill
#                     process_to_stop.wait(timeout=0.5) # Wait for kill
#                 print("TTS (say): Active 'say' process stopped.")
#             except Exception as e_stop:
#                 print(f"TTS (say): Error trying to stop 'say' process: {e_stop}")
        
#         # Reset the processing flag, as we've cleared the queue and attempted to stop speech
#         with self.lock:
#             self._is_processing_queue_flag = False 
#         print("TTS (say) stopped and queue cleared.")


# # Test for 'say' version
# if __name__ == '__main__':
#     # To see available voices: open Terminal and type `say -v ?`
#     # Common macOS voices: Alex, Allison, Ava, Fred, Kathy, Samantha, Susan, Tom, Victoria, Zoe
#     # For UK English: Daniel, Kate, Oliver, Serena
#     # Pick one that is available on your system. "Alex" is a common high-quality one.
#     tts_say = TTSManager(voice="Alex", rate=200) 
#     # tts_say = TTSManager(rate=180) # Uses default voice if none specified

#     print("TTS Manager (say command) Test...")
    
#     phrases_to_test = [
#         "Hello from the say command.",
#         "This is a second test, spoken with a bit of a pause.",
#         "This is a second test, spoken with a bit of a pause.", # Debounced
#         "After the debounce interval, this should speak again.",
#         "And a third phrase, added quickly now.",
#         "Followed by another one for good measure.",
#         "Let's see how the queue handles this.",
#         "Final test phrase."
#     ]

#     tts_say.speak(phrases_to_test[0])
#     time.sleep(0.1) # Let thread start
#     print(f"TTS busy after first speak: {tts_say.is_busy()}")

#     tts_say.speak(phrases_to_test[1])
#     time.sleep(0.2) 
#     print(f"TTS busy after second speak: {tts_say.is_busy()}")

#     tts_say.speak(phrases_to_test[2]) # Debounced
#     print(f"TTS busy after debounced speak: {tts_say.is_busy()} (should be true if prev still speaking or queued)")
    
#     print(f"Waiting {tts_say.debounce_interval + 0.2}s for debounce to clear...")
#     time.sleep(tts_say.debounce_interval + 0.2) 
#     tts_say.speak(phrases_to_test[3]) # Should speak now
    
#     tts_say.speak(phrases_to_test[4])
#     tts_say.speak(phrases_to_test[5])
#     tts_say.speak(phrases_to_test[6])
    
#     print("Waiting for all queued speech to finish...")
#     count = 0
#     max_wait_loops = 300 # Approx 30 seconds max wait for testing
#     while tts_say.is_busy() and count < max_wait_loops:
#         # print(f"Still busy... (Queue: {len(tts_say.queue)}, Processing: {tts_say._is_processing_queue_flag}, Process: {tts_say.current_speak_process.poll() if tts_say.current_speak_process else 'None'})")
#         time.sleep(0.1)
#         count += 1
    
#     if tts_say.is_busy():
#         print(f"TTS still busy after {max_wait_loops/10}s timeout. Forcing stop.")
#         tts_say.stop()

#     tts_say.speak(phrases_to_test[7])
#     count = 0
#     while tts_say.is_busy() and count < 50: # Max wait 5 seconds
#         time.sleep(0.1)
#         count +=1
    
#     print("Test complete.")