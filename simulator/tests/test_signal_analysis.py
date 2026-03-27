"""
Stage 2 exit criteria — signal_analysis:
  - parse_line() correctly handles STEP, SNAPSHOT, SESSION_END formats
  - parse_uart_log() routes events into correct lists
  - Unknown / noise lines return None (no crash)
  - parse_binary_snapshots() unpacks all 20-byte rolling_snapshot_t structs
  - Binary parser raises on bad magic / truncated data
"""
import struct
import pytest

from signal_analysis import (
    parse_line, parse_uart_log, parse_binary_snapshots,
    _BINARY_MAGIC, _SNAPSHOT_STRUCT,
)
from gait_algorithm import StepEvent, SnapshotEvent, SessionEndEvent


# ── parse_line: STEP ─────────────────────────────────────────────────────────

STEP_LINE = "STEP #5 ts=3012 acc=247 gyr_y=-632 cadence=100 spm"

def test_parse_step_type():
    ev = parse_line(STEP_LINE)
    assert isinstance(ev, StepEvent)

def test_parse_step_index():
    ev = parse_line(STEP_LINE)
    assert ev.step_index == 5

def test_parse_step_ts():
    ev = parse_line(STEP_LINE)
    assert ev.ts_ms == 3012.0

def test_parse_step_acc():
    ev = parse_line(STEP_LINE)
    assert abs(ev.peak_acc_mag - 24.7) < 1e-4

def test_parse_step_gyr_y():
    ev = parse_line(STEP_LINE)
    assert abs(ev.peak_gyr_y - (-63.2)) < 1e-4

def test_parse_step_cadence():
    ev = parse_line(STEP_LINE)
    assert abs(ev.cadence_spm - 100.0) < 1e-4


# ── parse_line: SNAPSHOT ─────────────────────────────────────────────────────

SNAP_LINE = "SNAPSHOT step=199 si_stance=13.3% si_swing=4.1% cadence=105.5 spm"

def test_parse_snapshot_type():
    ev = parse_line(SNAP_LINE)
    assert isinstance(ev, SnapshotEvent)

def test_parse_snapshot_anchor():
    ev = parse_line(SNAP_LINE)
    assert ev.anchor_step == 199

def test_parse_snapshot_si_stance():
    ev = parse_line(SNAP_LINE)
    assert abs(ev.si_stance_pct - 13.3) < 1e-4

def test_parse_snapshot_si_swing():
    ev = parse_line(SNAP_LINE)
    assert abs(ev.si_swing_pct - 4.1) < 1e-4

def test_parse_snapshot_cadence():
    ev = parse_line(SNAP_LINE)
    assert abs(ev.mean_cadence_spm - 105.5) < 1e-4


# ── parse_line: SESSION_END ───────────────────────────────────────────────────

SESSION_LINE = "SESSION_END steps=347"

def test_parse_session_end_type():
    ev = parse_line(SESSION_LINE)
    assert isinstance(ev, SessionEndEvent)

def test_parse_session_end_count():
    ev = parse_line(SESSION_LINE)
    assert ev.total_steps == 347


# ── parse_line: unknown / noise lines ────────────────────────────────────────

@pytest.mark.parametrize("line", [
    "",
    "   ",
    "[00:00:01.234,567] <inf> zephyr: Booting nRF52840",
    "I2C: bus busy",
    "CALIBRATION DONE bias_az=9.812",
    "step 5 at 3012ms",       # wrong format
    "SNAPSHOT step=foo si_stance=13% si_swing=0% cadence=100 spm",  # bad int
])
def test_parse_unknown_returns_none(line):
    assert parse_line(line) is None


# ── parse_uart_log ────────────────────────────────────────────────────────────

_LOG = """\
[00:00:00.001] booting
STEP #0 ts=1024 acc=194 gyr_y=-450 cadence=0 spm
STEP #1 ts=1624 acc=189 gyr_y=-512 cadence=100 spm
SNAPSHOT step=9 si_stance=0.5% si_swing=0.1% cadence=100.0 spm
SESSION_END steps=100
noise line ignored
SESSION_END steps=200
"""

def test_parse_log_step_count():
    steps, snaps, ends = parse_uart_log(_LOG)
    assert len(steps) == 2

def test_parse_log_snapshot_count():
    steps, snaps, ends = parse_uart_log(_LOG)
    assert len(snaps) == 1

def test_parse_log_session_end_count():
    steps, snaps, ends = parse_uart_log(_LOG)
    assert len(ends) == 2

def test_parse_log_step_order():
    steps, _, _ = parse_uart_log(_LOG)
    assert steps[0].step_index == 0
    assert steps[1].step_index == 1


# ── parse_binary_snapshots ────────────────────────────────────────────────────

def _make_binary(n: int) -> bytes:
    """Build a valid binary snapshot blob with n snapshots."""
    header = _BINARY_MAGIC + struct.pack("<I", n)
    body = b""
    for i in range(n):
        # anchor_step, anchor_ts_ms, si_stance_x10, si_swing_x10,
        # si_peak_angvel_x10, mean_cadence_x10, step_count, flags
        body += _SNAPSHOT_STRUCT.pack(
            i * 10,          # anchor_step_index
            i * 6000,        # anchor_ts_ms
            133,             # si_stance_x10 = 13.3%
            0,               # si_swing_x10
            0,               # si_peak_angvel_x10
            1000,            # mean_cadence_x10 = 100.0 spm
            min(i * 10 + 10, 200),  # step_count
            0,               # flags
        )
    return header + body


def test_binary_parse_count():
    snaps = parse_binary_snapshots(_make_binary(5))
    assert len(snaps) == 5

def test_binary_parse_zero_snapshots():
    snaps = parse_binary_snapshots(_make_binary(0))
    assert snaps == []

def test_binary_parse_si_value():
    snaps = parse_binary_snapshots(_make_binary(3))
    for s in snaps:
        assert abs(s.si_stance_pct - 13.3) < 0.05

def test_binary_parse_cadence():
    snaps = parse_binary_snapshots(_make_binary(3))
    for s in snaps:
        assert abs(s.mean_cadence_spm - 100.0) < 0.1

def test_binary_parse_anchor_step():
    snaps = parse_binary_snapshots(_make_binary(4))
    assert snaps[2].anchor_step == 20   # i=2 → 2*10=20

def test_binary_parse_bad_magic():
    bad = b"XXXX" + _make_binary(3)[4:]
    with pytest.raises(ValueError, match="Invalid binary snapshot header"):
        parse_binary_snapshots(bad)

def test_binary_parse_truncated():
    good = _make_binary(3)
    truncated = good[:-5]
    with pytest.raises(ValueError, match="truncated"):
        parse_binary_snapshots(truncated)

def test_binary_parse_large():
    """Verify 100 snapshots unpack without error."""
    snaps = parse_binary_snapshots(_make_binary(100))
    assert len(snaps) == 100
