# #!/usr/bin/env python3
# import asyncio
# import websockets
# import gi
# import base64
# gi.require_version("Gst", "1.0")
# from gi.repository import Gst, GLib

# Gst.init(None)

# clients = set()  # connected websocket clients


# async def register(websocket):
#     clients.add(websocket)
#     print("Client connected:", websocket.remote_address)


# async def unregister(websocket):
#     clients.remove(websocket)
#     print("Client disconnected:", websocket.remote_address)


# async def ws_handler(websocket, path):
#     await register(websocket)
#     try:
#         await websocket.wait_closed()
#     finally:
#         await unregister(websocket)


# def on_new_sample(sink, data):
#     sample = sink.emit("pull-sample")
#     buffer = sample.get_buffer()

#     success, mapinfo = buffer.map(Gst.MapFlags.READ)
#     if not success:
#         return Gst.FlowReturn.ERROR

#     jpeg_bytes = mapinfo.data  # this is raw JPEG bytes

#     # Broadcast manually (compatible with all websockets versions)
#     to_remove = []
#     for ws in clients:
#         try:
#             # send binary (faster than base64)
#             asyncio.create_task(ws.send(jpeg_bytes))
#         except:
#             to_remove.append(ws)

#     # Remove bad clients
#     for ws in to_remove:
#         clients.remove(ws)

#     buffer.unmap(mapinfo)
#     return Gst.FlowReturn.OK


# async def main():
#     pipeline = Gst.parse_launch(
#         "nvarguscamerasrc ! "
#         "video/x-raw(memory:NVMM), width=640, height=480, format=NV12, framerate=30/1 ! "
#         "nvjpegenc quality=60 ! "
#         "appsink name=appsink emit-signals=true max-buffers=1 drop=true"
#     )

#     appsink = pipeline.get_by_name("appsink")
#     appsink.connect("new-sample", on_new_sample, None)

#     pipeline.set_state(Gst.State.PLAYING)

#     print("WebSocket CSI stream running at ws://0.0.0.0:8765")

#     # Keep GStreamer alive
#     loop = GLib.MainLoop()
#     loop.run()


# if __name__ == "__main__":
#     loop = asyncio.get_event_loop()
#     server = websockets.serve(ws_handler, "0.0.0.0", 8765, max_size=2**23)

#     loop.run_until_complete(server)
#     loop.run_until_complete(main())
















#!/usr/bin/env python3
import asyncio
import websockets
import gi
import threading  # We need threading
# import bytesio      # To copy the buffer
from io import BytesIO
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

clients = set()  # A set of connected websocket clients
asyncio_loop = None # We'll store the main asyncio loop here

async def register(websocket):
    """Adds a new client to the set."""
    clients.add(websocket)
    print(f"Client connected: {websocket.remote_address} (Total: {len(clients)})")

async def unregister(websocket):
    """Removes a client from the set."""
    clients.remove(websocket)
    print(f"Client disconnected: {websocket.remote_address} (Total: {len(clients)})")

async def ws_handler(websocket, path):
    """Handles a new WebSocket connection."""
    # Ensure clients connect to the correct path
    if path != "/video":
        print(f"Client tried to connect to invalid path: {path}")
        await websocket.close(1003, "Invalid path")
        return

    await register(websocket)
    try:
        await websocket.wait_closed()  # Wait until the client disconnects
    finally:
        await unregister(websocket)

async def broadcast_frame(frame_bytes):
    """Broadcasts a frame to all connected clients concurrently."""
    if not clients:
        return  # No clients, do nothing

    # Use asyncio.gather for concurrent sending
    tasks = [ws.send(frame_bytes) for ws in clients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle clients that failed (e.g., disconnected)
    to_remove = []
    for ws, result in zip(list(clients), results):
        if isinstance(result, Exception):
            print(f"Failed to send to {ws.remote_address}, removing: {result}")
            to_remove.append(ws)
            
    # Safely remove bad clients from the set
    for ws in to_remove:
        if ws in clients:
            clients.remove(ws)

def on_new_sample(sink, data):
    """GStreamer 'new-sample' callback, runs in GStreamer's thread."""
    global asyncio_loop
    
    sample = sink.emit("pull-sample")
    if not sample:
        return Gst.FlowReturn.OK

    buffer = sample.get_buffer()
    success, mapinfo = buffer.map(Gst.MapFlags.READ)
    if not success:
        buffer.unmap(mapinfo)
        return Gst.FlowReturn.ERROR

    # Critical: Copy the frame data into a new 'bytes' object.
    # The 'mapinfo.data' is a view that becomes invalid after 'unmap'.
    frame_copy = bytes(mapinfo.data)

    # We are in GStreamer's thread. We must not call asyncio functions directly.
    # Use 'run_coroutine_threadsafe' to schedule the broadcast on the asyncio loop.
    if asyncio_loop and clients:
        asyncio.run_coroutine_threadsafe(broadcast_frame(frame_copy), asyncio_loop)

    buffer.unmap(mapinfo)
    return Gst.FlowReturn.OK

def start_gst_loop():
    """Starts the GStreamer pipeline in a separate thread."""
    pipeline = Gst.parse_launch(
        "nvarguscamerasrc sensor-id=0 ! "  # Explicitly set sensor-id (common for Jetson)
        "video/x-raw(memory:NVMM), width=640, height=480, format=NV12, framerate=30/1 ! "
        "nvjpegenc quality=70 ! "  # 70 is a good balance of quality/size
        "appsink name=appsink emit-signals=true max-buffers=1 drop=true"
    )

    appsink = pipeline.get_by_name("appsink")
    appsink.connect("new-sample", on_new_sample, None)

    pipeline.set_state(Gst.State.PLAYING)
    print("GStreamer pipeline running...")

    # Run the GStreamer main loop
    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping GStreamer loop...")
        pipeline.set_state(Gst.State.NULL)

async def start_websocket_server():
    """Starts the WebSocket server."""
    print(f"Starting WebSocket server at ws://0.0.0.0:8765/video")
    # Set max_size=None to allow for large video frames
    async with websockets.serve(ws_handler, "0.0.0.0", 8765, max_size=None):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    # Get the main asyncio event loop
    asyncio_loop = asyncio.get_event_loop()

    # Start the GStreamer loop in a separate, daemon thread
    gst_thread = threading.Thread(target=start_gst_loop, daemon=True)
    gst_thread.start()

    # Start the WebSocket server on the main thread's asyncio loop
    try:
        asyncio_loop.run_until_complete(start_websocket_server())
    except KeyboardInterrupt:
        print("WebSocket server stopped.")
    finally:
        asyncio_loop.close()
        print("Server shut down.")