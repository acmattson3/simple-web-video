#!/usr/bin/env bash
set -euo pipefail

RTSP_URL=${RTSP_URL:-rtsp://yourdomain:8554/stream}
RTSP_TRANSPORT=${RTSP_TRANSPORT:-tcp}
VIDEO_DEV=${VIDEO_DEV:-/dev/video0}
WIDTH=${WIDTH:-1280}
HEIGHT=${HEIGHT:-720}
FPS=${FPS:-25}
VBITRATE=${VBITRATE:-500k}
MAXRATE=${MAXRATE:-${VBITRATE}}
BUFSIZE=${BUFSIZE:-1000k}
PRESET=${PRESET:-veryfast}

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found. Please install it." >&2
  exit 1
fi

GOP=$FPS

exec ffmpeg \
  -f v4l2 \
  -framerate "${FPS}" \
  -video_size "${WIDTH}x${HEIGHT}" \
  -i "${VIDEO_DEV}" \
  -c:v libx264 \
  -preset "${PRESET}" \
  -tune zerolatency \
  -pix_fmt yuv420p \
  -profile:v baseline \
  -level 3.1 \
  -b:v "${VBITRATE}" \
  -maxrate "${MAXRATE}" \
  -bufsize "${BUFSIZE}" \
  -g "${GOP}" \
  -keyint_min "${GOP}" \
  -sc_threshold 0 \
  -bf 0 \
  -an \
  -f rtsp -rtsp_transport "${RTSP_TRANSPORT}" "${RTSP_URL}"
