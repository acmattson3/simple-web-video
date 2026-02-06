# syntax=docker/dockerfile:1
FROM bluenviron/mediamtx:latest

# Bake in the default server configuration from this repo.
COPY mediamtx.yml /mediamtx.yml

EXPOSE 8554/tcp
EXPOSE 8889/tcp
EXPOSE 8189/udp
