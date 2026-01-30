#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME=cam-stream
SERVICE_FILE="${SERVICE_NAME}.service"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SRC_DIR}/.." && pwd)"
CFG_SRC="${ROOT_DIR}/config.env"
CFG_DEST="/etc/cam-stream.env"

sudo mkdir -p /opt/cam
sudo cp -r "${ROOT_DIR}/stream.sh" "${ROOT_DIR}/stream.py" /opt/cam/

sudo cp "${SRC_DIR}/${SERVICE_FILE}" "/etc/systemd/system/${SERVICE_FILE}"

if [[ -f "${CFG_SRC}" ]]; then
  sudo cp "${CFG_SRC}" "${CFG_DEST}"
  echo "Installed config: ${CFG_DEST}"
else
  echo "Warning: ${CFG_SRC} not found. Create it from config.env.example." >&2
fi

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "Installed and started ${SERVICE_NAME}. Use: systemctl status ${SERVICE_NAME}"
