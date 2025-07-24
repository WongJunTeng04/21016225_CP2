# tts_manager.py

# Imports
import subprocess
import threading
import time
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
