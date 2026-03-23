"""
Layer 3 — LSM6DS3TR-C / LSM6DSO Renode Python peripheral stub.

DATA_READY mode: serves individual gyro/accel output registers (0x22-0x2D)
matching what the Zephyr LSM6DSO driver reads via sensor_sample_fetch().

Architecture:
    1. At init: read all quantized samples from /tmp/gait_imu_fifo.bin
       File format: N × 12 bytes, each block = [Gx Gy Gz Ax Ay Az] int16-LE
       (written by imu_model.quantize_to_file() before Renode starts).
    2. Maintain a current sample index.
    3. Assert INT1 GPIO immediately when samples are available.
    4. On each OUTZ_H_A (0x2D) read — the final output register the driver reads
       in sensor_sample_fetch() — advance to the next sample.  Re-assert INT1
       if more samples remain, deassert when the FIFO is exhausted.
    5. Respond to firmware I2C reads of all LSM6DSO output / config registers.

Renode Python peripheral API:
    request.isInit   — peripheral being initialised
    request.isRead   — firmware reading a register
    request.isWrite  — firmware writing a register
    request.offset   — register address (8-bit)
    request.value    — value to return (isRead) or value written (isWrite)

    self.IRQ.Set()   — assert the INT1 GPIO line
    self.IRQ.Unset() — deassert INT1

Register map implemented:
    0x0F  WHO_AM_I     → 0x6A
    0x0D  INT1_CTRL    — ACK writes
    0x10  CTRL1_XL     — ACK writes (accel config)
    0x11  CTRL2_G      — ACK writes (gyro config)
    0x12  CTRL3_C      — ACK writes / handle SW_RESET
    0x13  CTRL4_C      — ACK writes
    0x14  CTRL5_C      — ACK writes
    0x15  CTRL6_C      — ACK writes
    0x16  CTRL7_G      — ACK writes
    0x17  CTRL8_XL     — ACK writes
    0x1E  STATUS_REG   → 0x03 (XLDA | GDA always set)
    0x22  OUTX_L_G     — Gx low  byte of current sample
    0x23  OUTX_H_G     — Gx high byte
    0x24  OUTY_L_G     — Gy low  byte
    0x25  OUTY_H_G     — Gy high byte
    0x26  OUTZ_L_G     — Gz low  byte
    0x27  OUTZ_H_G     — Gz high byte
    0x28  OUTX_L_A     — Ax low  byte
    0x29  OUTX_H_A     — Ax high byte
    0x2A  OUTY_L_A     — Ay low  byte
    0x2B  OUTY_H_A     — Ay high byte
    0x2C  OUTZ_L_A     — Az low  byte
    0x2D  OUTZ_H_A     — Az high byte → ADVANCES sample + re-asserts INT1
"""

import struct
import os

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_WHO_AM_I_VAL      = 0x6A
_FIFO_BIN_PATH     = "/tmp/gait_imu_fifo.bin"
_WORDS_PER_SAMPLE  = 6     # Gx Gy Gz Ax Ay Az  (each int16 LE)
_BYTES_PER_SAMPLE  = 12

# Register addresses
_REG_INT1_CTRL  = 0x0D
_REG_WHO_AM_I   = 0x0F
_REG_CTRL1_XL   = 0x10
_REG_CTRL2_G    = 0x11
_REG_CTRL3_C    = 0x12
_REG_CTRL4_C    = 0x13
_REG_CTRL5_C    = 0x14
_REG_CTRL6_C    = 0x15
_REG_CTRL7_G    = 0x16
_REG_CTRL8_XL   = 0x17
_REG_STATUS     = 0x1E

# Gyro output registers
_REG_OUTX_L_G   = 0x22
_REG_OUTX_H_G   = 0x23
_REG_OUTY_L_G   = 0x24
_REG_OUTY_H_G   = 0x25
_REG_OUTZ_L_G   = 0x26
_REG_OUTZ_H_G   = 0x27

# Accel output registers
_REG_OUTX_L_A   = 0x28
_REG_OUTX_H_A   = 0x29
_REG_OUTY_L_A   = 0x2A
_REG_OUTY_H_A   = 0x2B
_REG_OUTZ_L_A   = 0x2C
_REG_OUTZ_H_A   = 0x2D   # reading this register advances to next sample

# ─────────────────────────────────────────────────────────────────────────────
# Peripheral state
# (persistent across isInit/isRead/isWrite because Renode uses a shared
# namespace for the Python peripheral module)
# ─────────────────────────────────────────────────────────────────────────────

_samples     = []     # list of (gx, gy, gz, ax, ay, az) int16 tuples
_sample_idx  = 0      # index of the currently-served sample
_int1_active = False  # current INT1 output state


def _load_samples():
    """Read the pre-written binary file and build the sample list."""
    global _samples
    _samples = []
    if not os.path.exists(_FIFO_BIN_PATH):
        self.Log(LogLevel.Warning,
                 f"LSM6DS3 stub: IMU file not found: {_FIFO_BIN_PATH}")
        return
    data = open(_FIFO_BIN_PATH, "rb").read()
    n = len(data) // _BYTES_PER_SAMPLE
    for i in range(n):
        block = data[i * _BYTES_PER_SAMPLE : (i + 1) * _BYTES_PER_SAMPLE]
        gx, gy, gz, ax, ay, az = struct.unpack_from("<hhhhhh", block)
        _samples.append((gx, gy, gz, ax, ay, az))
    self.Log(LogLevel.Info,
             f"LSM6DS3 stub: loaded {len(_samples)} samples from {_FIFO_BIN_PATH}")


def _current():
    """Return the current sample as a (gx, gy, gz, ax, ay, az) tuple."""
    if _sample_idx < len(_samples):
        return _samples[_sample_idx]
    return (0, 0, 0, 0, 0, 0)


def _advance():
    """Move to the next sample and update INT1."""
    global _sample_idx, _int1_active
    _sample_idx += 1
    has_more = _sample_idx < len(_samples)
    if has_more and not _int1_active:
        self.IRQ.Set()
        _int1_active = True
    elif not has_more and _int1_active:
        self.IRQ.Unset()
        _int1_active = False
        self.Log(LogLevel.Info,
                 f"LSM6DS3 stub: all {len(_samples)} samples consumed — INT1 deasserted")


# ─────────────────────────────────────────────────────────────────────────────
# Renode peripheral dispatch
# ─────────────────────────────────────────────────────────────────────────────

if request.isInit:
    _load_samples()
    _sample_idx  = 0
    _int1_active = False
    # Assert INT1 immediately so the firmware trigger fires as soon as it
    # enables the interrupt.
    if _samples:
        self.IRQ.Set()
        _int1_active = True

elif request.isRead:
    offset = request.offset
    s = _current()

    if offset == _REG_WHO_AM_I:
        request.value = _WHO_AM_I_VAL

    elif offset == _REG_STATUS:
        # XLDA (bit 0) + GDA (bit 1) always asserted = data ready
        request.value = 0x03

    # ── Gyro output ──────────────────────────────────────────────────────────
    elif offset == _REG_OUTX_L_G:
        request.value = s[0] & 0xFF
    elif offset == _REG_OUTX_H_G:
        request.value = (s[0] >> 8) & 0xFF
    elif offset == _REG_OUTY_L_G:
        request.value = s[1] & 0xFF
    elif offset == _REG_OUTY_H_G:
        request.value = (s[1] >> 8) & 0xFF
    elif offset == _REG_OUTZ_L_G:
        request.value = s[2] & 0xFF
    elif offset == _REG_OUTZ_H_G:
        request.value = (s[2] >> 8) & 0xFF

    # ── Accel output ─────────────────────────────────────────────────────────
    elif offset == _REG_OUTX_L_A:
        request.value = s[3] & 0xFF
    elif offset == _REG_OUTX_H_A:
        request.value = (s[3] >> 8) & 0xFF
    elif offset == _REG_OUTY_L_A:
        request.value = s[4] & 0xFF
    elif offset == _REG_OUTY_H_A:
        request.value = (s[4] >> 8) & 0xFF
    elif offset == _REG_OUTZ_L_A:
        request.value = s[5] & 0xFF
    elif offset == _REG_OUTZ_H_A:
        # Last register read by sensor_sample_fetch() — advance to next sample
        request.value = (s[5] >> 8) & 0xFF
        _advance()

    else:
        request.value = 0

elif request.isWrite:
    offset = request.offset
    if offset == _REG_CTRL3_C and (request.value & 0x80):
        # SW_RESET: reload samples from file and reset index
        _load_samples()
        _sample_idx  = 0
        _int1_active = False
        if _samples:
            self.IRQ.Set()
            _int1_active = True
    # All other writes silently acknowledged
