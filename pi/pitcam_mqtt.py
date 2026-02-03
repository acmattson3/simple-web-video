#!/usr/bin/env python3
import argparse
import json
import logging
import os
import signal
import ssl
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt


DEFAULT_HEARTBEAT = 10
DEFAULT_SYSTEM = "pebblebot"
DEFAULT_COMPONENT_TYPE = "cameras"
DEFAULT_COMPONENT_ID = "pitcam"
DEFAULT_STREAM_SERVICE = "cam-stream"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_tls(cfg: Any) -> Dict[str, Any]:
    if isinstance(cfg, bool):
        return {"enabled": cfg}
    if isinstance(cfg, dict):
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "ca_cert": cfg.get("ca_cert") or "",
            "client_cert": cfg.get("client_cert") or "",
            "client_key": cfg.get("client_key") or "",
            "insecure": bool(cfg.get("insecure", False)),
            "ciphers": cfg.get("ciphers") or "",
        }
    return {"enabled": False}


def _apply_tls(client: mqtt.Client, tls_cfg: Dict[str, Any]) -> None:
    if not tls_cfg.get("enabled"):
        return
    ca_cert = tls_cfg.get("ca_cert") or None
    client_cert = tls_cfg.get("client_cert") or None
    client_key = tls_cfg.get("client_key") or None
    ciphers = tls_cfg.get("ciphers") or None
    client.tls_set(
        ca_certs=ca_cert,
        certfile=client_cert,
        keyfile=client_key,
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
        ciphers=ciphers,
    )
    if tls_cfg.get("insecure"):
        client.tls_insecure_set(True)


def _extract_enabled(payload: bytes) -> Optional[bool]:
    raw = payload.strip()
    if raw in (b"true", b"false"):
        return raw == b"true"
    try:
        data = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        if isinstance(data.get("enabled"), bool):
            return bool(data.get("enabled"))
        if isinstance(data.get("value"), bool):
            return bool(data.get("value"))
    return None


def _run_systemctl(action: str, service: str) -> None:
    subprocess.run(["systemctl", action, service], check=False)


def _systemd_notify(message: str) -> None:
    if not os.environ.get("NOTIFY_SOCKET"):
        return
    subprocess.run(["systemd-notify", message], check=False)


class PitcamController:
    def __init__(self, config: Dict[str, Any]) -> None:
        component = config.get("component", {}) if isinstance(config.get("component"), dict) else {}
        mqtt_cfg = config.get("mqtt", {}) if isinstance(config.get("mqtt"), dict) else {}
        tls_cfg = _normalize_tls(mqtt_cfg.get("tls"))

        self.system = str(config.get("system") or DEFAULT_SYSTEM)
        self.component_type = str(component.get("type") or DEFAULT_COMPONENT_TYPE)
        self.component_id = str(component.get("id") or DEFAULT_COMPONENT_ID)
        self.heartbeat_interval = int(config.get("heartbeat_interval") or DEFAULT_HEARTBEAT)
        self.stream_service = str(config.get("stream_service") or DEFAULT_STREAM_SERVICE)
        self.webrtc_url = str(config.get("webrtc_url") or "").strip()

        self.command_topic = (
            f"{self.system}/components/{self.component_type}/{self.component_id}/incoming/front-camera"
        )
        self.online_topic = (
            f"{self.system}/components/{self.component_type}/{self.component_id}/outgoing/online"
        )
        self.status_topic = (
            f"{self.system}/components/{self.component_type}/{self.component_id}/outgoing/status"
        )

        self.client = mqtt.Client(client_id=f"{self.component_id}-mqtt")
        if mqtt_cfg.get("username"):
            self.client.username_pw_set(
                mqtt_cfg.get("username"),
                mqtt_cfg.get("password") or None,
            )
        _apply_tls(self.client, tls_cfg)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.will_set(
            self.online_topic,
            json.dumps({"t": 0, "online": False}),
            qos=1,
            retain=True,
        )

        self._stop_event = threading.Event()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._host = str(mqtt_cfg.get("host") or "")
        self._port = int(mqtt_cfg.get("port") or 1883)
        self._keepalive = int(mqtt_cfg.get("keepalive") or 30)

    def _publish_online(self, online: bool) -> None:
        payload = {"t": _now_ms(), "online": bool(online)}
        self.client.publish(self.online_topic, json.dumps(payload), qos=1, retain=True)

    def _publish_status(self) -> None:
        if not self.webrtc_url:
            return
        payload = {
            "timestamp": time.time(),
            "value": {"webrtc_url": self.webrtc_url},
        }
        self.client.publish(self.status_topic, json.dumps(payload), qos=1, retain=True)

    def _on_connect(self, _client: mqtt.Client, _userdata: Any, _flags: Dict[str, Any], rc: int) -> None:
        if rc != 0:
            logging.error("MQTT connection failed: %s", mqtt.connack_string(rc))
            return
        logging.info("MQTT connected")
        self.client.subscribe(self.command_topic, qos=1)
        self._publish_online(True)
        self._publish_status()
        _systemd_notify("READY=1")

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int) -> None:
        if rc != mqtt.MQTT_ERR_SUCCESS:
            logging.error("MQTT disconnected (rc=%s); exiting for restart", rc)
            self._stop_event.set()

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if msg.topic != self.command_topic:
            return
        enabled = _extract_enabled(msg.payload)
        if enabled is None:
            logging.warning("Invalid front-camera payload: %s", msg.payload)
            return
        action = "start" if enabled else "stop"
        logging.info("Received front-camera=%s; systemctl %s %s", enabled, action, self.stream_service)
        _run_systemctl(action, self.stream_service)

    def _heartbeat_loop(self) -> None:
        interval = max(1, self.heartbeat_interval)
        while not self._stop_event.is_set():
            try:
                self._publish_online(True)
                self._publish_status()
                _systemd_notify("WATCHDOG=1")
            except Exception:
                logging.exception("Heartbeat failed")
            self._stop_event.wait(interval)

    def run(self) -> int:
        if not self._host:
            logging.error("MQTT host not configured.")
            return 2
        self._heartbeat_thread.start()
        try:
            self.client.connect(self._host, self._port, self._keepalive)
        except Exception:
            logging.exception("Failed to connect to MQTT broker")
            return 2
        self.client.loop_start()
        while not self._stop_event.is_set():
            time.sleep(0.2)
        self.client.loop_stop()
        try:
            self._publish_online(False)
        except Exception:
            logging.exception("Failed to publish offline state")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Pitcam MQTT bridge")
    parser.add_argument("--config", default="/etc/pitcam-mqtt.json", help="Path to MQTT config JSON")
    args = parser.parse_args()

    try:
        config = _load_config(args.config)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 2

    log_level = str(config.get("log_level") or "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")

    controller = PitcamController(config)

    def _handle_signal(_signum: int, _frame: Any) -> None:
        controller._stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    return controller.run()


if __name__ == "__main__":
    raise SystemExit(main())
