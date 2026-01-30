# simple-web-video

Minimal setup for: Pi pushes RTMP to server; server serves HLS on a subdomain.

## Server-side (RTMP + HLS)

From `server/`:

```sh
./scripts/up.sh
```

Ports:

- RTMP ingest: `1935/tcp`
- HLS/player: `8080/tcp`

URLs:

- Ingest: `rtmp://<server-host>/live/stream`
- Player: `http://<server-host>:8080/` or `https://cam.<domain>/`
- HLS: `http://<server-host>:8080/hls/stream.m3u8`

Reverse proxy mode:

- Proxy `cam.<domain>` to `http://127.0.0.1:8080`.

Health check:

```sh
./scripts/healthcheck.sh
```

## User-side (viewer)

- Open `https://cam.<domain>/` (recommended) or `http://<server-host>:8080/`.
- The page auto-loads `/hls/stream.m3u8` with native HLS or hls.js.

## Pi-side (streamer)

Install deps:

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg
```

Quick test:

```sh
RTMP_URL=rtmp://<server-host>/live/stream ./pi/stream.sh
```

Note: the default stream disables audio and forces H.264 baseline + yuv420p for browser compatibility.

Optional systemd:

```sh
sudo mkdir -p /opt/cam
sudo cp -r ./pi/stream.sh ./pi/stream.py /opt/cam/
sudo cp ./pi/systemd/cam-stream.service /etc/systemd/system/cam-stream.service
sudo systemctl daemon-reload
sudo systemctl enable --now cam-stream
```

Create `/etc/cam-stream.env` to override defaults (bitrate, resolution, etc). See `pi/README.md`.

## Security note

No authentication is used. Anyone with the URL can view the stream.
