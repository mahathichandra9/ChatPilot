#!/usr/bin/env python3
"""
rover_simple_client.py

Minimal end-to-end rover client for Jetson Nano:
 - Waits for wake-word (pvporcupine) if installed, otherwise press ENTER (push-to-talk)
 - Records a short WAV (16kHz, 16-bit, mono)
 - POSTs the wav to CLOUD_URL as multipart/form-data (field name: "file")
 - Expects JSON reply:
     { "response_text": "...", "command": { "action":"move", "direction":"forward", "speed":0.6, "duration":2.0 } }
 - Runs motor commands by direct velocity (set_velocity: -1.0..1.0)
 - Runs local TTS using espeak (non-blocking)
 
 Edit CLOUD_URL and AUTH_TOKEN below. Replace set_velocity() body with your motor driver calls.
"""

import os
import time
import io
import sys
import json
import threading
import requests

# Optional recording libs
try:
    import sounddevice as sd
    from scipy.io.wavfile import write as wav_write
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    SOUNDDEVICE_AVAILABLE = False

# Optional wake-word (Porcupine)
PORCUPINE_AVAILABLE = False
try:
    import pvporcupine
    import numpy as np
    PORCUPINE_AVAILABLE = True
except Exception:
    PORCUPINE_AVAILABLE = False

# ---------- CONFIG ----------
# IMPORTANT: set CLOUD_URL to your laptop's server IP (e.g. "http://192.168.1.45:5000/recognize")
CLOUD_URL = "http://192.168.137.83:5000:5000/recognize"
AUTH_TOKEN = ""                                # e.g. "Bearer <token>" or leave empty for no auth

SAMPLE_RATE = 16000
CHANNELS = 1
MAX_UTTERANCE_SECONDS = 8
WAV_PATH = "/tmp/rover_utterance.wav"

# Motor scale/clamp
MAX_SPEED = 1.0
MIN_SPEED = -1.0
SAMPLE_RATE = 16000        # Matches your arecord rate
CHANNELS = 1               # Mono
DEVICE = 'hw:1,0'          # I2S microphone device
DTYPE = 'int32'            # Match S32_LE
CHUNK_DURATION = 3         # seconds per recognition chunk

# ----------------------------

# ---------- Replace this with your real motor implementation ----------
# set_velocity(left, right, duration=None)
# left/right in [-1.0 .. 1.0] -> negative = reverse, positive = forward
# duration (seconds) optional; if provided the function should block for that duration or internally stop after it.
def set_velocity(left: float, right: float, duration: float = None):
    """
    STUB: Replace the body of this function with calls to your actual motor API.
    Example conversion if your motor API expects -100..100:
        motor_driver.set(left * 100, right * 100)
    """
    left = max(MIN_SPEED, min(MAX_SPEED, float(left)))
    right = max(MIN_SPEED, min(MAX_SPEED, float(right)))
    left_pct = int(left * 100)
    right_pct = int(right * 100)
    # Debug print (or replace with actual motor call)
    print(f"[MOTOR] set_velocity: L={left:.2f} ({left_pct}%), R={right:.2f} ({right_pct}%)")
    # TODO: Replace the following with the real motor driver call:
    # motor_driver.set_speed(left_pct, right_pct)
    if duration and duration > 0:
        time.sleep(duration)
        # stop after duration
        print("[MOTOR] duration finished -> stopping motors")
        # motor_driver.set_speed(0, 0)
        print("[MOTOR] set_velocity: L=0 R=0")
# ----------------------------------------------------------------------

def speak(text: str):
    """Local TTS using espeak (non-blocking)."""
    if not text:
        return
    print("[TTS]", text)
    # spawn a background thread to avoid blocking main loop
    threading.Thread(target=lambda t: os.system(f'espeak "{t}" >/dev/null 2>&1'), args=(text,), daemon=True).start()

def record_wav(filename: str, duration: int = MAX_UTTERANCE_SECONDS, fs=SAMPLE_RATE):
    """Record using sounddevice if available, else fallback to arecord utility (Linux)."""
    # Use sounddevice when available for portability in Python
    if SOUNDDEVICE_AVAILABLE:
        try:
            print(f"[REC] Recording (sounddevice) up to {duration}s...")
            rec = sd.rec(int(duration * fs), samplerate=fs, channels=CHANNELS, dtype='int16')
            sd.wait()
            wav_write(filename, fs, rec, SAMPLE_RATE, format='WAV', subtype='PCM_16')
            # sf.write(buf, audio_float, SAMPLE_RATE, format='WAV', subtype='PCM_16')
            print("[REC] Saved", filename)
            return True
        except Exception as e:
            print("[REC] sounddevice record failed:", e)
            return False
    else:
        # fallback: require arecord on system
        print("[REC] sounddevice not available — using arecord fallback (Linux required).")
        cmd = f'arecord -f S16_LE -r {fs} -c {CHANNELS} -d {duration} "{filename}"'
        ret = os.system(cmd)
        return ret == 0

def upload_wav_and_get_json(filename: str):
    """POST wav to CLOUD_URL and return parsed JSON or None on error."""
    if not os.path.exists(filename):
        print("[UPLOAD] file not found:", filename)
        return None
    files = {'file': (os.path.basename(filename), open(filename, 'rb'), 'audio/wav')}
    headers = {}
    if AUTH_TOKEN:
        headers['Authorization'] = AUTH_TOKEN
    try:
        print("[UPLOAD] Sending to", CLOUD_URL)
        r = requests.post(CLOUD_URL, files=files, headers=headers, timeout=30)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            print("[UPLOAD] Received non-JSON response")
            return None
    except Exception as e:
        print("[UPLOAD] request failed:", e)
        return None

def execute_command(cmd: dict):
    """Interpret movement command and call set_velocity accordingly."""
    if not cmd:
        return
    action = cmd.get("action", "move")
    if action == "stop":
        set_velocity(0.0, 0.0)
        return
    if action != "move":
        print("[CMD] Unsupported action:", action)
        return

    direction = str(cmd.get("direction", "forward")).lower()
    speed = float(cmd.get("speed", 0.5))
    duration = float(cmd.get("duration", 0.0))
    # clamp speed 0..1 for directional moves
    speed = max(0.0, min(1.0, speed))

    if direction == "forward":
        left_v = speed
        right_v = speed
    elif direction == "backward":
        left_v = -speed
        right_v = -speed
    elif direction == "left":
        left_v = -speed * 0.6
        right_v = speed * 0.6
    elif direction == "right":
        left_v = speed * 0.6
        right_v = -speed * 0.6
    else:
        # allow explicit left/right speeds if provided
        l = cmd.get("left_speed")
        r = cmd.get("right_speed")
        if l is not None and r is not None:
            left_v = float(l)
            right_v = float(r)
        else:
            print("[CMD] Unknown direction:", direction)
            return

    print(f"[CMD] execute move dir={direction} speed={speed} dur={duration}")
    if duration and duration > 0:
        set_velocity(left_v, right_v, duration=duration)
    else:
        # Non-blocking set (caller must ensure watchdog or later stop)
        set_velocity(left_v, right_v)

import time
import threading

def _porcupine_available_and_working():
    """
    Return (pvporcupine_module, porcupine_obj) or (None, None) on failure.
    This attempts to import and call pvporcupine.create safely.
    """
    try:
        import pvporcupine
    except Exception as e:
        print("[WAKE-DEBUG] pvporcupine import failed:", e)
        return None, None

    # quick attribute check
    if not hasattr(pvporcupine, "create"):
        print("[WAKE-DEBUG] pvporcupine module found but has no 'create' attribute. Module dir():")
        try:
            print(dir(pvporcupine))
        except Exception:
            pass
        return None, None

    # try to construct an instance (may raise if wheel missing native lib)
    try:
        porcupine = pvporcupine.create()  # default keyword model
        return pvporcupine, porcupine
    except Exception as e:
        print("[WAKE-DEBUG] pvporcupine.create() failed:", e)
        return None, None

def wait_for_wake():
    """
    Try Porcupine wakeword; if unavailable or broken, fall back to push-to-talk (ENTER).
    This function does not raise; it either returns on detection or returns after ENTER.
    """
    pvmod, porcupine = _porcupine_available_and_working()
    if pvmod and porcupine:
        print("[WAKE] Porcupine available — listening for wake word...")
        try:
            import sounddevice as sd
            import numpy as np
            with sd.RawInputStream(samplerate=porcupine.sample_rate,
                                   blocksize=porcupine.frame_length,
                                   dtype='int16', channels=1) as stream:
                while True:
                    pcm = stream.read(porcupine.frame_length)[0]
                    arr = np.frombuffer(pcm, dtype=np.int16)
                    try:
                        idx = porcupine.process(arr)
                    except Exception as e:
                        print("[WAKE-DEBUG] porcupine.process() error, falling back:", e)
                        break
                    if idx >= 0:
                        print("[WAKE] Wake-word detected.")
                        try:
                            porcupine.delete()
                        except Exception:
                            pass
                        return
        except Exception as e:
            print("[WAKE-DEBUG] sound loop error or stream error:", e)
            try:
                porcupine.delete()
            except Exception:
                pass
            # fallthrough to push-to-talk

    # fallback
    print("[WAKE] Porcupine not usable — falling back to push-to-talk.")
    input("[WAKE] Press ENTER to start recording...")

def main_loop():
    print("ROVER SIMPLE CLIENT READY")
    print("CLOUD_URL =", CLOUD_URL)
    if not SOUNDDEVICE_AVAILABLE:
        print("Note: sounddevice not available — arecord fallback will be used (Linux only).")
    if not PORCUPINE_AVAILABLE:
        print("Note: porcupine not available — using push-to-talk (Enter).")

    while True:
        try:
            wait_for_wake()
            # Record audio file
            ok = record_wav(WAV_PATH, duration=MAX_UTTERANCE_SECONDS)
            if not ok:
                print("[MAIN] Recording failed; retrying loop.")
                continue

            # Upload and get response
            resp = upload_wav_and_get_json(WAV_PATH)
            if not resp:
                speak("Sorry, I couldn't reach the server.")
                continue

            print("[MAIN] Cloud response:", json.dumps(resp))
            # Speak response_text if present
            text = resp.get("response_text") or resp.get("text")
            if text:
                speak(text)

            # Execute movement if present
            cmd = resp.get("command")
            if cmd:
                # execute in a background thread so TTS and other loops don't block if desired
                threading.Thread(target=execute_command, args=(cmd,), daemon=True).start()
            else:
                print("[MAIN] No movement command in response.")
        except KeyboardInterrupt:
            print("Exiting on user interrupt.")
            break
        except Exception as e:
            print("Runtime error:", e)
            # small sleep to avoid tight crash loop
            time.sleep(0.5)

if __name__ == "__main__":
    main_loop()
