#!/usr/bin/env python3

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer, GObject

Gst.init(None)

class RTSPServer(GstRtspServer.RTSPServer):
    def __init__(self):
        super(RTSPServer, self).__init__()
        factory = GstRtspServer.RTSPMediaFactory()
        
        # CSI camera RTSP pipeline
        factory.set_launch((
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=640, height=360, framerate=30/1 ! "
    "nvvidconv ! "
    "nvv4l2h264enc insert-sps-pps=true iframeinterval=10 bitrate=2000000 preset-level=1 control-rate=2 ! "
    "h264parse config-interval=1 ! "
    "rtph264pay pt=96 name=pay0 "
))


        factory.set_shared(True)
        self.get_mount_points().add_factory("/cam", factory)

if __name__ == "__main__":
    server = RTSPServer()
    server.attach(None)
    print("RTSP Server started at rtsp://<Jetson-IP>:8554/cam")
    loop = GObject.MainLoop()
    loop.run()
