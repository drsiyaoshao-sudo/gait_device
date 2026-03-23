"""
host_tool/download_session.py — BLE central tool for downloading gait sessions.

Connects to the GaitSense device over BLE, subscribes to the Step Data
Transfer characteristic (GAIT-0002), writes CTRL_EXPORT (0x0003) to the
Control Point, and collects rolling_snapshot_t notifications until the
session status reverts to COMPLETE.

Binary formats
--------------
Notification PDU:
    2 bytes  seq     uint16 LE  — packet sequence number
    2 bytes  n       uint16 LE  — number of snapshots in this PDU
    n × 20   rolling_snapshot_t

rolling_snapshot_t (20 bytes, packed, little-endian):
    uint32  anchor_step_index
    uint32  anchor_ts_ms
    uint16  si_stance_x10        (13.3% → 133)
    uint16  si_swing_x10
    uint16  si_peak_angvel_x10
    uint16  mean_cadence_x10     (100 spm → 1000)
    uint8   step_count
    int8    flags                (bit0=walking, bit1=running)

Usage
-----
    python3 host_tool/download_session.py [--output session.csv] [--device GaitSense]

Requires: bleak >= 0.21
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# GATT UUIDs — must match ble_gait_svc.c
# ─────────────────────────────────────────────────────────────────────────────

_SVC_UUID   = "6e410000-b5a3-f393-e0a9-e50e24dcca9e"
_STATUS_UUID = "6e410001-b5a3-f393-e0a9-e50e24dcca9e"
_DATA_UUID   = "6e410002-b5a3-f393-e0a9-e50e24dcca9e"
_CTRL_UUID   = "6e410003-b5a3-f393-e0a9-e50e24dcca9e"

_CTRL_EXPORT = struct.pack("<H", 0x0003)
_CTRL_CLEAR  = struct.pack("<H", 0x0004)

# ─────────────────────────────────────────────────────────────────────────────
# Snapshot struct
# ─────────────────────────────────────────────────────────────────────────────

_SNAP_STRUCT = struct.Struct("<IIHHHHBb")  # 20 bytes
_PDU_HEADER  = struct.Struct("<HH")        # seq (2) + count (2)

SESSION_IDLE      = 0
SESSION_RECORDING = 1
SESSION_COMPLETE  = 2
SESSION_TRANSFER  = 3


@dataclass
class SnapshotRecord:
    seq:               int    # PDU sequence number
    anchor_step_index: int
    anchor_ts_ms:      int
    si_stance_pct:     float  # %
    si_swing_pct:      float  # %
    si_peak_angvel_pct: float # %
    mean_cadence_spm:  float  # spm
    step_count:        int
    is_walking:        bool
    is_running:        bool


def unpack_notification(data: bytes, seq: int) -> list[SnapshotRecord]:
    """Unpack one BLE notification PDU → list of SnapshotRecord.

    Parameters
    ----------
    data : bytes
        Raw notification bytes from the Step Data characteristic.
    seq : int
        PDU sequence number from the 2-byte header.

    Returns
    -------
    list[SnapshotRecord]
        Decoded snapshot records.

    Raises
    ------
    ValueError
        If the PDU is shorter than its declared length.
    """
    if len(data) < _PDU_HEADER.size:
        raise ValueError(f"PDU too short for header: {len(data)} bytes")

    pdu_seq, n = _PDU_HEADER.unpack_from(data, 0)
    payload_start = _PDU_HEADER.size
    expected = payload_start + n * _SNAP_STRUCT.size

    if len(data) < expected:
        raise ValueError(
            f"PDU truncated: declared {n} snapshots need {expected} bytes, "
            f"got {len(data)}"
        )

    records: list[SnapshotRecord] = []
    offset = payload_start
    for _ in range(n):
        (
            anchor_step, anchor_ts_ms,
            si_stance_x10, si_swing_x10, si_peak_x10,
            cadence_x10, step_count, flags,
        ) = _SNAP_STRUCT.unpack_from(data, offset)
        offset += _SNAP_STRUCT.size

        records.append(SnapshotRecord(
            seq                = pdu_seq,
            anchor_step_index  = anchor_step,
            anchor_ts_ms       = anchor_ts_ms,
            si_stance_pct      = si_stance_x10  / 10.0,
            si_swing_pct       = si_swing_x10   / 10.0,
            si_peak_angvel_pct = si_peak_x10    / 10.0,
            mean_cadence_spm   = cadence_x10    / 10.0,
            step_count         = step_count,
            is_walking         = bool(flags & 0x01),
            is_running         = bool(flags & 0x02),
        ))

    return records


def export_csv(records: list[SnapshotRecord], path: Path) -> None:
    """Write snapshot records to a CSV file."""
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "seq", "anchor_step_index", "anchor_ts_ms",
            "si_stance_pct", "si_swing_pct", "si_peak_angvel_pct",
            "mean_cadence_spm", "step_count", "is_walking", "is_running",
        ])
        writer.writeheader()
        for r in records:
            writer.writerow({
                "seq":               r.seq,
                "anchor_step_index": r.anchor_step_index,
                "anchor_ts_ms":      r.anchor_ts_ms,
                "si_stance_pct":     f"{r.si_stance_pct:.1f}",
                "si_swing_pct":      f"{r.si_swing_pct:.1f}",
                "si_peak_angvel_pct": f"{r.si_peak_angvel_pct:.1f}",
                "mean_cadence_spm":  f"{r.mean_cadence_spm:.1f}",
                "step_count":        r.step_count,
                "is_walking":        int(r.is_walking),
                "is_running":        int(r.is_running),
            })


# ─────────────────────────────────────────────────────────────────────────────
# BLE download (requires bleak)
# ─────────────────────────────────────────────────────────────────────────────

async def _download(device_name: str, output: Optional[Path]) -> list[SnapshotRecord]:
    try:
        from bleak import BleakScanner, BleakClient
    except ImportError:
        print("bleak not installed. Install with: pip install bleak", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning for '{device_name}'...")
    device = await BleakScanner.find_device_by_name(device_name, timeout=10.0)
    if device is None:
        print(f"Device '{device_name}' not found.", file=sys.stderr)
        sys.exit(1)

    all_records: list[SnapshotRecord] = []
    seq_counter = [0]

    def _on_data(_, data: bytearray):
        try:
            recs = unpack_notification(bytes(data), seq_counter[0])
            all_records.extend(recs)
            seq_counter[0] += 1
        except ValueError as e:
            print(f"[WARN] bad PDU: {e}", file=sys.stderr)

    async with BleakClient(device) as client:
        print(f"Connected to {device.name} ({device.address})")

        # Check session state
        status_raw = await client.read_gatt_char(_STATUS_UUID)
        status = status_raw[0]
        if status not in (SESSION_COMPLETE, SESSION_TRANSFER):
            print(f"Device not in COMPLETE state (status={status}). "
                  "Finish recording first.", file=sys.stderr)
            return []

        await client.start_notify(_DATA_UUID, _on_data)
        await client.write_gatt_char(_CTRL_UUID, _CTRL_EXPORT)

        # Poll status until transfer completes (back to IDLE or COMPLETE)
        for _ in range(300):   # 30s timeout
            await asyncio.sleep(0.1)
            status_raw = await client.read_gatt_char(_STATUS_UUID)
            if status_raw[0] != SESSION_TRANSFER:
                break

        await client.stop_notify(_DATA_UUID)

    print(f"Received {len(all_records)} snapshots.")

    if output:
        export_csv(all_records, output)
        print(f"Saved to {output}")

    return all_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Download gait session from GaitSense device")
    parser.add_argument("--device", default="GaitSense", help="BLE device name")
    parser.add_argument("--output", type=Path, default=None,
                        help="CSV output path (default: session_<timestamp>.csv)")
    args = parser.parse_args()

    output = args.output
    if output is None:
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(f"session_{ts}.csv")

    asyncio.run(_download(args.device, output))


if __name__ == "__main__":
    main()
