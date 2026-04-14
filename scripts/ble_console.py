#!/usr/bin/env python3.11
"""
ble_console.py — GaitSense BLE console receiver

Scans for "GaitSense", connects, subscribes to Nordic UART Service RX notify,
and prints all output to stdout. Ctrl+C to exit.

Usage:
    python3.11 scripts/ble_console.py

NUS UUIDs (Nordic UART Service):
    Service:    6E400001-B5A3-F393-E0A9-E50E24DCCA9E
    TX (notify): 6E400003-B5A3-F393-E0A9-E50E24DCCA9E  ← board sends here
    RX (write):  6E400002-B5A3-F393-E0A9-E50E24DCCA9E
"""

import asyncio
import sys
from bleak import BleakScanner, BleakClient

NUS_TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # board → laptop
DEVICE_NAME = "GaitS"   # advertising packet truncates "GaitSense" to "GaitS"


_buf = ""
def on_notify(sender, data: bytearray):
    global _buf
    _buf += data.decode("utf-8", errors="replace")
    while "\n" in _buf:
        line, _buf = _buf.split("\n", 1)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


async def main():
    device = None
    while device is None:
        print(f"Scanning for '{DEVICE_NAME}*'...")
        device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
        if device is None:
            print("Not found, retrying...")

    print(f"Found: {device.name} [{device.address}]")
    print("Connecting...")

    async with BleakClient(device) as client:
        print(f"Connected. Subscribing to NUS TX...")
        await client.start_notify(NUS_TX, on_notify)
        print("--- GaitSense output ---")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        await client.stop_notify(NUS_TX)
        print("\n--- disconnected ---")


if __name__ == "__main__":
    asyncio.run(main())
