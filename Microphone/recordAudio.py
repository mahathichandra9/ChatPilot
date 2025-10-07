import sounddevice as sd
import scipy.io.wavfile as wav
import datetime

# Recording settings
SAMPLE_RATE = 44100  # CD-quality
CHANNELS = 1         # Mono
DURATION = 5         # Seconds

def record_audio(filename="output.wav", duration=DURATION):
    print(f"Recording for {duration} seconds...")
    audio_data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    sd.wait()  # Wait until recording is finished
    wav.write(filename, SAMPLE_RATE, audio_data)
    print(f"Saved recording as {filename}")

if __name__ == "__main__":
    # Auto-generate filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{timestamp}.wav"
    record_audio(filename, DURATION)
