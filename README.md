# simple-web-video

Minimal setup for sub-second latency: Pi pushes RTSP to server; server serves WebRTC on a subdomain.

## Server-side (RTSP + WebRTC)

From `server/`:

```sh
./scripts/up.sh
```

Ports:

- RTSP ingest: `8554/tcp`
- WebRTC HTTP: `8889/tcp`
- WebRTC media: `8189/udp`

URLs:

- Ingest: `rtsp://<server-host>:8554/stream`
- Viewer: `http://<server-host>:8889/stream` or `https://cam.<domain>/stream`

Reverse proxy mode:

- Proxy `cam.<domain>` to `http://127.0.0.1:8889` and enable TLS.

Health check:

```sh
./scripts/healthcheck.sh
```

## User-side (viewer)

- Open `https://cam.<domain>/stream` (recommended) or `http://<server-host>:8889/stream` on LAN.
- WebRTC requires HTTPS on non-localhost.

## Pi-side (streamer)

Install deps:

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg
```

Quick test:

```sh
RTSP_URL=rtsp://<server-host>:8554/stream ./pi/stream.sh
```

Systemd (recommended):

1. Create a local config file:

```sh
cp ./pi/config.env.example ./pi/config.env
${EDITOR:-nano} ./pi/config.env
```

2. Install + enable the service (copies files, config, and restarts):

```sh
./pi/systemd/install.sh
```

Manual systemd (if you prefer):

```sh
sudo mkdir -p /opt/cam
sudo cp -r ./pi/stream.sh ./pi/stream.py /opt/cam/
sudo cp ./pi/systemd/cam-stream.service /etc/systemd/system/cam-stream.service
sudo cp ./pi/config.env /etc/cam-stream.env
sudo systemctl daemon-reload
sudo systemctl enable --now cam-stream
```

Config notes:

- The service reads `/etc/cam-stream.env`.
- Rerun `./pi/systemd/install.sh` after changing `./pi/config.env` to apply updates.
- See `pi/README.md` for all options.

## Security note

No authentication is used. Anyone with the URL can view the stream.
