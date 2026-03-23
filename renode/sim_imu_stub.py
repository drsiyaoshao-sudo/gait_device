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

import struct
import os

_SIM_F32_PATH = "/tmp/gait_imu_sim.f32"

# Guard against module-level code resetting state on each re-exec.
# Renode re-executes this script for every peripheral access.
# Use 'if not in globals()' so state survives across calls.
if '_samples' not in dir():
    _samples = []
    _idx = 0
    _cur_bytes = b'\x00' * 24


def _pack_current():
    global _cur_bytes
    if _idx < len(_samples):
        _cur_bytes = struct.pack("<ffffff", *_samples[_idx])
    else:
        _cur_bytes = b'\x00' * 24


if request.IsInit:
    _samples = []
    _idx = 0
    if os.path.exists(_SIM_F32_PATH):
        raw = open(_SIM_F32_PATH, "rb").read()
        n = len(raw) // 24
        for i in range(n):
            _samples.append(struct.unpack_from("<ffffff", raw, i * 24))
        self.NoisyLog("sim_imu_stub: loaded %d samples from %s" % (n, _SIM_F32_PATH))
    else:
        self.NoisyLog("sim_imu_stub: file not found: %s" % _SIM_F32_PATH)
    _pack_current()

elif request.IsRead:
    off = request.Offset
    if off < 4:
        status = 1 if _idx < len(_samples) else 0
        request.Value = (status >> (off * 8)) & 0xFF
    elif 4 <= off < 28:
        request.Value = ord(_cur_bytes[off - 4]) if isinstance(_cur_bytes[off - 4], str) else _cur_bytes[off - 4]
    else:
        request.Value = 0

elif request.IsWrite:
    if request.Offset == 0x1C:
        if _idx < len(_samples):
            _idx += 1
            _pack_current()
            if _idx >= len(_samples):
                self.NoisyLog("sim_imu_stub: all %d samples consumed" % len(_samples))
