# simple-web-video

Minimal setup for sub-second latency: Pi pushes RTSP to server; server serves WebRTC on a subdomain.

## How it works

This repo implements a minimal live video pipeline with two parts: a server and a Pi client. The server runs MediaMTX in Docker (`server/docker-compose.yml`) and exposes RTSP ingest on `8554`, plus a WebRTC viewer endpoint on `8889` (with UDP media on `8189`). The MediaMTX config defines a single `stream` path, so a publisher sends video to `rtsp://<server-host>:8554/stream` and viewers open `http://<server-host>:8889/stream` (or `https://cam.<domain>/stream` behind a TLS reverse proxy).

On the Pi side, `stream.sh` captures `/dev/video0` and pushes low-latency H.264 to the RTSP URL. For managed operation, systemd installs `cam-stream` plus an MQTT bridge (`pitcam_mqtt.py`) that listens for front-camera enable/disable commands and starts or stops the stream service with `systemctl`. The MQTT bridge also publishes online heartbeats and optional status metadata (like a WebRTC URL), while a watchdog timer keeps the control service healthy.

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
sudo apt-get install -y ffmpeg python3-paho-mqtt
```

Quick test:

```sh
RTSP_URL=rtsp://<server-host>:8554/stream ./pi/stream.sh
```

Systemd + MQTT control (recommended):

1. Create a local config file:

```sh
cp ./pi/config.env.example ./pi/config.env
${EDITOR:-nano} ./pi/config.env
```

2. Create MQTT config:

```sh
cp ./pi/mqtt_config.json.template ./pi/mqtt_config.json
${EDITOR:-nano} ./pi/mqtt_config.json
```

3. Install + enable the services (copies files, config, and restarts):

```sh
./pi/systemd/install.sh
```

The camera stream is started/stopped via MQTT:

```
pebblebot/components/cameras/pitcam/incoming/front-camera
```

`cam-stream` is installed but disabled by default; the MQTT helper toggles it.

Manual systemd (if you prefer):

```sh
sudo mkdir -p /opt/cam
sudo cp -r ./pi/stream.sh ./pi/stream.py ./pi/pitcam_mqtt.py /opt/cam/
sudo cp ./pi/systemd/cam-stream.service /etc/systemd/system/cam-stream.service
sudo cp ./pi/config.env /etc/cam-stream.env
sudo cp ./pi/systemd/pitcam-mqtt.service /etc/systemd/system/pitcam-mqtt.service
sudo cp ./pi/systemd/pitcam-mqtt-watchdog.service /etc/systemd/system/pitcam-mqtt-watchdog.service
sudo cp ./pi/systemd/pitcam-mqtt-watchdog.timer /etc/systemd/system/pitcam-mqtt-watchdog.timer
sudo cp ./pi/mqtt_config.json /etc/pitcam-mqtt.json
sudo systemctl daemon-reload
sudo systemctl enable --now pitcam-mqtt
sudo systemctl enable --now pitcam-mqtt-watchdog.timer
```

Config notes:

- The service reads `/etc/cam-stream.env`.
- The MQTT helper reads `/etc/pitcam-mqtt.json`.
- Rerun `./pi/systemd/install.sh` after changing `./pi/config.env` or `./pi/mqtt_config.json` to apply updates.
- See `pi/README.md` for all options.

## Security note

No authentication is used. Anyone with the URL can view the stream.
