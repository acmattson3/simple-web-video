# Pi RTMP Streamer

Minimal client to push a V4L2 camera stream to an RTMP server.

## Install deps

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## Quick test (one-shot)

```sh
RTMP_URL=rtmp://<server-host>/live/stream ./stream.sh
```

Note: the default stream disables audio and forces H.264 baseline + yuv420p for browser compatibility.

## Configuration via `/etc/cam-stream.env`

Create a file like:

```sh
RTMP_URL=rtmp://yourdomain/live/stream
VIDEO_DEV=/dev/video0
WIDTH=1280
HEIGHT=720
FPS=25
VBITRATE=500k
MAXRATE=500k
BUFSIZE=1000k
PRESET=veryfast
```

## systemd setup

1. Copy scripts to a stable path (example: `/opt/cam`):

```sh
sudo mkdir -p /opt/cam
sudo cp -r ./stream.sh ./stream.py /opt/cam/
```

2. Install the unit file:

```sh
sudo cp ./systemd/cam-stream.service /etc/systemd/system/cam-stream.service
```

3. Reload and enable:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now cam-stream
```

## Troubleshooting

- Logs: `journalctl -u cam-stream -f`
- Verify camera device exists: `ls -l /dev/video0`
- Test RTMP TCP connectivity: `nc -vz <server-host> 1935`
- Server-side: confirm `server/www/hls/stream.m3u8` and `.ts` segments appear

## Security note

No authentication is used. Anyone with the URL can view the stream.
