#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Serial VE.Direct logger:
- Displays hex stream with timestamp
- Parses VE.Direct-style ASCII data blocks
"""

import argparse
import serial
import time
from datetime import datetime
from collections import deque


def parse_args():
    parser = argparse.ArgumentParser(description="Serial HEX + VE.Direct parser")
    parser.add_argument("--device", required=True, help="Serial device (e.g. /dev/ttyUSB0)")
    parser.add_argument("--pause", type=int, default=50, help="Pause threshold in milliseconds for line break")
    return parser.parse_args()


# VE.Direct block parsing logic
def parse_vedirect_blocks(data_bytes):
    lines = data_bytes.split(b'\r\n')
    block = {}
    blocks = []

    for line in lines:
        if b'\t' in line:
            key, value = line.split(b'\t', 1)
            block[key.decode(errors='ignore')] = value.decode(errors='ignore')
        elif block:
            blocks.append(block)
            block = {}

    if block:
        blocks.append(block)

    return blocks

def print_vedirect_block(block):
    print("\n--- VE.Direct Block ---")
    for k, v in block.items():
        print(f"{k:<8}: {v}")
    print()

def hex_ascii_dump(data: bytes, prefix=""):
    """
    Print hex + ASCII dump in Wireshark-style format.
    """
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{prefix}{offset:04x}  {hex_part:<48}  {ascii_part}")


def receive_serial_data(ser):
    """
    Generator yielding packets based on message terminators:
    - VE.Direct blocks end with b'\r\nChecksum\t...'
    - Binary messages end with LF (b'\n')
    """
    buffer = bytearray()

    while True:
        byte = ser.read(1)
        if byte:
            buffer.extend(byte)

            # Binary message block (ends with LF)
            if byte == b'\n' and not buffer.endswith(b'\r\nChecksum\t') and b'\t' not in buffer:
                yield buffer
                buffer = bytearray()

            # VE.Direct full block
            if b'\r\nChecksum\t' in buffer or b'\r\nChecksum\t.' in buffer:
                yield buffer
                buffer = bytearray()


def filter1(chunk: bytes) -> bytes:
    """
    Filters a multi-line chunk to only include lines starting with b',:A1'.

    Args:
        chunk (bytes): Full multi-line byte string

    Returns:
        bytes: Filtered byte string containing only lines that start with ',:A1'
    """
    lines = chunk.split(b'\n')
    filtered = [line + b'\n' for line in lines if line.startswith(b',:A1')]
    return b''.join(filtered)

def extract_current_setpoint_a2(line: bytes) -> int | None:
    """
    Extract estimated current setpoint from :A2 message.

    Args:
        line (bytes): Full :A2 message (ends with \n)

    Returns:
        int: decoded setpoint byte (likely amps), or None if not a valid :A2 message
    """
    if not line.startswith(b':A2') or len(line) < 10:
        return None
    return line[7]  # index 7 is the 8th byte, corresponds to the varying field


def process_serial_data(device: str):
    """
    Reads serial data and routes it to either hex dump or VE.Direct parser.
    """
    try:
        ser = serial.Serial(device, baudrate=19200, timeout=0.01)
        print(f"🔌 Connected to {device} @19200 baud")
    except serial.SerialException as e:
        print(f"❌ Serial open failed: {e}")
        return

    try:
        for chunk in receive_serial_data(ser):
            #print(f"\n[{datetime.now().isoformat(timespec='milliseconds')}]")

            # Check if it's a VE.Direct text block
            if b'\t' in chunk and b'\r\nChecksum\t' in chunk:
                blocks = parse_vedirect_blocks(chunk)
                for b in blocks:
                    pass
                    #print_vedirect_block(b)
            else:
                hex_ascii_dump(chunk)
                #if extract_current_setpoint_a2(chunk) != None:
                #    print(extract_current_setpoint_a2(chunk), "A")

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    finally:
        ser.close()


if __name__ == "__main__":
    args = parse_args()
    process_serial_data(args.device)
