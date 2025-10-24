import pvporcupine
import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import speech_recognition as sr
import time
import struct
import webrtcvad
import collections

# ====== CONFIGURATION ======
WAKE_WORD = "computer"         # Your chosen wake word
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'              # I2S microphone
DTYPE = 'int32'
FRAME_DURATION = 30            # 10, 20, or 30 ms
VAD_SENSITIVITY = 2            # 0–3 (3 = most sensitive)
SILENCE_LIMIT = 1.0            # seconds of silence to stop recording

# ====== INITIALIZE ======
recognizer = sr.Recognizer()
porcupine = pvporcupine.create(keywords=[WAKE_WORD])
FRAME_LENGTH = porcupine.frame_length
vad = webrtcvad.Vad(VAD_SENSITIVITY)

print(f"🎧 Listening for wake word: '{WAKE_WORD}'...")

# ====== FUNCTION: Record until silence ======
def record_until_silence():
    print("🎙 Wake word detected! Waiting for your speech...")

    frame_size = int(SAMPLE_RATE * FRAME_DURATION / 1000)
    frames = collections.deque(maxlen=int(SILENCE_LIMIT * 1000 / FRAME_DURATION))
    voiced_frames = []
    recording = False
    silence_counter = 0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE,
        blocksize=frame_size
    ) as stream:
        while True:
            frame, _ = stream.read(frame_size)
            pcm16 = np.int16(frame.flatten() / np.iinfo(np.int32).max * 32767)
            raw_bytes = pcm16.tobytes()

            is_speech = vad.is_speech(raw_bytes, SAMPLE_RATE)

            if is_speech:
                if not recording:
                    print("🗣 Speech started — recording...")
                    recording = True
                voiced_frames.append(raw_bytes)
                silence_counter = 0
            elif recording:
                silence_counter += FRAME_DURATION / 1000
                if silence_counter > SILENCE_LIMIT:
                    print("🔇 Speech ended — stopping recording.")
                    break

    # Convert collected frames to float audio
    pcm_concat = b''.join(voiced_frames)
    audio_np = np.frombuffer(pcm_concat, dtype=np.int16).astype(np.float32) / 32767.0
    return audio_np

# ====== FUNCTION: Speech-to-Text ======
def audio_to_text(audio_float):
    buf = io.BytesIO()
    sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    buf.seek(0)
    with sr.AudioFile(buf) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)
        print(f"💬 You said: {text}")
        return text
    except sr.UnknownValueError:
        print("🤔 Could not understand audio.")
    except sr.RequestError as e:
        print(f"⚠️ API request failed: {e}")

# ====== CONTINUOUS LOOP ======
try:
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_LENGTH,
        dtype=DTYPE,
        channels=1,
        device=DEVICE
    ) as stream:
        while True:
            pcm = stream.read(FRAME_LENGTH)[0]
            pcm16 = np.int16(pcm.flatten() / np.iinfo(np.int32).max * 32767)
            keyword_index = porcupine.process(pcm16)

            if keyword_index >= 0:
                print("💡 Wake word detected!")
                audio_data = record_until_silence()
                if len(audio_data) > 0:
                    audio_to_text(audio_data)
                print(f"\n🎧 Listening again for wake word: '{WAKE_WORD}'...\n")

except KeyboardInterrupt:
    print("\n🛑 Exiting...")
finally:
    porcupine.delete()
