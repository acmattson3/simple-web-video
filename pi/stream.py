#!/usr/bin/env python3
import os
import subprocess
import time

RTSP_URL = os.getenv("RTSP_URL", "rtsp://yourdomain:8554/stream")
RTSP_TRANSPORT = os.getenv("RTSP_TRANSPORT", "tcp")
VIDEO_DEV = os.getenv("VIDEO_DEV", "/dev/video0")
WIDTH = os.getenv("WIDTH", "1280")
HEIGHT = os.getenv("HEIGHT", "720")
FPS = int(os.getenv("FPS", "25"))
VBITRATE = os.getenv("VBITRATE", "500k")
MAXRATE = os.getenv("MAXRATE", VBITRATE)
BUFSIZE = os.getenv("BUFSIZE", "1000k")
PRESET = os.getenv("PRESET", "veryfast")

GOP = FPS

cmd = [
    "ffmpeg",
    "-f", "v4l2",
    "-framerate", str(FPS),
    "-video_size", f"{WIDTH}x{HEIGHT}",
    "-i", VIDEO_DEV,
    "-c:v", "libx264",
    "-preset", PRESET,
    "-tune", "zerolatency",
    "-pix_fmt", "yuv420p",
    "-profile:v", "baseline",
    "-level", "3.1",
    "-b:v", VBITRATE,
    "-maxrate", MAXRATE,
    "-bufsize", BUFSIZE,
    "-g", str(GOP),
    "-keyint_min", str(GOP),
    "-sc_threshold", "0",
    "-bf", "0",
    "-an",
    "-f", "rtsp",
    "-rtsp_transport", RTSP_TRANSPORT,
    RTSP_URL,
]

backoff = 1
max_backoff = 30

while True:
    print("Starting ffmpeg...", flush=True)
    try:
        proc = subprocess.Popen(cmd)
        code = proc.wait()
        print(f"ffmpeg exited with code {code}", flush=True)
    except FileNotFoundError:
        print("ffmpeg not found. Please install it.", flush=True)
        raise SystemExit(1)

    print(f"Restarting in {backoff}s...", flush=True)
    time.sleep(backoff)
    backoff = min(backoff * 2, max_backoff)
