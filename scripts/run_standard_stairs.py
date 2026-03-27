"""
Standard algorithm — Python signal-level pipeline on stairs, 100 steps.

Confirms baseline before comparison with terrain-aware detector.
Same filter chain as step_detector.c, pure Python, no Renode.
"""

import sys, math
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))
from walker_model import PROFILES, generate_imu_sequence
from terrain_aware_step_detector import (
    _alpha_hp, _alpha_lp, HP_CUTOFF_HZ, LP_WALKING_HZ, LP_RUNNING_HZ,
    CADENCE_RUN_THRESH, ODR_HZ,
)

# ── Standard algorithm (acc-primary, 40ms gyr_y zero-crossing confirmation) ──

GYR_CONFIRM_MS  = 40
GYR_MIN_DPS     = 5.0
MIN_INTERVAL_MS = 250
PEAK_HISTORY    = 8
ACC_SEED        = 10.0

IDLE, RISING, FALLING, CONFIRMED = 0, 1, 2, 3

hp_x1 = hp_y1 = lp_y1 = 0.0
state = IDLE
peak_candidate = peak_ts = peak_gyr_y = 0.0
hist = [ACC_SEED] * PEAK_HISTORY
hist_idx = 0
last_ts = -(MIN_INTERVAL_MS + 1)
step_count = 0
cadence = 100.0
interval_hist = [600.0] * 4
interval_idx = 0
detected_steps = []

timeout_count = 0   # acc peaks that timed out waiting for gyr_y
false_peak_ts = []

def hp(x):
    global hp_x1, hp_y1
    a = _alpha_hp(HP_CUTOFF_HZ)
    y = a * (hp_y1 + x - hp_x1)
    hp_x1, hp_y1 = x, y
    return y

def lp(x):
    global lp_y1
    a = _alpha_lp(LP_RUNNING_HZ if cadence >= CADENCE_RUN_THRESH else LP_WALKING_HZ)
    lp_y1 = a * x + (1 - a) * lp_y1
    return lp_y1

def thresh():
    return 0.5 * sum(hist) / PEAK_HISTORY

def record(peak):
    global hist_idx
    hist[hist_idx] = peak
    hist_idx = (hist_idx + 1) % PEAK_HISTORY

def update_cadence(iv):
    global interval_idx, cadence
    interval_hist[interval_idx] = iv
    interval_idx = (interval_idx + 1) % 4
    m = sum(interval_hist) / 4
    cadence = 60000.0 / m if m > 0 else 0.0

# ── Run ───────────────────────────────────────────────────────────────────────

profile = PROFILES["stairs"]
rng     = np.random.default_rng(42)
samples = generate_imu_sequence(profile, 100, rng=rng)

print(f"Profile : {profile.name}")
print(f"Samples : {len(samples)}  ({len(samples)/ODR_HZ:.1f}s)")
print(f"gyr_y range : [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
print()

for i, row in enumerate(samples):
    ts_ms = i / ODR_HZ * 1000.0
    ax, ay, az, gyr_y = row[0], row[1], row[2], row[4]

    mag = math.sqrt(ax*ax + ay*ay + az*az)
    af  = lp(hp(mag))
    th  = thresh()

    if state in (IDLE, CONFIRMED):
        if state == CONFIRMED and (ts_ms - last_ts) < MIN_INTERVAL_MS:
            continue
        if af > th:
            state = RISING
            peak_candidate = af
            peak_ts = ts_ms
            peak_gyr_y = gyr_y

    elif state == RISING:
        if af > peak_candidate:
            peak_candidate = af
            peak_ts = ts_ms
            peak_gyr_y = gyr_y
        else:
            state = FALLING

    elif state == FALLING:
        elapsed = ts_ms - peak_ts
        gyr_cross = (peak_gyr_y * gyr_y < 0.0)
        gyr_strong = abs(peak_gyr_y) >= GYR_MIN_DPS

        if gyr_cross and elapsed <= GYR_CONFIRM_MS and gyr_strong:
            record(peak_candidate)
            if step_count > 0:
                update_cadence(peak_ts - last_ts)
            detected_steps.append({"step_index": step_count, "ts_ms": peak_ts,
                                    "acc_peak": peak_candidate,
                                    "elapsed_to_confirm_ms": elapsed})
            last_ts = peak_ts
            step_count += 1
            state = CONFIRMED

        elif elapsed > GYR_CONFIRM_MS:
            timeout_count += 1
            false_peak_ts.append(peak_ts)
            state = IDLE

# ── Report ────────────────────────────────────────────────────────────────────

print(f"Standard algorithm — stairs 100 steps")
print(f"{'─'*45}")
print(f"  Steps detected      : {step_count}")
print(f"  acc peaks timed out : {timeout_count}  (gyr_y confirm expired)")
print(f"  Target              : 100 ±5")
print()

if detected_steps:
    print(f"  Detected steps (first 5):")
    for s in detected_steps[:5]:
        print(f"    step {s['step_index']:>3}  ts={s['ts_ms']:>8.1f}ms  "
              f"acc_peak={s['acc_peak']:.2f}  confirm_gap={s['elapsed_to_confirm_ms']:.1f}ms")
else:
    print(f"  No steps detected.")
    print()
    print(f"  Timeout events (first 10 acc peaks that failed gyr_y confirm):")
    for ts in false_peak_ts[:10]:
        print(f"    acc_peak at ts={ts:.1f}ms — gyr_y crossing did not occur within {GYR_CONFIRM_MS}ms")

print()
if step_count == 0:
    print("BASELINE CONFIRMED: standard algorithm detects 0 steps on stairs.")
    print("Proceed to compare with terrain-aware detector.")
else:
    print(f"WARNING: expected 0, got {step_count}. Python mirror may diverge from firmware.")
