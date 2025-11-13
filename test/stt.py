# import speech_recognition as sr

# recognizer = sr.Recognizer()
# text = recognizer.recognize_google(recognizer.record("stop.wav"))
# print(text)

import speech_recognition as sr

def wav_to_text(file_path):
    # Initialize recognizer
    recognizer = sr.Recognizer()

    # Load the audio file
    with sr.AudioFile(file_path) as source:
        print("🎧 Reading audio file...")
        audio_data = recognizer.record(source)  # read the entire audio file

    try:
        # Recognize speech using Google Web Speech API
        print("🧠 Recognizing speech...")
        text = recognizer.recognize_google(audio_data)
        print("\n✅ Transcription Successful!")
        print("Text Output:\n")
        print(text)
        return text

    except sr.UnknownValueError:
        print("❌ Speech Recognition could not understand the audio.")
    except sr.RequestError as e:
        print(f"⚠️ Could not request results; check your internet connection. Error: {e}")

# ===============================
# Example usage
# ===============================
if __name__ == "__main__":
    audio_path = "stop.wav"  # Replace with your .wav file path
    wav_to_text(audio_path)
