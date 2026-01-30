# Pi RTSP Streamer

Minimal client to push a V4L2 camera stream to a MediaMTX server for WebRTC playback.

## Install deps

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## Quick test (one-shot)

```sh
RTSP_URL=rtsp://<server-host>:8554/stream ./stream.sh
```

Note: the default stream disables audio and forces H.264 baseline + yuv420p for browser compatibility.

## Configuration via `/etc/cam-stream.env`

Create `./config.env` (copy from `config.env.example`) and edit values:

```sh
cp ./config.env.example ./config.env
${EDITOR:-nano} ./config.env
```

`./systemd/install.sh` will copy `./config.env` to `/etc/cam-stream.env` and restart the service.

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

Quick install (copies files and enables service):

```sh
./systemd/install.sh
```

## Troubleshooting

- Logs: `journalctl -u cam-stream -f`
- Verify camera device exists: `ls -l /dev/video0`
- Test RTSP TCP connectivity: `nc -vz <server-host> 8554`
- Server-side: open `http://<server-host>:8889/stream` on LAN

## Security note

No authentication is used. Anyone with the URL can view the stream.
