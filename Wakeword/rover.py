import pvporcupine
import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import speech_recognition as sr
import time
import struct

# ====== CONFIGURATION ======
WAKE_WORD = "computer"       # Try “computer”, “jarvis”, “alexa”, etc.
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 'hw:1,0'            # Your I2S mic device
DTYPE = 'int32'
RECORD_DURATION = 5          # Duration after wake word
CHUNK_DURATION = 0.5         # Seconds per listening chunk

# ====== INITIALIZE ======
recognizer = sr.Recognizer()
porcupine = pvporcupine.create(keywords=[WAKE_WORD])
FRAME_LENGTH = porcupine.frame_length

print(f"🎧 Listening for wake word: '{WAKE_WORD}'...")

# ====== FUNCTION: Record a short command ======
def record_audio(duration=RECORD_DURATION):
    print(f"🎙 Wake word detected! Recording {duration}s of speech...")
    audio_data = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE
    )
    sd.wait()
    audio_float = audio_data.astype(np.float32) / np.iinfo(np.int32).max
    return audio_float

# ====== FUNCTION: Speech-to-Text ======
def audio_to_text(audio_float):
    buf = io.BytesIO()
    sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    buf.seek(0)
    with sr.AudioFile(buf) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)
        print(f"🗣  {text}")
        return text
    except sr.UnknownValueError:
        print("🤔 Could not understand audio.")
    except sr.RequestError as e:
        print(f"⚠ API request failed: {e}")

# ====== CONTINUOUS LISTEN LOOP ======
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
                audio_chunk = record_audio(RECORD_DURATION)
                audio_to_text(audio_chunk)
                print(f"\n🎧 Listening again for '{WAKE_WORD}'...\n")

except KeyboardInterrupt:
    print("\n🛑 Exiting...")
finally:
    porcupine.delete()
