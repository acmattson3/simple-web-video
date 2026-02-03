#!/usr/bin/env bash
set -euo pipefail

STREAM_SERVICE=cam-stream
STREAM_SERVICE_FILE="${STREAM_SERVICE}.service"
MQTT_SERVICE=pitcam-mqtt
MQTT_SERVICE_FILE="${MQTT_SERVICE}.service"
WATCHDOG_SERVICE=pitcam-mqtt-watchdog.service
WATCHDOG_TIMER=pitcam-mqtt-watchdog.timer
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SRC_DIR}/.." && pwd)"
STREAM_CFG_SRC="${ROOT_DIR}/config.env"
STREAM_CFG_DEST="/etc/cam-stream.env"
MQTT_CFG_SRC="${ROOT_DIR}/mqtt_config.json"
MQTT_CFG_DEST="/etc/pitcam-mqtt.json"

sudo mkdir -p /opt/cam
sudo cp -r "${ROOT_DIR}/stream.sh" "${ROOT_DIR}/stream.py" "${ROOT_DIR}/pitcam_mqtt.py" /opt/cam/

sudo systemctl disable --now "${STREAM_SERVICE}" >/dev/null 2>&1 || true
sudo systemctl disable --now "${MQTT_SERVICE}" >/dev/null 2>&1 || true
sudo systemctl disable --now "${WATCHDOG_TIMER}" >/dev/null 2>&1 || true
sudo systemctl disable --now "${WATCHDOG_SERVICE}" >/dev/null 2>&1 || true

sudo rm -f "/etc/systemd/system/${STREAM_SERVICE_FILE}" \
  "/etc/systemd/system/${MQTT_SERVICE_FILE}" \
  "/etc/systemd/system/${WATCHDOG_SERVICE}" \
  "/etc/systemd/system/${WATCHDOG_TIMER}"

sudo cp "${SRC_DIR}/${STREAM_SERVICE_FILE}" "/etc/systemd/system/${STREAM_SERVICE_FILE}"
sudo cp "${SRC_DIR}/${MQTT_SERVICE_FILE}" "/etc/systemd/system/${MQTT_SERVICE_FILE}"
sudo cp "${SRC_DIR}/${WATCHDOG_SERVICE}" "/etc/systemd/system/${WATCHDOG_SERVICE}"
sudo cp "${SRC_DIR}/${WATCHDOG_TIMER}" "/etc/systemd/system/${WATCHDOG_TIMER}"

if [[ -f "${STREAM_CFG_SRC}" ]]; then
  sudo cp "${STREAM_CFG_SRC}" "${STREAM_CFG_DEST}"
  echo "Installed stream config: ${STREAM_CFG_DEST}"
else
  echo "Warning: ${STREAM_CFG_SRC} not found. Create it from config.env.example." >&2
fi

if [[ -f "${MQTT_CFG_SRC}" ]]; then
  sudo cp "${MQTT_CFG_SRC}" "${MQTT_CFG_DEST}"
  echo "Installed MQTT config: ${MQTT_CFG_DEST}"
else
  echo "Warning: ${MQTT_CFG_SRC} not found. Create it from mqtt_config.json.template." >&2
fi

sudo systemctl daemon-reload
sudo systemctl enable --now "${MQTT_SERVICE}"
sudo systemctl enable --now "${WATCHDOG_TIMER}"

echo "Installed ${STREAM_SERVICE} (manual start/stop) and started ${MQTT_SERVICE}."
echo "Use: systemctl status ${MQTT_SERVICE}"
