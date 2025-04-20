#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VE.Direct → MQTT logger + current‑limit setter for Victron Blue Smart Charger.

  - Reads voltage/current from serial
  - Publishes via MQTT Discovery + state/availability topics
  - Subscribes to an MQTT “current_limit” topic and sends VE.Direct set‑current commands
  - Marks sensors unavailable if no data for 30 s
  - If no serial data for ≥5 min, waits for first block, then after 10 s re‑sends the current limit
"""

import argparse
import json
import logging
import threading
import time
from typing import Dict, List

import paho.mqtt.client as mqtt
import serial
import yaml


def load_config(path: str) -> dict:
    """Load YAML configuration from a file path."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Config load failed ({path}): {e}")
        raise


def setup_logger(level: str) -> None:
    """Configure logging format & level."""
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def connect_mqtt(cfg: dict, on_message_cb) -> mqtt.Client:
    """
    Connect to MQTT broker, set up callbacks, and start loop thread.
    Expects cfg to include host, port, username, password.
    """
    client = mqtt.Client(userdata={})
    if cfg.get('username'):
        client.username_pw_set(cfg['username'], cfg.get('password'))
    client.on_message = on_message_cb
    try:
        client.connect(cfg['host'], cfg.get('port', 1883))
        client.loop_start()
    except Exception as e:
        logging.error(f"MQTT connect failed: {e}")
        raise
    return client


def publish_discovery(
    client: mqtt.Client,
    base: str,
    name: str,
    unique_id: str,
    unit: str,
    device_class: str,
) -> None:
    """
    Publish Home Assistant Discovery for one sensor, including availability.
    """
    cfg = {
        "name": name,
        "state_topic": f"{base}/{name}",
        "availability_topic": f"{base}/status",
        "payload_available": "online",
        "payload_not_available": "offline",
        "unit_of_measurement": unit,
        "device_class": device_class,
        "state_class": "measurement",
        "unique_id": f"{unique_id}_{name}",
        "force_update": True,
        "device": {
            "identifiers": [unique_id],
            "manufacturer": "Victron",
            "model": "Blue Smart Charger",
            "name": unique_id,
        },
    }
    topic = f"homeassistant/sensor/{unique_id}/{name}/config"
    client.publish(topic, json.dumps(cfg), retain=True)
    logging.info(f"Discovery published for '{name}'")


def publish_state(client: mqtt.Client, topic: str, value) -> None:
    """Publish a retained state value."""
    client.publish(topic, payload=value, retain=True)
    logging.debug(f"{topic} ← {value}")


def build_vedirect_current_command(current: float) -> str:
    """
    Build VE.Direct command to set charging current.
    current in amps → P1 = current*10, P2 = (0x70-P1)&0xFF
    """
    p1 = int(current * 10)
    p2 = (0x70 - p1) & 0xFF
    return f":8F0ED00{p1:02X}00{p2:02X}\n"


def send_charging_current(port: str, current: float) -> None:
    """Open serial port and send the set‑current command."""
    try:
        with serial.Serial(port, baudrate=19200, timeout=1) as ser:
            cmd = build_vedirect_current_command(current)
            logging.debug(f"→ Serial CMD: {cmd.strip()}")
            ser.write(cmd.encode('ascii'))
    except Exception as e:
        logging.error(f"Failed to send current {current} A: {e}")


def parse_vedirect_block(lines: List[str]) -> Dict[str, float]:
    """
    Parse tab‑separated VE.Direct lines. Returns keys 'voltage' (V) & 'current' (A).
    """
    out = {}
    for ln in lines:
        parts = ln.split('\t')
        if len(parts) != 2:
            continue
        key, raw = parts
        try:
            val = int(raw)
        except ValueError:
            continue
        if key == 'V':
            out['voltage'] = val / 1000.0
        elif key == 'I':
            out['current'] = val / 1000.0
    logging.debug(f"Parsed VE.Direct → {out}")
    return out


class ChargerController:
    """Holds state and runs the main read/publish loop plus MQTT callback."""
    def __init__(self, cfg: dict):
        self.serial_port = cfg['serial']['port']
        self.baud = cfg['serial'].get('baudrate', 19200)
        self.base = f"{cfg['mqtt'].get('base_topic', cfg['device']['vendor'])}/{cfg['device']['name']}"
        self.uid = f"{cfg['device']['vendor']}_{cfg['device']['name']}"
        self.avail_topic = f"{self.base}/status"
        self.current_limit_topic = cfg['mqtt']['current_limit_topic']
        self.current_limit = float(cfg['device'].get('initial_current_limit', 10.0))
        # time tracking
        self.last_serial = time.time()
        self.need_resend = False
        self.resend_start = None
        self.available = True

        # MQTT client
        self.client = connect_mqtt(cfg['mqtt'], self.on_mqtt_message)
        # subscribe & discovery
        self.client.subscribe(self.current_limit_topic)
        for sensor, cls, unit in (('voltage','voltage','V'), ('current','current','A')):
            publish_discovery(self.client, self.base, sensor, self.uid, unit, cls)
        # initial state/availability
        publish_state(self.client, self.avail_topic, 'online')
        # send limit on startup
        send_charging_current(self.serial_port, self.current_limit)

    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming current_limit updates."""
        if msg.topic != self.current_limit_topic:
            return
        try:
            new = float(msg.payload.decode())
            self.current_limit = new
            logging.info(f"MQTT → new limit: {new} A")
            send_charging_current(self.serial_port, new)
        except ValueError:
            logging.error(f"Invalid limit payload: {msg.payload!r}")

    def run(self):
        """Main loop: read serial, publish, and handle timeouts."""
        buffer: List[str] = []

        try:
            ser = serial.Serial(self.serial_port, self.baud, timeout=1)
        except Exception as e:
            logging.error(f"Cannot open serial: {e}")
            return

        try:
            while True:
                raw = ser.readline()
                now = time.time()

                # handle 30s “unavailable”
                if self.available and now - self.last_serial > 30:
                    publish_state(self.client, self.avail_topic, 'offline')
                    self.available = False

                # handle 5 min gap detection
                if not self.need_resend and now - self.last_serial > 300:
                    self.need_resend = True
                    logging.info("No serial data for 5 min → will re-send limit on next block")

                if not raw:
                    continue

                line = raw.decode('ascii', errors='ignore').strip()
                if line.startswith('Checksum'):
                    # complete block
                    data = parse_vedirect_block(buffer)
                    buffer.clear()

                    # mark available & reset timers
                    if not self.available:
                        publish_state(self.client, self.avail_topic, 'online')
                        self.available = True

                    self.last_serial = now

                    # if gap was long, wait 10 s then resend limit
                    if self.need_resend:
                        if self.resend_start is None:
                            self.resend_start = now
                        elif now - self.resend_start >= 10:
                            logging.info("Re-sending limit after gap")
                            send_charging_current(self.serial_port, self.current_limit)
                            self.need_resend = False
                            self.resend_start = None

                    # publish measurements
                    if 'voltage' in data:
                        publish_state(self.client, f"{self.base}/voltage", data['voltage'])
                    if 'current' in data:
                        publish_state(self.client, f"{self.base}/current", data['current'])

                    # rate-limit: wait 8 seconds before next update
                    logging.debug("Sleeping for 8 seconds to rate-limit updates")
                    time.sleep(8)

                else:
                    buffer.append(line)
        except KeyboardInterrupt:
            logging.info("Interrupted by user")
        finally:
            ser.close()
            self.client.loop_stop()
            self.client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Victron VE.Direct → MQTT + limit setter")
    parser.add_argument('--config', default='config.yaml', help='Path to YAML config')
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logger(cfg.get('log_level', 'INFO'))

    controller = ChargerController(cfg)
    controller.run()


if __name__ == "__main__":
    main()
