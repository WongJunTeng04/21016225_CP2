# test_pyaudio_simple.py
import pyaudio
import wave
import traceback # Add this

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000 # Common rate for STT
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output_test.wav"

p = None
stream = None

try:
    p = pyaudio.PyAudio()
    print("PyAudio Initialized. Available audio devices:")
    default_input_device_index = -1
    try:
        default_input_device_index = p.get_default_input_device_info()['index']
        print(f"Default Input Device Index: {default_input_device_index}")
    except Exception as e:
        print(f"Could not get default input device: {e}")


    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        print(f"  {i}: {dev['name']} (Input Channels: {dev['maxInputChannels']})")
    
    print(f"\nAttempting to open stream with default input device (or index 0 if default failed)...")
    
    # Try default input device, fallback to 0 if necessary
    device_to_try = default_input_device_index if default_input_device_index != -1 else 0
    print(f"Using device index: {device_to_try}")


    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_to_try, # Explicitly use an index
                    frames_per_buffer=CHUNK)
    print(f"* Recording for {RECORD_SECONDS} seconds using: {p.get_device_info_by_index(device_to_try)['name']}")
    frames = []
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
    print("* Done recording")

except Exception as e:
    print(f"Error during PyAudio test: {e}")
    traceback.print_exc()
finally:
    if stream:
        stream.stop_stream()
        stream.close()
        print("Stream closed.")
    if p:
        p.terminate()
        print("PyAudio terminated.")

if frames: # Only try to save if recording happened
    try:
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT)) # Re-init p for this if terminated
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        print(f"Saved to {WAVE_OUTPUT_FILENAME}. Please check this file with an audio player.")
    except Exception as e:
        print(f"Error saving WAV file: {e}")
else:
    print("No frames recorded to save.")