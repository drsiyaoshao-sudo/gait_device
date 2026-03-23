"""
Stage 2 — imu_model (Layer 2) tests:
  - quantize() output length matches input
  - Quantization round-trips within one LSB for in-range values
  - Saturation clips at ±32767 for out-of-range values
  - Output is packed in Gx Gy Gz Ax Ay Az order (gyro first)
"""
import struct
import numpy as np
import pytest

from imu_model import (
    quantize, BYTES_PER_SAMPLE,
    ACCEL_SENSITIVITY, GYRO_SENSITIVITY,
)


def _make_samples(n: int, ax=0.0, ay=0.0, az=9.81,
                  gx=0.0, gy=0.0, gz=0.0) -> np.ndarray:
    out = np.zeros((n, 6), dtype=np.float32)
    out[:, 0] = ax; out[:, 1] = ay; out[:, 2] = az
    out[:, 3] = gx; out[:, 4] = gy; out[:, 5] = gz
    return out


# ── output length ────────────────────────────────────────────────────────────

def test_output_length():
    s = _make_samples(50)
    b = quantize(s)
    assert len(b) == 50 * BYTES_PER_SAMPLE


def test_output_length_single():
    b = quantize(_make_samples(1))
    assert len(b) == BYTES_PER_SAMPLE


# ── round-trip ────────────────────────────────────────────────────────────────

def test_accel_roundtrip():
    """az=9.81 m/s² should round-trip to within 1 LSB."""
    az = 9.81
    s = _make_samples(1, az=az)
    b = quantize(s)
    # Byte layout per sample: Gx Gy Gz Ax Ay Az (each 2 bytes, signed LE)
    vals = struct.unpack("<hhhhhh", b)
    az_raw = vals[5]   # Az is the 6th word
    az_reconstructed = az_raw * ACCEL_SENSITIVITY
    assert abs(az_reconstructed - az) < ACCEL_SENSITIVITY * 1.5  # within 1.5 LSB


def test_gyro_roundtrip():
    """gy=200 dps should round-trip to within 1 LSB."""
    gy = 200.0
    s = _make_samples(1, gy=gy)
    b = quantize(s)
    vals = struct.unpack("<hhhhhh", b)
    gy_raw = vals[1]   # Gy is the 2nd word (gyro-first order: Gx Gy Gz Ax Ay Az)
    gy_reconstructed = gy_raw * GYRO_SENSITIVITY
    assert abs(gy_reconstructed - gy) < GYRO_SENSITIVITY * 1.5


# ── saturation ────────────────────────────────────────────────────────────────

def test_accel_saturation_positive():
    """Accel beyond ±16g should clip at 32767."""
    s = _make_samples(1, az=200.0)   # 200 m/s² >> 16g
    b = quantize(s)
    vals = struct.unpack("<hhhhhh", b)
    az_raw = vals[5]
    assert az_raw == 32767


def test_accel_saturation_negative():
    s = _make_samples(1, az=-200.0)
    b = quantize(s)
    vals = struct.unpack("<hhhhhh", b)
    az_raw = vals[5]
    assert az_raw == -32767


def test_gyro_saturation():
    """Gyro beyond ±2000 dps should clip at 32767."""
    s = _make_samples(1, gy=5000.0)
    b = quantize(s)
    vals = struct.unpack("<hhhhhh", b)
    gy_raw = vals[1]   # Gy is index 1 (Gx Gy Gz Ax Ay Az)
    assert gy_raw == 32767


# ── word order ────────────────────────────────────────────────────────────────

def test_gyro_first_word_order():
    """Gyro-only sample: first 3 words non-zero, last 3 near-zero."""
    s = _make_samples(1, ax=0.0, ay=0.0, az=0.0, gx=100.0, gy=200.0, gz=300.0)
    b = quantize(s)
    vals = struct.unpack("<hhhhhh", b)
    # Layout: Gx(0) Gy(1) Gz(2) Ax(3) Ay(4) Az(5)
    gx_raw, gy_raw, gz_raw, ax_raw, ay_raw, az_raw = vals
    assert abs(gx_raw) > 100   # gx present
    assert abs(gy_raw) > 100   # gy present
    assert abs(gz_raw) > 100   # gz present
    assert ax_raw == 0 and ay_raw == 0 and az_raw == 0   # no accel


def test_accel_only_word_order():
    """Accel-only sample: first 3 words zero, last 3 non-zero."""
    s = _make_samples(1, az=9.81)
    b = quantize(s)
    vals = struct.unpack("<hhhhhh", b)
    gx_raw, gy_raw, gz_raw, ax_raw, ay_raw, az_raw = vals
    assert gx_raw == 0 and gy_raw == 0 and gz_raw == 0
    assert az_raw != 0


# ── multi-sample consistency ─────────────────────────────────────────────────

def test_constant_signal_identical_words():
    """Constant input → all samples identical."""
    n = 10
    s = _make_samples(n, az=9.81, gy=50.0)
    b = quantize(s)
    words = [struct.unpack("<hhhhhh", b[i*12:(i+1)*12]) for i in range(n)]
    assert all(w == words[0] for w in words)
