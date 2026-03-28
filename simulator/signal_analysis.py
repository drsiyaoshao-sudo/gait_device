"""
Layer 5 — UART event parser.

Parses structured log lines that the firmware emits over UART into the same
typed event objects that gait_algorithm.py produces on the pure-Python path.
The UI (app.py) and PipelineResult are identical regardless of which path ran.

Firmware log formats (from src/gait/):
    STEP #<N> ts=<ms> acc=<m/s²> gyr_y=<dps> cadence=<spm> spm
    SNAPSHOT step=<N> si_stance=<pct>% si_swing=<pct>% cadence=<spm> spm
    SESSION_END steps=<N>

Binary snapshot format (CONFIG_GAIT_UART_EXPORT=y):
    Magic: b'GA1T'  (4 bytes)
    Count: uint32 LE (4 bytes)
    N × rolling_snapshot_t (20 bytes each):
        struct("<IIHHHHBb"):
            anchor_step_index  uint32
            anchor_ts_ms       uint32
            si_stance_x10      uint16   (× 10, so 13.3% → 133)
            si_swing_x10       uint16
            si_peak_angvel_x10 uint16
            mean_cadence_x10   uint16
            step_count         uint8
            flags              int8
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass

# Import event types from gait_algorithm to share the schema
from gait_algorithm import StepEvent, SnapshotEvent, SessionEndEvent

# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns for text UART log lines
# ─────────────────────────────────────────────────────────────────────────────

_RE_STEP = re.compile(
    r"STEP\s+#(\d+)\s+ts=(\d+)\s+acc=([-\d]+)\s+gyr_y=([-\d]+)\s+cadence=([\d]+)\s+spm"
)
_RE_SNAPSHOT = re.compile(
    r"SNAPSHOT\s+step=(\d+)\s+si_stance=([\d.]+)%\s+si_swing=([\d.]+)%"
    r"\s+cadence=([\d.]+)\s+spm"
)
_RE_SESSION_END = re.compile(r"SESSION_END\s+steps=(\d+)")

# Binary export constants (CONFIG_GAIT_UART_EXPORT=y)
_BINARY_MAGIC          = b"GA1T"
_SNAPSHOT_STRUCT       = struct.Struct("<IIHHHHBb")   # 20 bytes
_SNAPSHOT_STRUCT_SIZE  = _SNAPSHOT_STRUCT.size


# ─────────────────────────────────────────────────────────────────────────────
# Text line parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_line(
    line: str,
) -> StepEvent | SnapshotEvent | SessionEndEvent | None:
    """Parse a single UART log line.

    Returns a typed event object or None if the line is not a recognised
    event (e.g. a Zephyr boot message or INFO log prefix).
    """
    line = line.strip()

    m = _RE_STEP.search(line)
    if m:
        return StepEvent(
            step_index   = int(m.group(1)),
            ts_ms        = float(m.group(2)),
            peak_acc_mag = int(m.group(3)) / 10.0,   # firmware prints acc×10
            peak_gyr_y   = int(m.group(4)) / 10.0,   # firmware prints gyr_y×10
            cadence_spm  = float(m.group(5)),
        )

    m = _RE_SNAPSHOT.search(line)
    if m:
        return SnapshotEvent(
            anchor_step        = int(m.group(1)),
            anchor_ts_ms       = 0.0,          # not in text format
            si_stance_pct      = float(m.group(2)),
            si_swing_pct       = float(m.group(3)),
            si_peak_angvel_pct = 0.0,          # not in text format
            mean_cadence_spm   = float(m.group(4)),
            step_count         = 0,
            is_running         = float(m.group(4)) >= 130,
        )

    m = _RE_SESSION_END.search(line)
    if m:
        return SessionEndEvent(total_steps=int(m.group(1)))

    return None


def parse_uart_log(text: str) -> tuple[
    list[StepEvent], list[SnapshotEvent], list[SessionEndEvent]
]:
    """Parse a full UART log string.

    Returns (steps, snapshots, session_ends).
    """
    steps: list[StepEvent]       = []
    snaps: list[SnapshotEvent]   = []
    ends:  list[SessionEndEvent] = []

    for line in text.splitlines():
        ev = parse_line(line)
        if isinstance(ev, StepEvent):
            steps.append(ev)
        elif isinstance(ev, SnapshotEvent):
            snaps.append(ev)
        elif isinstance(ev, SessionEndEvent):
            ends.append(ev)

    return steps, snaps, ends


# ─────────────────────────────────────────────────────────────────────────────
# Binary snapshot parser (CONFIG_GAIT_UART_EXPORT=y)
# ─────────────────────────────────────────────────────────────────────────────

def parse_binary_export_log(text: str) -> list[SnapshotEvent]:
    """Extract the BLE binary export block from a text UART log.

    The firmware (CONFIG_GAIT_UART_EXPORT=y) emits:
        BLE_BINARY_START count=N
        <40 hex chars = 20-byte rolling_snapshot_t, one per line>
        BLE_BINARY_END

    This function hex-decodes those lines, prepends the GA1T magic header,
    and calls parse_binary_snapshots() so the same unpack path used by the
    real BLE host tool is exercised.

    Returns an empty list if no BLE_BINARY_START block is found.
    """
    count = 0
    hex_lines: list[str] = []
    in_export = False

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("BLE_BINARY_START"):
            m = re.search(r"count=(\d+)", line)
            count = int(m.group(1)) if m else 0
            in_export = True
        elif line == "BLE_BINARY_END":
            in_export = False
        elif in_export and len(line) == _SNAPSHOT_STRUCT_SIZE * 2:
            hex_lines.append(line)

    if not hex_lines:
        return []

    header = _BINARY_MAGIC + struct.pack("<I", count)
    body = b"".join(bytes.fromhex(h) for h in hex_lines)
    return parse_binary_snapshots(header + body)


def parse_binary_snapshots(data: bytes) -> list[SnapshotEvent]:
    """Unpack a binary snapshot dump from CONFIG_GAIT_UART_EXPORT firmware.

    Expected layout:
        4 bytes  magic  = b'GA1T'
        4 bytes  count  = uint32 LE
        count × 20 bytes rolling_snapshot_t
    """
    if len(data) < 8 or data[:4] != _BINARY_MAGIC:
        raise ValueError(f"Invalid binary snapshot header: {data[:8]!r}")

    count = struct.unpack_from("<I", data, 4)[0]
    expected = 8 + count * _SNAPSHOT_STRUCT_SIZE
    if len(data) < expected:
        raise ValueError(
            f"Binary snapshot truncated: need {expected} bytes, got {len(data)}"
        )

    snaps: list[SnapshotEvent] = []
    offset = 8
    for _ in range(count):
        (
            anchor_step, anchor_ts_ms,
            si_stance_x10, si_swing_x10, si_peak_x10,
            cadence_x10, step_count, flags,
        ) = _SNAPSHOT_STRUCT.unpack_from(data, offset)
        offset += _SNAPSHOT_STRUCT_SIZE

        snaps.append(SnapshotEvent(
            anchor_step        = anchor_step,
            anchor_ts_ms       = float(anchor_ts_ms),
            si_stance_pct      = si_stance_x10 / 10.0,
            si_swing_pct       = si_swing_x10  / 10.0,
            si_peak_angvel_pct = si_peak_x10   / 10.0,
            mean_cadence_spm   = cadence_x10   / 10.0,
            step_count         = step_count,
            is_running         = bool(flags & 0x02),
        ))

    return snaps
