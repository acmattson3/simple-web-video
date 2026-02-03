# Pi RTSP Streamer

Minimal client to push a V4L2 camera stream to a MediaMTX server for WebRTC playback.

## Install deps

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg python3-paho-mqtt
```

## Quick test (one-shot)

```sh
RTSP_URL=rtsp://<server-host>:8554/stream ./stream.sh
```

Note: the default stream disables audio and forces H.264 baseline + yuv420p for browser compatibility.

## Stream configuration via `/etc/cam-stream.env`

Create `./config.env` (copy from `config.env.example`) and edit values:

```sh
cp ./config.env.example ./config.env
${EDITOR:-nano} ./config.env
```

`./systemd/install.sh` will copy `./config.env` to `/etc/cam-stream.env`.

## MQTT control (start/stop on command)

Create `./mqtt_config.json` (copy from `mqtt_config.json.template`) and edit values:

```sh
cp ./mqtt_config.json.template ./mqtt_config.json
${EDITOR:-nano} ./mqtt_config.json
```

The MQTT helper listens on:

```
{system}/components/cameras/pitcam/incoming/front-camera
```

and publishes online heartbeats to:

```

`./systemd/install.sh` will copy `./mqtt_config.json` to `/etc/pitcam-mqtt.json`.

Optional: set `webrtc_url` in the config to advertise a viewer link to the PebbleBot UI.
{system}/components/cameras/pitcam/outgoing/online
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

3. Reload:

```sh
sudo systemctl daemon-reload
```

Quick install (copies files, installs MQTT helper, enables watchdog/timer):

```sh
./systemd/install.sh
```

This will:
- install `cam-stream` (disabled by default)
- install and start `pitcam-mqtt`
- install and start a watchdog timer

## Troubleshooting

- Logs: `journalctl -u pitcam-mqtt -f`
- Stream logs: `journalctl -u cam-stream -f`
- Verify camera device exists: `ls -l /dev/video0`
- Test RTSP TCP connectivity: `nc -vz <server-host> 8554`
- Server-side: open `http://<server-host>:8889/stream` on LAN

## Security note

No authentication is used. Anyone with the URL can view the stream.
