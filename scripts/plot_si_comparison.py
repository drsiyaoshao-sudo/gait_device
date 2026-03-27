"""
Stage 2 Python milestone plot — SI comparison: standard vs terrain-aware algorithm.

Procedure (per CLAUDE.md learner-in-the-loop):
  1. Run both detectors against all 4 walker profiles in pure Python.
  2. Plot step count and SI side-by-side — human reviews before C port.
  3. No Renode, no hardware. Signal arbitration only.

Standard algorithm  → mirrors step_detector.c (acc-primary, 40ms gyr_y confirm)
Terrain-aware algo  → TerrainAwareStepDetector (gyr_y_hp push-off, acc confirm)

Saved to docs/plots/si_comparison_standard_vs_terrain.png
"""

import sys, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))
from walker_model import PROFILES, generate_imu_sequence
from terrain_aware_step_detector import (
    TerrainAwareStepDetector, ODR_HZ, DT,
    _alpha_hp, _alpha_lp, HP_CUTOFF_HZ, LP_WALKING_HZ, LP_RUNNING_HZ,
    CADENCE_RUN_THRESH,
)

# ── Standard algorithm (mirrors step_detector.c) ──────────────────────────────

GYR_CONFIRM_MS   = 40
GYR_MIN_DPS      = 5.0
MIN_INTERVAL_MS  = 250
PEAK_HISTORY     = 8
ACC_SEED         = 10.0

class StandardStepDetector:
    """Python mirror of step_detector.c — acc-primary, 40ms gyro confirmation."""

    IDLE, RISING, FALLING, CONFIRMED = 0, 1, 2, 3

    def __init__(self):
        self.reset()

    def reset(self):
        self._hp_x1 = self._hp_y1 = 0.0
        self._lp_y1 = 0.0
        self._state = self.IDLE
        self._peak_candidate = 0.0
        self._peak_ts = 0.0
        self._peak_gyr_y = 0.0
        self._hist = [ACC_SEED] * PEAK_HISTORY
        self._hist_idx = 0
        self._last_ts = -(MIN_INTERVAL_MS + 1)
        self._step_count = 0
        self._steps = []
        self._interval_hist = [600.0] * 4
        self._interval_idx = 0
        self._cadence = 100.0

    def _hp(self, x):
        a = _alpha_hp(HP_CUTOFF_HZ)
        y = a * (self._hp_y1 + x - self._hp_x1)
        self._hp_x1, self._hp_y1 = x, y
        return y

    def _lp(self, x):
        a = _alpha_lp(LP_RUNNING_HZ if self._cadence >= CADENCE_RUN_THRESH else LP_WALKING_HZ)
        self._lp_y1 = a * x + (1 - a) * self._lp_y1
        return self._lp_y1

    def _thresh(self):
        return 0.5 * sum(self._hist) / PEAK_HISTORY

    def _record(self, peak):
        self._hist[self._hist_idx] = peak
        self._hist_idx = (self._hist_idx + 1) % PEAK_HISTORY

    def _cadence_update(self, iv):
        self._interval_hist[self._interval_idx] = iv
        self._interval_idx = (self._interval_idx + 1) % 4
        m = sum(self._interval_hist) / 4
        self._cadence = 60000.0 / m if m > 0 else 0.0

    def update(self, ts_ms, ax, ay, az, gyr_y):
        mag = math.sqrt(ax*ax + ay*ay + az*az)
        af  = self._lp(self._hp(mag))
        th  = self._thresh()

        step = None
        if self._state in (self.IDLE, self.CONFIRMED):
            if self._state == self.CONFIRMED and (ts_ms - self._last_ts) < MIN_INTERVAL_MS:
                return None
            if af > th:
                self._state = self.RISING
                self._peak_candidate = af
                self._peak_ts = ts_ms
                self._peak_gyr_y = gyr_y

        elif self._state == self.RISING:
            if af > self._peak_candidate:
                self._peak_candidate = af
                self._peak_ts = ts_ms
                self._peak_gyr_y = gyr_y
            else:
                self._state = self.FALLING

        elif self._state == self.FALLING:
            elapsed = ts_ms - self._peak_ts
            gyr_cross = (self._peak_gyr_y * gyr_y < 0.0)
            gyr_strong = abs(self._peak_gyr_y) >= GYR_MIN_DPS

            if gyr_cross and elapsed <= GYR_CONFIRM_MS and gyr_strong:
                self._record(self._peak_candidate)
                if self._step_count > 0:
                    self._cadence_update(self._peak_ts - self._last_ts)
                step = {"step_index": self._step_count, "ts_ms": self._peak_ts}
                self._steps.append(step)
                self._last_ts = self._peak_ts
                self._step_count += 1
                self._state = self.CONFIRMED
            elif elapsed > GYR_CONFIRM_MS:
                self._state = self.IDLE

        return step

    @property
    def steps(self):
        return list(self._steps)


# ── Run both detectors ────────────────────────────────────────────────────────

def run_both(profile_key, n_steps, seed=42):
    profile = PROFILES[profile_key]
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)

    std = StandardStepDetector()
    new = TerrainAwareStepDetector()

    for i, row in enumerate(samples):
        ts = i / ODR_HZ * 1000.0
        std.update(ts, row[0], row[1], row[2], row[4])
        new.update(ts, row[0], row[1], row[2], row[4])

    return std.steps, new.steps


def si_from_steps(steps_list, ts_key="ts_ms", idx_key="step_index", warmup=4):
    if len(steps_list) < warmup + 4:
        return None
    ts      = {s[idx_key]: s[ts_key] for s in steps_list} if isinstance(steps_list[0], dict) \
              else {s.step_index: s.ts_ms for s in steps_list}
    indices = sorted(ts)
    ivals   = {indices[i]: ts[indices[i+1]] - ts[indices[i]]
               for i in range(len(indices) - 1)}
    odd  = [v for k, v in ivals.items() if k >= warmup and k % 2 == 1]
    even = [v for k, v in ivals.items() if k >= warmup and k % 2 == 0]
    if not odd or not even:
        return None
    T_o, T_e = sum(odd)/len(odd), sum(even)/len(even)
    denom = T_o + T_e
    return 200.0 * abs(T_o - T_e) / denom if denom > 1e-6 else None


# ── Collect results ───────────────────────────────────────────────────────────

PROFILES_ORDER = ["flat", "bad_wear", "slope", "stairs"]
LABELS         = ["Flat", "Bad wear", "Slope (10°)", "Stairs"]
COLORS_STD     = "#90CAF9"   # light blue
COLORS_NEW     = "#1565C0"   # dark blue
N_STEPS        = 100

results = {}
print(f"{'Profile':<12}  {'Std steps':>9}  {'New steps':>9}  {'Std SI%':>8}  {'New SI%':>8}")
print("-" * 55)
for key, label in zip(PROFILES_ORDER, LABELS):
    std_steps, new_steps = run_both(key, N_STEPS)
    std_si = si_from_steps(std_steps)
    new_si = si_from_steps(new_steps)
    results[key] = {
        "std_count": len(std_steps),
        "new_count": len(new_steps),
        "std_si":    std_si,
        "new_si":    new_si,
    }
    std_si_str = f"{std_si:.2f}" if std_si is not None else "n/a"
    new_si_str = f"{new_si:.2f}" if new_si is not None else "n/a"
    print(f"{label:<12}  {len(std_steps):>9}  {len(new_steps):>9}  "
          f"{std_si_str:>8}  {new_si_str:>8}")

# ── Plot ──────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle(
    "Python Stage 2 Milestone — Standard vs Terrain-Aware Step Detector\n"
    "All 4 walker profiles  |  100 steps each  |  seed=42\n"
    "Human review required before porting algorithm to step_detector.c",
    fontsize=12
)

x     = np.arange(len(PROFILES_ORDER))
w     = 0.35

# ─── Panel 1: Step count ───────────────────────────────────────────────────
ax1 = axes[0]
b1  = ax1.bar(x - w/2, [results[k]["std_count"] for k in PROFILES_ORDER], w,
              color=COLORS_STD, label="Standard (acc-primary, 40ms gate)", edgecolor="white")
b2  = ax1.bar(x + w/2, [results[k]["new_count"] for k in PROFILES_ORDER], w,
              color=COLORS_NEW, label="Terrain-aware (gyr_y_hp push-off)", edgecolor="white")

ax1.axhline(100, color="green", linewidth=1.2, linestyle="--", label="Target (100 ±5)")
ax1.axhline(95,  color="green", linewidth=0.6, linestyle=":",  alpha=0.5)
ax1.axhline(105, color="green", linewidth=0.6, linestyle=":",  alpha=0.5)
ax1.set_xticks(x); ax1.set_xticklabels(LABELS, fontsize=10)
ax1.set_ylabel("Steps detected"); ax1.set_title("Step Count (target 100 ±5)")
ax1.set_ylim(0, 120); ax1.legend(fontsize=8); ax1.grid(True, axis="y", alpha=0.3)

for bar, val in zip(list(b1) + list(b2),
                    [results[k]["std_count"] for k in PROFILES_ORDER] +
                    [results[k]["new_count"] for k in PROFILES_ORDER]):
    ax1.text(bar.get_x() + bar.get_width()/2, val + 1, str(val),
             ha="center", va="bottom", fontsize=9, fontweight="bold")

# Verdict labels
for i, key in enumerate(PROFILES_ORDER):
    for offset, count, color_ok in [
        (-w/2, results[key]["std_count"], "green"),
        (+w/2, results[key]["new_count"], "green"),
    ]:
        ok = abs(count - 100) <= 5
        ax1.text(i + offset, -10,
                 "✓" if ok else "✗",
                 ha="center", fontsize=13,
                 color="green" if ok else "red",
                 transform=ax1.get_xaxis_transform())

# ─── Panel 2: SI% ─────────────────────────────────────────────────────────
ax2 = axes[1]

std_si_vals = [results[k]["std_si"] if results[k]["std_si"] is not None else 0
               for k in PROFILES_ORDER]
new_si_vals = [results[k]["new_si"] if results[k]["new_si"] is not None else 0
               for k in PROFILES_ORDER]

b3 = ax2.bar(x - w/2, std_si_vals, w,
             color=COLORS_STD, label="Standard", edgecolor="white")
b4 = ax2.bar(x + w/2, new_si_vals, w,
             color=COLORS_NEW, label="Terrain-aware", edgecolor="white")

ax2.axhline(3.0, color="red", linewidth=1.2, linestyle="--", label="±3% tolerance")
ax2.set_xticks(x); ax2.set_xticklabels(LABELS, fontsize=10)
ax2.set_ylabel("SI_interval (%)"); ax2.set_title("Symmetry Index — interval method (target <3%)")
ax2.set_ylim(0, max(max(std_si_vals), max(new_si_vals), 3.5) * 1.2)
ax2.legend(fontsize=8); ax2.grid(True, axis="y", alpha=0.3)

std_na = [results[k]["std_si"] is None for k in PROFILES_ORDER]
new_na = [results[k]["new_si"] is None for k in PROFILES_ORDER]
for bar, val, is_na in zip(
    list(b3) + list(b4),
    std_si_vals + new_si_vals,
    std_na + new_na,
):
    label = "n/a" if is_na else f"{val:.2f}%"
    ax2.text(bar.get_x() + bar.get_width()/2, val + 0.05, label,
             ha="center", va="bottom", fontsize=9, fontweight="bold")

# Verdict
for i, key in enumerate(PROFILES_ORDER):
    for offset, si_val in [
        (-w/2, results[key]["std_si"]),
        (+w/2, results[key]["new_si"]),
    ]:
        ok = si_val is not None and si_val <= 3.0
        ax2.text(i + offset, -0.4,
                 "✓" if ok else "✗",
                 ha="center", fontsize=13,
                 color="green" if ok else "red",
                 transform=ax2.get_xaxis_transform())

plt.tight_layout()
out = "docs/plots/si_comparison_standard_vs_terrain.png"
plt.savefig(out, dpi=150)
print(f"\nSaved → {out}")
print("\nHuman review required. If plots confirm:")
print("  - stairs step count recovered (terrain-aware ≈100)")
print("  - SI < 3% for all 4 profiles (terrain-aware)")
print("  - flat/slope/bad_wear unchanged")
print("Then proceed to port TerrainAwareStepDetector → step_detector.c")
