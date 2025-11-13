from faster_whisper import WhisperModel

# Load a model (tiny, base, small, medium, large-v2)
model = WhisperModel("small", device="cpu")

# Transcribe audio file
wav_file = "test.wav"
segments, info = model.transcribe(wav_file)

# Combine text
transcript = " ".join([seg.text for seg in segments])
print("Transcription:", transcript)