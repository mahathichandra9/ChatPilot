import pvporcupine
import pyaudio
import struct
import webrtcvad
import collections
import time
import wave
import speech_recognition as sr

# ========== CONFIGURATION ==========
WAKE_WORD = "computer"
SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms (10, 20, or 30)
FRAME_LENGTH = int(SAMPLE_RATE * FRAME_DURATION / 1000)
VAD_SENSITIVITY = 2  # 0–3 (3 = very sensitive)
SILENCE_LIMIT = 1.0  # seconds of silence to stop recording
OUTPUT_FILE = "command.wav"

# ========== INITIALIZATION ==========
porcupine = pvporcupine.create(
        access_key="VBNktt/3G1Hw2Of+ajNPQnvW8mPtA40BCZGsKIb9mxPhG0kW7JXDcw==",
        keyword_paths=[f'./Hey-rover_en_windows_v3_0_0.ppn']
    )
vad = webrtcvad.Vad(VAD_SENSITIVITY)
pa = pyaudio.PyAudio()
recognizer = sr.Recognizer()

audio_stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

print(f"🎧 Listening for wake word: '{WAKE_WORD}'...")

def record_until_silence():
    """Record automatically based on speech activity."""
    print("🎙 Wake word detected! Waiting for speech...")
    frames = collections.deque(maxlen=int(SILENCE_LIMIT * 1000 / FRAME_DURATION))
    voiced_frames = []
    recording = False
    silence_counter = 0

    while True:
        pcm = audio_stream.read(FRAME_LENGTH, exception_on_overflow=False)
        is_speech = vad.is_speech(pcm, SAMPLE_RATE)

        if is_speech:
            if not recording:
                print("🗣 Speech detected! Recording...")
                recording = True
            voiced_frames.append(pcm)
            silence_counter = 0
        elif recording:
            silence_counter += FRAME_DURATION / 1000
            if silence_counter > SILENCE_LIMIT:
                print("🔇 Silence detected. Stopping recording.")
                break

    wf = wave.open(OUTPUT_FILE, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(b''.join(voiced_frames))
    wf.close()
    print("✅ Audio saved:", OUTPUT_FILE)

def speech_to_text(filename=OUTPUT_FILE):
    print("🧠 Converting speech to text...")
    with sr.AudioFile(filename) as source:
        audio = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio)
            print(f"💬 You said: {text}")
        except sr.UnknownValueError:
            print("❌ Could not understand audio.")
        except sr.RequestError:
            print("⚠️ Speech service unavailable.")

try:
    while True:
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)

        keyword_index = porcupine.process(pcm_unpacked)
        if keyword_index >= 0:
            record_until_silence()
            speech_to_text()
            print(f"\n🎧 Listening again for wake word: '{WAKE_WORD}'...\n")

except KeyboardInterrupt:
    print("🛑 Exiting...")
finally:
    audio_stream.close()
    pa.terminate()
    porcupine.delete()
