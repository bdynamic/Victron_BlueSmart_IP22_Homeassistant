#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Send VE.Direct command to set the charging current for a Victron Blue Smart charger via serial.
"""

import argparse
import serial
import logging


def build_vedirect_current_command(current: float) -> str:
    """
    Build a VE.Direct-style serial command for setting the charging current.

    Args:
        current (float): Desired charging current in amps.

    Returns:
        str: Full VE.Direct command string.
    """
    numP1 = int(current * 10)
    numP2 = (0x70 - numP1) & 0xFF
    hexP1 = f"{numP1:02X}"
    hexP2 = f"{numP2:02X}"
    return f":8F0ED00{hexP1}{'00'}{hexP2}\n"


def send_charging_current(serial_port: str, current: float) -> None:
    """
    Open the serial port and send the charging current command.

    Args:
        serial_port (str): Serial device (e.g., /dev/ttyUSB0).
        current (float): Charging current in amps.
    """
    try:
        with serial.Serial(serial_port, baudrate=19200, timeout=1) as ser:
            cmd = build_vedirect_current_command(current)
            logging.info(f"Sending command: {cmd.strip()}")
            ser.write(cmd.encode("ascii"))
    except serial.SerialException as e:
        logging.error(f"Failed to open serial port: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Set charging current over VE.Direct serial")
    parser.add_argument("--device", required=True, help="Serial device (e.g., /dev/ttyUSB0)")
    parser.add_argument("--current", required=True, type=float, help="Charging current in amps (e.g., 10.5)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    send_charging_current(args.device, args.current)
