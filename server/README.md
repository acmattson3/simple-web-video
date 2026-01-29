# RTMP -> HLS Server

Dockerized NGINX with RTMP ingest and HLS output.

## Ports

- RTMP ingest: `1935/tcp`
- HTTP (HLS + player): `8080/tcp`

## URLs

- Ingest: `rtmp://<server-host>/live/stream`
- Viewer page: `http://<server-host>:8080/` or `https://cam.<domain>/`
- HLS playlist: `http://<server-host>:8080/hls/stream.m3u8`

## Deployment modes

1. Direct access on port `:8080`
   - Open `http://<server-host>:8080/` in a browser.

2. Behind a reverse proxy (SWAG/NGINX/etc)
   - Proxy `cam.<domain>` to `http://127.0.0.1:8080`.

## Firewall notes

- Allow TCP `1935` from the Pi to the server (outbound from the Pi, inbound on the server).
- For viewers, open `80/443` on the reverse proxy (or `8080` if using direct access).

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
