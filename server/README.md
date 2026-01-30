# RTSP -> WebRTC Server

Dockerized MediaMTX for RTSP ingest and WebRTC playback (sub-second latency).

## Ports

- RTSP ingest: `8554/tcp`
- WebRTC HTTP endpoint: `8889/tcp`
- WebRTC media (UDP): `8189/udp`

## URLs

- Ingest: `rtsp://<server-host>:8554/stream`
- Viewer page: `http://<server-host>:8889/stream` or `https://cam.<domain>/stream`

## Deployment modes

1. Direct access on port `:8889`
   - Open `http://<server-host>:8889/stream` in a browser on the same LAN.
   - For remote access, browsers require HTTPS for WebRTC.

2. Behind a reverse proxy (SWAG/NGINX/etc)
   - Proxy `cam.<domain>` to `http://127.0.0.1:8889`.
   - Enable TLS on the proxy so browsers allow WebRTC.

## Firewall notes

- Allow TCP `8554` from the Pi to the server (outbound from the Pi, inbound on the server).
- Allow TCP `8889` (from proxy or LAN) and UDP `8189` for WebRTC media.

## NAT note

If viewers connect from outside your LAN, set `webrtcAdditionalHosts` in `mediamtx.yml` to your public IP/hostname and consider adding STUN/TURN servers.

## Security note

This setup has no authentication. Anyone with the URL can view the stream.

## Quick start

From this folder:

```sh
./scripts/up.sh
```

Then push from the Pi to the ingest URL above.

## Health check

```sh
./scripts/healthcheck.sh
```
