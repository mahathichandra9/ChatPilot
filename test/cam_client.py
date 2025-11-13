#!/usr/bin/env python3
import asyncio
import websockets
import cv2
import numpy as np

JETSON_IP = "10.11.105.204"   # << CHANGE THIS
URL = f"ws://{JETSON_IP}:8765/video"

async def receive_video():
    print(f"Connecting to {URL} ...")

    async with websockets.connect(URL, max_size=2**23) as ws:
        print("Connected!")

        while True:
            try:
                # Receive raw JPEG bytes
                frame_bytes = await ws.recv()

                # Convert bytes → numpy array
                np_arr = np.frombuffer(frame_bytes, np.uint8)

                # Decode JPEG → image
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if img is None:
                    continue

                # Show the frame
                cv2.imshow("Jetson CSI Stream", img)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            except websockets.ConnectionClosed:
                print("Connection closed. Reconnecting...")
                await asyncio.sleep(1)
                return await receive_video()
            except Exception as e:
                print("Error:", e)
                continue

    cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(receive_video())
