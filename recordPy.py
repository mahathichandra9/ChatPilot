import pyaudio
import wave

# Recording parameters
FORMAT = pyaudio.paInt16      # 16-bit
CHANNELS = 1                  # Mono
RATE = 44100                  # 44.1 kHz
CHUNK = 512
RECORD_SECONDS = 5
OUTPUT_FILE = "test.wav"

# Initialize PyAudio
p = pyaudio.PyAudio()

# Find your device index (USB mic)
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if "USB PnP Sound Device" in info.get("name"):
        DEVICE_INDEX = i
        print(f"Using device {i}: {info.get('name')}")
        break
else:
    raise RuntimeError("USB mic not found")

# Open stream
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=DEVICE_INDEX,
                frames_per_buffer=CHUNK)

print("Recording...")
frames = []

for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

print("Recording finished.")

# Stop stream
stream.stop_stream()
stream.close()
p.terminate()

# Save as WAV
wf = wave.open(OUTPUT_FILE, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()

print(f"Saved recording as {OUTPUT_FILE}")
