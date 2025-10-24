from speechbrain.inference.classifiers import EncoderClassifier

# Load pretrained SpeechBrain emotion model
# (Trained on IEMOCAP using wav2vec2)
classifier = EncoderClassifier.from_hparams(
    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
    savedir="pretrained_models/emotion-recognition-wav2vec2-IEMOCAP"
)

# Classify an example audio file
AUDIO_FILE = "output.wav"  # <-- replace with your file path

# Get predictions
out_prob, score, index, text_lab = classifier.classify_file(AUDIO_FILE)

# Print results
print(f"Predicted emotion: {text_lab}")
print(f"Confidence score: {score}")
print(f"Probabilities: {out_prob}")