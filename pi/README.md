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

## MQTT control (start/stop on mqtt-video flag)

Create `./mqtt_config.json` (copy from `mqtt_config.json.template`) and edit values:

```sh
cp ./mqtt_config.json.template ./mqtt_config.json
${EDITOR:-nano} ./mqtt_config.json
```

The MQTT helper listens on:

```
{system}/cameras/pitcam/incoming/flags/mqtt-video
{system}/cameras/pitcam/incoming/flags/reboot
{system}/cameras/pitcam/incoming/flags/git-pull
```

`true` starts `cam-stream`; `false` stops it.

`true` on `flags/reboot` issues a one-shot reboot command.

`true` on `flags/git-pull` issues a one-shot repo update command.

Safety behavior:

- `reboot` and `git-pull` requests are expected to be non-retained.
- Retained `reboot` and `git-pull` requests are ignored by default.
- `reboot` uses a default 30 second cooldown.
- `git-pull` uses a default 60 second cooldown and ignores overlapping runs.

It publishes liveness/status to:

```
{system}/cameras/pitcam/outgoing/online
{system}/cameras/pitcam/outgoing/heartbeat
{system}/cameras/pitcam/outgoing/status
```

`./systemd/install.sh` will copy `./mqtt_config.json` to `/etc/pitcam-mqtt.json`.

Optional: set `webrtc_url` in the config to advertise a viewer link to the PebbleBot UI.
If reboot or git-pull commands are configured, the status payload also advertises those control topics.

Remote command config lives in `mqtt_config.json`:

- `reboot_control.command`
  - Command to run for `incoming/flags/reboot`. Example: `["sudo", "-n", "/sbin/reboot"]`
- `reboot_control.cwd`
  - Optional working directory for the reboot command.
- `reboot_control.ignore_retained`
  - Default `true`.
- `reboot_control.cooldown_seconds`
  - Default `30`.
- `git_pull_control.command`
  - Command to run for `incoming/flags/git-pull`. Leave empty to disable.
- `git_pull_control.cwd`
  - Repo path on the Pi where `git pull` should run.
- `git_pull_control.env`
  - Optional environment overrides for the git-pull command.
- `git_pull_control.ignore_retained`
  - Default `true`.
- `git_pull_control.cooldown_seconds`
  - Default `60`.

Example git-pull setup:

```json
"git_pull_control": {
  "command": ["git", "pull", "--ff-only"],
  "cwd": "/home/pi/simple-web-video",
  "env": {},
  "ignore_retained": true,
  "cooldown_seconds": 60
}
```

This only works if the Pi is actually running from a git checkout. If you only copied files into `/opt/cam`, there is no repo there for `git pull`.

## Reboot permission setup

If `reboot_control.command` uses `sudo`, the runtime user must be allowed to reboot without an interactive password prompt. Edit sudoers with:

```sh
sudo visudo
```

Add a rule like this, replacing `pi` with the service user:

```text
pi ALL=(root) NOPASSWD: /sbin/reboot
```

`sudoers` is the right file; `visudo` is the safe way to edit it.

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
