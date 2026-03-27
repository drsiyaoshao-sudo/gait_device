# -*- coding: ascii -*-
# Renode Python peripheral -- simulation-mode IMU stub.
# Python 2 (IronPython) compatible: no f-strings, no non-ASCII.
#
# Registered at sysbus 0x400B0000 (size 0x100).
# Used only when firmware is built with CONFIG_GAIT_RENODE_SIM=y.
#
# Register map (byte-addressed):
#   0x00-0x03  STATUS  uint32 LE  (1 = sample ready, 0 = exhausted)
#   0x04-0x1B  sample data: [ax ay az gx gy gz] float32 LE (24 bytes)
#   0x1C       ACK     (write any value) -- advances to next sample
#
# File format (/tmp/gait_imu_sim.f32):
#   N x 24 bytes, each = [ax ay az gx gy gz] float32 LE
#   Written by simulator/renode_bridge.py before Renode starts.
#
# State persistence strategy: file-based _idx avoids IronPython in-memory
# list truncation (large _samples list silently capped at ~5 entries in
# Renode 1.16 embedded IronPython context).
# _idx is stored in /tmp/stub_idx.txt on every ACK write.
# _cur_bytes (24 bytes) is kept as a module global -- small enough to be safe.

import struct
import os

_SIM_F32_PATH = "/tmp/gait_imu_sim.f32"
_IDX_PATH     = os.path.expanduser("~/.gait_stub_idx.txt")


def _n_samples():
    try:
        return os.path.getsize(_SIM_F32_PATH) // 24
    except Exception:
        return 0


def _read_idx():
    try:
        return int(open(_IDX_PATH, "r").read().strip())
    except Exception:
        return 0


def _write_idx(idx):
    f = open(_IDX_PATH, "w")
    f.write(str(idx))
    f.close()


def _load_sample(idx):
    # Read exactly one 24-byte sample from the f32 file at the given index.
    try:
        f = open(_SIM_F32_PATH, "rb")
        f.seek(idx * 24)
        raw = f.read(24)
        f.close()
        if len(raw) == 24:
            return raw
    except Exception:
        pass
    return b'\x00' * 24


# Module-level cache for the current sample bytes (24 bytes only -- safe for IronPython).
if '_cur_bytes' not in globals():
    _cur_bytes = b'\x00' * 24


if request.IsInit:
    _write_idx(0)
    _cur_bytes = _load_sample(0)
    n = _n_samples()
    self.NoisyLog("sim_imu_stub: file-based idx, %d samples, path=%s" % (n, _SIM_F32_PATH))

elif request.IsRead:
    off = request.Offset
    if off < 4:
        idx = _read_idx()
        n   = _n_samples()
        status = 1 if idx < n else 0
        request.Value = (status >> (off * 8)) & 0xFF
    elif 4 <= off < 28:
        # Load fresh sample bytes when reading first data byte (offset 4).
        # Subsequent bytes within the same sample use the cached _cur_bytes.
        if off == 4:
            idx = _read_idx()
            _cur_bytes = _load_sample(idx)
        b = _cur_bytes[off - 4]
        request.Value = ord(b) if isinstance(b, str) else b
    else:
        request.Value = 0

elif request.IsWrite:
    if request.Offset == 0x1C:
        idx = _read_idx()
        n   = _n_samples()
        if idx < n:
            _write_idx(idx + 1)
            if idx + 1 >= n:
                self.NoisyLog("sim_imu_stub: all %d samples consumed" % n)
