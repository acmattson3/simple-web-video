#!/usr/bin/env python3
import argparse
import json
import logging
import os
import shlex
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


def _normalize_command(command: Any) -> list[str]:
    if isinstance(command, str):
        parts = shlex.split(command)
    elif isinstance(command, list):
        parts = [str(item) for item in command if item is not None]
    else:
        raise ValueError("command must be string or list")
    if not parts:
        raise ValueError("command cannot be empty")
    return parts


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

        self.video_flag_topic = (
            f"{self.system}/{self.component_type}/{self.component_id}/incoming/flags/mqtt-video"
        )
        self.online_topic = (
            f"{self.system}/{self.component_type}/{self.component_id}/outgoing/online"
        )
        self.heartbeat_topic = (
            f"{self.system}/{self.component_type}/{self.component_id}/outgoing/heartbeat"
        )
        self.status_topic = (
            f"{self.system}/{self.component_type}/{self.component_id}/outgoing/status"
        )
        self.reboot_flag_topic = (
            f"{self.system}/{self.component_type}/{self.component_id}/incoming/flags/reboot"
        )
        self.git_pull_flag_topic = (
            f"{self.system}/{self.component_type}/{self.component_id}/incoming/flags/git-pull"
        )

        self.client = mqtt.Client(client_id=f"{self.component_id}-mqtt")
        self.client.max_inflight_messages_set(1)
        self.client.max_queued_messages_set(8)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
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
        self._connected = threading.Event()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._host = str(mqtt_cfg.get("host") or "")
        self._port = int(mqtt_cfg.get("port") or 1883)
        self._keepalive = int(mqtt_cfg.get("keepalive") or 30)
        self._mqtt_video_enabled = False
        self._reboot_control_cfg = (
            config.get("reboot_control", {}) if isinstance(config.get("reboot_control"), dict) else {}
        )
        self._git_pull_control_cfg = (
            config.get("git_pull_control", {}) if isinstance(config.get("git_pull_control"), dict) else {}
        )
        self._last_reboot_request_at = 0.0
        self._last_git_pull_request_at = 0.0
        self._git_pull_process: Optional[subprocess.Popen[Any]] = None

    def _apply_video_state(self, reason: str) -> None:
        should_run = self._mqtt_video_enabled
        action = "start" if should_run else "stop"
        logging.info(
            "Video state update (%s): mqtt-video=%s -> systemctl %s %s",
            reason,
            self._mqtt_video_enabled,
            action,
            self.stream_service,
        )
        _run_systemctl(action, self.stream_service)

    def _publish_online(self, online: bool) -> None:
        payload = {"t": _now_ms() if online else 0, "online": bool(online)}
        self.client.publish(self.online_topic, json.dumps(payload), qos=1, retain=True)

    def _publish_heartbeat(self, timestamp_ms: Optional[int] = None) -> None:
        t = _now_ms() if timestamp_ms is None else int(timestamp_ms)
        self.client.publish(self.heartbeat_topic, json.dumps({"t": t}), qos=0, retain=False)

    def _publish_status(self) -> None:
        value: Dict[str, Any] = {}
        if self.webrtc_url:
            value["webrtc_url"] = self.webrtc_url
        if self._reboot_command():
            value["reboot"] = {
                "available": True,
                "flag_topic": self.reboot_flag_topic,
            }
        if self._git_pull_command():
            value["git_pull"] = {
                "available": True,
                "flag_topic": self.git_pull_flag_topic,
            }
        if not value:
            return
        payload = {
            "timestamp": time.time(),
            "value": value,
        }
        self.client.publish(self.status_topic, json.dumps(payload), qos=0, retain=True)

    def _on_connect(self, _client: mqtt.Client, _userdata: Any, _flags: Dict[str, Any], rc: int) -> None:
        if rc != 0:
            logging.error("MQTT connection failed: %s", mqtt.connack_string(rc))
            return
        logging.info("MQTT connected")
        self._connected.set()
        self.client.subscribe(self.video_flag_topic, qos=1)
        self.client.subscribe(self.reboot_flag_topic, qos=1)
        self.client.subscribe(self.git_pull_flag_topic, qos=1)
        self._publish_online(True)
        self._publish_heartbeat()
        self._publish_status()
        _systemd_notify("READY=1")

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int) -> None:
        self._connected.clear()
        if rc != mqtt.MQTT_ERR_SUCCESS:
            logging.error("MQTT disconnected (rc=%s); exiting for restart", rc)
            self._stop_event.set()

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        enabled = _extract_enabled(msg.payload)
        if msg.topic == self.video_flag_topic:
            if enabled is None:
                logging.warning("Invalid mqtt-video flag payload: %s", msg.payload)
                return
            self._mqtt_video_enabled = enabled
            self._apply_video_state("flags/mqtt-video")
            return
        if msg.topic == self.reboot_flag_topic:
            self._handle_reboot_request(enabled, bool(msg.retain), msg.payload)
            return
        if msg.topic == self.git_pull_flag_topic:
            self._handle_git_pull_request(enabled, bool(msg.retain), msg.payload)

    @staticmethod
    def _resolve_cwd(cwd_value: Any) -> Optional[str]:
        if not cwd_value:
            return None
        return str(os.path.abspath(os.path.expanduser(str(cwd_value))))

    @staticmethod
    def _build_env(env_overrides: Any) -> Dict[str, str]:
        env = os.environ.copy()
        if isinstance(env_overrides, dict):
            env.update({str(k): str(v) for k, v in env_overrides.items()})
        return env

    def _reboot_command(self) -> Any:
        return self._reboot_control_cfg.get("command")

    def _git_pull_command(self) -> Any:
        return self._git_pull_control_cfg.get("command")

    def _start_reboot_command(self) -> None:
        command = self._reboot_command()
        if not command:
            logging.warning("reboot flag received but reboot_control.command is missing")
            return
        try:
            proc = subprocess.Popen(
                _normalize_command(command),
                cwd=self._resolve_cwd(self._reboot_control_cfg.get("cwd")),
                env=self._build_env(self._reboot_control_cfg.get("env")),
            )
            logging.warning("Issued reboot command pid=%s", proc.pid)
        except (OSError, ValueError) as exc:
            logging.error("Failed to execute reboot command: %s", exc)

    def _start_git_pull_command(self) -> None:
        command = self._git_pull_command()
        if not command:
            logging.warning("git-pull flag received but git_pull_control.command is missing")
            return
        existing = self._git_pull_process
        if existing and existing.poll() is None:
            logging.warning("Ignoring git-pull request while previous git pull command is still running")
            return
        try:
            proc = subprocess.Popen(
                _normalize_command(command),
                cwd=self._resolve_cwd(self._git_pull_control_cfg.get("cwd")),
                env=self._build_env(self._git_pull_control_cfg.get("env")),
            )
            self._git_pull_process = proc
            logging.warning("Issued git pull command pid=%s", proc.pid)
        except (OSError, ValueError) as exc:
            logging.error("Failed to execute git pull command: %s", exc)

    def _handle_reboot_request(self, enabled: Optional[bool], retained: bool, payload: bytes) -> None:
        if enabled is None:
            logging.warning("Invalid reboot flag payload: %s", payload)
            return
        if not enabled:
            return
        if retained and bool(self._reboot_control_cfg.get("ignore_retained", True)):
            logging.warning("Ignoring retained reboot request on %s", self.reboot_flag_topic)
            return
        cooldown = float(self._reboot_control_cfg.get("cooldown_seconds") or 30)
        now = time.monotonic()
        elapsed = now - self._last_reboot_request_at
        if elapsed < cooldown:
            logging.warning(
                "Ignoring reboot request on %s during cooldown (%.1fs remaining)",
                self.reboot_flag_topic,
                cooldown - elapsed,
            )
            return
        self._last_reboot_request_at = now
        self._start_reboot_command()

    def _handle_git_pull_request(self, enabled: Optional[bool], retained: bool, payload: bytes) -> None:
        if enabled is None:
            logging.warning("Invalid git-pull flag payload: %s", payload)
            return
        if not enabled:
            return
        if retained and bool(self._git_pull_control_cfg.get("ignore_retained", True)):
            logging.warning("Ignoring retained git-pull request on %s", self.git_pull_flag_topic)
            return
        cooldown = float(self._git_pull_control_cfg.get("cooldown_seconds") or 60)
        now = time.monotonic()
        elapsed = now - self._last_git_pull_request_at
        if elapsed < cooldown:
            logging.warning(
                "Ignoring git-pull request on %s during cooldown (%.1fs remaining)",
                self.git_pull_flag_topic,
                cooldown - elapsed,
            )
            return
        self._last_git_pull_request_at = now
        self._start_git_pull_command()

    def _heartbeat_loop(self) -> None:
        interval = max(1, self.heartbeat_interval)
        while not self._stop_event.is_set():
            try:
                if self._connected.is_set():
                    self._publish_heartbeat()
                    _systemd_notify("WATCHDOG=1")
            except Exception:
                logging.exception("Heartbeat failed")
            self._stop_event.wait(interval)

    def run(self) -> int:
        if not self._host:
            logging.error("MQTT host not configured.")
            return 2
        self._apply_video_state("startup-default")
        try:
            self.client.connect_async(self._host, self._port, self._keepalive)
        except Exception:
            logging.exception("Failed to connect to MQTT broker")
            return 2
        self.client.loop_start()
        self._heartbeat_thread.start()
        while not self._stop_event.is_set():
            time.sleep(0.2)
        try:
            if self._connected.is_set():
                self._publish_online(False)
                self._publish_heartbeat(0)
                time.sleep(0.2)
        except Exception:
            logging.exception("Failed to publish offline state")
        self.client.loop_stop()
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
