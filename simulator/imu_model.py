"""
Layer 2 — IMU quantisation model.

Converts the physical-unit float32 signal from walker_model.py into the
binary word format that the LSM6DS3TR-C would place in its 4 KB FIFO.

    Input : np.ndarray (N, 6)  float32  [ax ay az gx gy gz]  m/s², dps
    Output: bytes of length N×12 — 6×int16 per sample, little-endian
            Word order: Gx Gy Gz Ax Ay Az  (gyro first, per FIFO_DATA_OUT spec)

Sensitivity at configured full-scale ranges:
    Accel ±16g :  0.488 mg/LSB  →  4.786728e-3 m/s²/LSB
    Gyro  ±2000:  70 mdps/LSB   →  0.070 dps/LSB
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Physical constants — must match prj.conf / device tree full-scale settings
# ─────────────────────────────────────────────────────────────────────────────

G = 9.81  # m/s²

ACCEL_FS_G         = 16          # ±16g
GYRO_FS_DPS        = 2000        # ±2000 dps
ACCEL_SENSITIVITY  = 0.488e-3 * G   # m/s² per LSB  (0.488 mg/LSB)
GYRO_SENSITIVITY   = 70e-3          # dps per LSB   (70 mdps/LSB)

# Struct for one FIFO sample: Gx Gy Gz Ax Ay Az — all signed int16 LE
_SAMPLE_STRUCT = struct.Struct("<hhhhhh")
BYTES_PER_SAMPLE = _SAMPLE_STRUCT.size   # 12


# ─────────────────────────────────────────────────────────────────────────────
# Quantisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_raw_accel(ms2: np.ndarray) -> np.ndarray:
    """Convert m/s² → int16 raw counts, clipping at ±32767."""
    raw = np.round(ms2 / ACCEL_SENSITIVITY).astype(np.int32)
    return np.clip(raw, -32767, 32767).astype(np.int16)


def _to_raw_gyro(dps: np.ndarray) -> np.ndarray:
    """Convert dps → int16 raw counts, clipping at ±32767."""
    raw = np.round(dps / GYRO_SENSITIVITY).astype(np.int32)
    return np.clip(raw, -32767, 32767).astype(np.int16)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def quantize(samples: np.ndarray) -> bytes:
    """Quantise (N,6) float32 → bytes in LSM6DS3TR-C FIFO word order.

    Parameters
    ----------
    samples : np.ndarray (N, 6)
        Columns: [ax, ay, az, gx, gy, gz]  (m/s², m/s², m/s², dps, dps, dps)

    Returns
    -------
    bytes
        Length N×12.  Each 12-byte block: Gx Gy Gz Ax Ay Az (int16 LE).
    """
    ax = _to_raw_accel(samples[:, 0])
    ay = _to_raw_accel(samples[:, 1])
    az = _to_raw_accel(samples[:, 2])
    gx = _to_raw_gyro(samples[:, 3])
    gy = _to_raw_gyro(samples[:, 4])
    gz = _to_raw_gyro(samples[:, 5])

    # Pack N samples in one vectorised operation
    packed = np.stack([gx, gy, gz, ax, ay, az], axis=1)   # (N, 6) int16
    return packed.astype("<i2").tobytes()


def quantize_to_file(
    samples: np.ndarray,
    path: str | Path = "/tmp/gait_imu_fifo.bin",
) -> Path:
    """Quantise samples and write to a binary file for the Renode stub.

    The stub reads this file at init time and loads all words into its
    internal deque.  Called by RenonePipeline before launching Renode.

    Returns the path written.
    """
    data = quantize(samples)
    p = Path(path)
    p.write_bytes(data)
    return p


def dequantize(data: bytes) -> np.ndarray:
    """Inverse of quantize — for unit-test round-trip validation.

    Returns (N, 6) float32  [ax ay az gx gy gz] in physical units.
    """
    n = len(data) // BYTES_PER_SAMPLE
    raw = np.frombuffer(data, dtype="<i2").reshape(n, 6)  # Gx Gy Gz Ax Ay Az
    # unpack: columns 0-2 = gyro, columns 3-5 = accel
    gx_r, gy_r, gz_r = raw[:, 0], raw[:, 1], raw[:, 2]
    ax_r, ay_r, az_r = raw[:, 3], raw[:, 4], raw[:, 5]
    result = np.column_stack([
        ax_r * ACCEL_SENSITIVITY,
        ay_r * ACCEL_SENSITIVITY,
        az_r * ACCEL_SENSITIVITY,
        gx_r * GYRO_SENSITIVITY,
        gy_r * GYRO_SENSITIVITY,
        gz_r * GYRO_SENSITIVITY,
    ]).astype(np.float32)
    return result


def sample_count(path: str | Path = "/tmp/gait_imu_fifo.bin") -> int:
    """Return number of samples in a previously written FIFO file."""
    return Path(path).stat().st_size // BYTES_PER_SAMPLE
