import os
import sys
import json
import subprocess
from vosk import Model, KaldiRecognizer

MODEL_PATH = "vosk-model-small-en-us-0.15"

# Load Vosk model
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)

# Use arecord to capture audio in real-time
arecord_cmd = [
    "arecord",
    "-D", "hw:2,0",   # Change this to your USB mic device
    "-f", "S16_LE", "-c1",
    "-r", "44100",
    "-c", "1",
    "-t", "raw"
]

print("Listening... Press Ctrl+C to stop.")
with subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE, bufsize=8000) as stream:
    while True:
        data = stream.stdout.read(4000)
        if len(data) == 0:
            break
        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            if result.get("text"):
                print("You said:", result["text"])
