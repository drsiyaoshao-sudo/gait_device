"""
Stage 2 exit criteria — host_tool/download_session.py:
  - unpack_notification() correctly decodes all 48-byte step_record_t structs
  - Handles a PDU with N snapshots in a single notification
  - Raises ValueError on truncated PDU
  - export_csv() produces a valid CSV without error
"""
import struct
import io
import sys
import os
import pytest

# host_tool is not inside simulator/, resolve from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "host_tool"))

from download_session import (
    unpack_notification, export_csv, SnapshotRecord,
    _SNAP_STRUCT, _PDU_HEADER,
)
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_pdu(n: int, seq: int = 0) -> bytes:
    """Build a valid PDU with n snapshots."""
    header = _PDU_HEADER.pack(seq, n)
    body = b""
    for i in range(n):
        body += _SNAP_STRUCT.pack(
            i * 10,     # anchor_step_index
            i * 6000,   # anchor_ts_ms
            133,        # si_stance_x10 = 13.3%
            41,         # si_swing_x10  = 4.1%
            0,          # si_peak_angvel_x10
            1000,       # mean_cadence_x10 = 100.0 spm
            min(i * 10 + 10, 200),  # step_count
            0b00000001, # flags: walking
        )
    return header + body


# ─────────────────────────────────────────────────────────────────────────────
# unpack_notification
# ─────────────────────────────────────────────────────────────────────────────

def test_unpack_count():
    records = unpack_notification(_make_pdu(5), seq=0)
    assert len(records) == 5


def test_unpack_zero_snapshots():
    records = unpack_notification(_make_pdu(0), seq=0)
    assert records == []


def test_unpack_si_stance():
    records = unpack_notification(_make_pdu(3), seq=0)
    for r in records:
        assert abs(r.si_stance_pct - 13.3) < 0.05


def test_unpack_si_swing():
    records = unpack_notification(_make_pdu(3), seq=0)
    for r in records:
        assert abs(r.si_swing_pct - 4.1) < 0.05


def test_unpack_cadence():
    records = unpack_notification(_make_pdu(3), seq=0)
    for r in records:
        assert abs(r.mean_cadence_spm - 100.0) < 0.1


def test_unpack_anchor_step():
    records = unpack_notification(_make_pdu(4), seq=0)
    assert records[2].anchor_step_index == 20  # i=2 → 2*10=20


def test_unpack_is_walking_flag():
    records = unpack_notification(_make_pdu(2), seq=0)
    for r in records:
        assert r.is_walking is True
        assert r.is_running is False


def test_unpack_seq_preserved():
    records = unpack_notification(_make_pdu(2, seq=7), seq=7)
    for r in records:
        assert r.seq == 7


def test_unpack_5_snapshots():
    """Exact scenario from ble_gait_svc.c: SNAPS_PER_NOTIF=10."""
    records = unpack_notification(_make_pdu(10), seq=0)
    assert len(records) == 10


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────

def test_truncated_header():
    with pytest.raises(ValueError, match="too short"):
        unpack_notification(b"\x00", seq=0)


def test_truncated_payload():
    pdu = _make_pdu(3)
    with pytest.raises(ValueError, match="truncated"):
        unpack_notification(pdu[:-5], seq=0)


def test_empty_bytes():
    with pytest.raises(ValueError, match="too short"):
        unpack_notification(b"", seq=0)


# ─────────────────────────────────────────────────────────────────────────────
# export_csv
# ─────────────────────────────────────────────────────────────────────────────

def test_export_csv_creates_file(tmp_path):
    records = unpack_notification(_make_pdu(5), seq=0)
    out = tmp_path / "session.csv"
    export_csv(records, out)
    assert out.exists()


def test_export_csv_row_count(tmp_path):
    records = unpack_notification(_make_pdu(5), seq=0)
    out = tmp_path / "session.csv"
    export_csv(records, out)
    lines = out.read_text().splitlines()
    assert len(lines) == 6  # header + 5 rows


def test_export_csv_has_header(tmp_path):
    records = unpack_notification(_make_pdu(2), seq=0)
    out = tmp_path / "session.csv"
    export_csv(records, out)
    header = out.read_text().splitlines()[0]
    assert "si_stance_pct" in header
    assert "anchor_step_index" in header


def test_export_csv_empty(tmp_path):
    out = tmp_path / "empty.csv"
    export_csv([], out)
    lines = out.read_text().splitlines()
    assert len(lines) == 1  # header only
