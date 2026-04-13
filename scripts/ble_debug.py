#!/usr/bin/env python3.11
"""
ble_debug.py — raw BLE notification dump for diagnostics
Prints every notification packet as hex + text, no line buffering.
"""

import asyncio
import sys
from bleak import BleakScanner, BleakClient

NUS_TX  = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_SVC = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
DEVICE_NAME = "GaitS"


def on_notify(sender, data: bytearray):
    print(f"[{len(data)}B] hex={data.hex()}  text={data.decode('utf-8', errors='replace')!r}")
    sys.stdout.flush()


async def main():
    print(f"Scanning for '{DEVICE_NAME}'...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Not found. Is board advertising?")
        return

    print(f"Found: {device.name} [{device.address}]")

    async with BleakClient(device) as client:
        print(f"Connected. MTU={client.mtu_size}")

        # List all services/characteristics
        print("--- Services ---")
        for svc in client.services:
            print(f"  SVC {svc.uuid}")
            for ch in svc.characteristics:
                print(f"    CHAR {ch.uuid}  props={ch.properties}")

        print("--- Subscribing to NUS TX ---")
        await client.start_notify(NUS_TX, on_notify)
        print("Waiting for notifications... (Ctrl+C to stop)")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        await client.stop_notify(NUS_TX)


if __name__ == "__main__":
    asyncio.run(main())
