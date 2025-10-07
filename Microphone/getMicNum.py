import pyaudio

# Create an instance of PyAudio
p = pyaudio.PyAudio()

# Get the total number of audio devices
num_devices = p.get_device_count()

print(f"Total number of audio devices found: {num_devices}\n")
print("Connected Microphones:")

# Iterate through all devices
for i in range(num_devices):
    device_info = p.get_device_info_by_index(i)

    # Check if the device has input channels (indicating it's a microphone)
    if device_info.get('maxInputChannels') > 0:
        print(f"  Device Index: {i}")
        print(f"  Device Name: {device_info.get('name')}")
        print(f"  Max Input Channels: {device_info.get('maxInputChannels')}")
        print("-" * 30)

# Terminate the PyAudio instance
p.terminate()