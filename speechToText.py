import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer

MODEL_PATH = "vosk-model-small-en-us-0.15"
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)

q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(bytes(indata))

def main():
    with sd.RawInputStream(samplerate=16000, blocksize=8000,
                           dtype='int16', channels=1, callback=callback):
        print("Listening... (Ctrl+C to stop)")
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if result["text"]:
                    print("You said:", result["text"])

if __name__ == "__main__":
    main()
