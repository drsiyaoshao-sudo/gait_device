"""
Three-algorithm comparison — step count and SI.

Standard algo    : acc-primary, 40ms gyr_y gate  (step_detector.c today)
Terrain-aware    : gyr_y_hp push-off threshold, acc confirm (no ring buffer)
Option C         : terrain-aware + ring-buffer heel-strike inference
                   (StepEvent carries heel_strike_ts_ms — SI still uses push-off intervals)

All three use identical filter chains and adaptive threshold.

Saved to docs/plots/option_c_si_comparison.png
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
    TerrainAwareStepDetector, ODR_HZ,
    _alpha_hp, _alpha_lp, HP_CUTOFF_HZ, LP_WALKING_HZ, LP_RUNNING_HZ,
    CADENCE_RUN_THRESH,
)

# ── Standard algorithm (mirrors step_detector.c) ──────────────────────────────

GYR_CONFIRM_MS  = 40
GYR_MIN_DPS     = 5.0
MIN_INTERVAL_MS = 250
PEAK_HISTORY    = 8
ACC_SEED        = 10.0

class StandardStepDetector:
    IDLE, RISING, FALLING, CONFIRMED = 0, 1, 2, 3

    def __init__(self):
        self.reset()

    def reset(self):
        self._hx = self._hy = self._ly = 0.0
        self._state = self.IDLE
        self._pc = self._pt = self._pg = 0.0
        self._hist = [ACC_SEED] * PEAK_HISTORY
        self._hi = 0
        self._lt = -(MIN_INTERVAL_MS + 1)
        self._steps = []; self._n = 0
        self._iv = [600.] * 4; self._ii = 0; self._cad = 100.

    def _hp(self, x):
        a = _alpha_hp(HP_CUTOFF_HZ)
        y = a * (self._hy + x - self._hx)
        self._hx, self._hy = x, y
        return y

    def _lp(self, x):
        a = _alpha_lp(LP_RUNNING_HZ if self._cad >= CADENCE_RUN_THRESH else LP_WALKING_HZ)
        self._ly = a * x + (1 - a) * self._ly
        return self._ly

    def _th(self): return 0.5 * sum(self._hist) / PEAK_HISTORY

    def _rec(self, p):
        self._hist[self._hi] = p
        self._hi = (self._hi + 1) % PEAK_HISTORY

    def update(self, ts, ax, ay, az, gy):
        mag = math.sqrt(ax*ax + ay*ay + az*az)
        af  = self._lp(self._hp(mag))
        th  = self._th()
        if self._state in (self.IDLE, self.CONFIRMED):
            if self._state == self.CONFIRMED and ts - self._lt < MIN_INTERVAL_MS:
                return None
            if af > th:
                self._state = self.RISING
                self._pc, self._pt, self._pg = af, ts, gy
        elif self._state == self.RISING:
            if af > self._pc:
                self._pc, self._pt, self._pg = af, ts, gy
            else:
                self._state = self.FALLING
        elif self._state == self.FALLING:
            el = ts - self._pt
            if self._pg * gy < 0 and el <= GYR_CONFIRM_MS and abs(self._pg) >= GYR_MIN_DPS:
                self._rec(self._pc)
                if self._n > 0:
                    self._iv[self._ii] = self._pt - self._lt
                    self._ii = (self._ii + 1) % 4
                    self._cad = 60000. / (sum(self._iv) / 4 or 1)
                self._steps.append({"step_index": self._n, "ts_ms": self._pt})
                self._lt = self._pt; self._n += 1; self._state = self.CONFIRMED
            elif el > GYR_CONFIRM_MS:
                self._state = self.IDLE
        return None

    @property
    def steps(self): return self._steps


# ── Run all three algorithms ───────────────────────────────────────────────────

def run_all(profile_key, n_steps=100, seed=42):
    profile = PROFILES[profile_key]
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)

    std = StandardStepDetector()
    ta  = TerrainAwareStepDetector()   # Option C is now the only implementation

    for i, row in enumerate(samples):
        ts = i / ODR_HZ * 1000.0
        std.update(ts, row[0], row[1], row[2], row[4])
        ta.update(ts,  row[0], row[1], row[2], row[4])

    return std.steps, ta.steps


def si_from_steps(steps_list, ts_key="ts_ms", idx_key="step_index", warmup=4):
    if not steps_list or len(steps_list) < warmup + 4:
        return None
    if isinstance(steps_list[0], dict):
        ts = {s[idx_key]: s[ts_key] for s in steps_list}
    else:
        ts = {s.step_index: s.ts_ms for s in steps_list}
    indices = sorted(ts)
    ivals   = {indices[i]: ts[indices[i+1]] - ts[indices[i]]
               for i in range(len(indices) - 1)}
    odd  = [v for k, v in ivals.items() if k >= warmup and k % 2 == 1]
    even = [v for k, v in ivals.items() if k >= warmup and k % 2 == 0]
    if not odd or not even:
        return None
    T_o, T_e = sum(odd) / len(odd), sum(even) / len(even)
    denom = T_o + T_e
    return 200.0 * abs(T_o - T_e) / denom if denom > 1e-6 else None


# ── Also compute SI using heel_strike_ts for Option C ─────────────────────────

def si_from_heel_strike(ta_steps, warmup=4):
    """SI computed from heel_strike_ts_ms intervals (Option C only)."""
    steps = [s for s in ta_steps if s.step_index >= warmup and s.heel_strike_ts_ms != s.ts_ms]
    if len(steps) < 4:
        return None
    tms     = [s.heel_strike_ts_ms for s in steps]
    ivals   = [tms[i+1] - tms[i] for i in range(len(tms) - 1)]
    odd  = [ivals[i] for i in range(len(ivals)) if i % 2 == 1]
    even = [ivals[i] for i in range(len(ivals)) if i % 2 == 0]
    if not odd or not even:
        return None
    T_o, T_e = sum(odd) / len(odd), sum(even) / len(even)
    denom = T_o + T_e
    return 200.0 * abs(T_o - T_e) / denom if denom > 1e-6 else None


# ── Collect results ───────────────────────────────────────────────────────────

PROFILES_ORDER = ["flat", "bad_wear", "slope", "stairs"]
LABELS         = ["Flat", "Bad wear", "Slope (10°)", "Stairs"]
N_STEPS        = 100

results = {}
print(f"{'Profile':<12}  {'Std cnt':>7}  {'OC cnt':>7}  "
      f"{'Std SI%':>8}  {'OC push-off SI%':>15}  {'OC hs SI%':>10}")
print("─" * 70)

for key, label in zip(PROFILES_ORDER, LABELS):
    std_steps, ta_steps = run_all(key, N_STEPS)
    std_si = si_from_steps(std_steps)
    oc_si  = si_from_steps(ta_steps)          # push-off intervals (same as before)
    oc_hs_si = si_from_heel_strike(ta_steps)  # heel-strike intervals (Option C bonus)

    results[key] = dict(
        label=label,
        std_count=len(std_steps),
        oc_count=len(ta_steps),
        std_si=std_si,
        oc_si=oc_si,
        oc_hs_si=oc_hs_si,
    )
    print(f"{label:<12}  {len(std_steps):>7}  {len(ta_steps):>7}  "
          f"{std_si or 0:>8.2f}  {oc_si or 0:>15.2f}  {oc_hs_si or 0:>10.2f}")

print()

# ── Plot ──────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(1, 2, figsize=(15, 7))
fig.suptitle(
    "Step Count & SI — Standard Algorithm vs Option C (Terrain-Aware + Ring-Buffer)\n"
    "All 4 Walker Profiles  |  100 steps each  |  seed=42",
    fontsize=12,
)

x = np.arange(len(PROFILES_ORDER))
w = 0.3

COLOR_STD = "#90CAF9"   # light blue  — standard
COLOR_OC  = "#1565C0"   # dark blue   — option C push-off SI
COLOR_HS  = "#43A047"   # green       — option C heel-strike SI

# ─── Panel 1: Step count ──────────────────────────────────────────────────────
ax1 = axes[0]

b1 = ax1.bar(x - w/2, [results[k]["std_count"] for k in PROFILES_ORDER], w,
             color=COLOR_STD, label="Standard (acc-primary, 40ms gate)", edgecolor="white")
b2 = ax1.bar(x + w/2, [results[k]["oc_count"]  for k in PROFILES_ORDER], w,
             color=COLOR_OC,  label="Option C (gyr_y_hp push-off + ring buffer)", edgecolor="white")

ax1.axhline(100, color="green",  linewidth=1.2, linestyle="--", label="Target (100 ±5)")
ax1.axhline(95,  color="green",  linewidth=0.6, linestyle=":",  alpha=0.5)
ax1.axhline(105, color="green",  linewidth=0.6, linestyle=":",  alpha=0.5)
ax1.set_xticks(x); ax1.set_xticklabels(LABELS, fontsize=10)
ax1.set_ylabel("Steps detected"); ax1.set_title("Step Count (target 100 ±5)")
ax1.set_ylim(0, 120); ax1.legend(fontsize=8); ax1.grid(True, axis="y", alpha=0.3)

for bar, val in zip(list(b1) + list(b2),
                    [results[k]["std_count"] for k in PROFILES_ORDER] +
                    [results[k]["oc_count"]  for k in PROFILES_ORDER]):
    ax1.text(bar.get_x() + bar.get_width()/2, val + 1, str(val),
             ha="center", va="bottom", fontsize=9, fontweight="bold")

for i, key in enumerate(PROFILES_ORDER):
    for offset, count in [(-w/2, results[key]["std_count"]),
                          (+w/2, results[key]["oc_count"])]:
        ok = abs(count - 100) <= 5
        ax1.text(i + offset, -10, "✓" if ok else "✗",
                 ha="center", fontsize=13,
                 color="green" if ok else "red",
                 transform=ax1.get_xaxis_transform())

# ─── Panel 2: SI ──────────────────────────────────────────────────────────────
ax2 = axes[1]

std_si_vals  = [results[k]["std_si"]   or 0 for k in PROFILES_ORDER]
oc_si_vals   = [results[k]["oc_si"]    or 0 for k in PROFILES_ORDER]
oc_hs_vals   = [results[k]["oc_hs_si"] or 0 for k in PROFILES_ORDER]

# Three bars per profile: std / OC push-off / OC heel-strike
x3 = np.arange(len(PROFILES_ORDER))
w3 = 0.22
b3 = ax2.bar(x3 - w3,     std_si_vals, w3, color=COLOR_STD, label="Standard SI (push-off)", edgecolor="white")
b4 = ax2.bar(x3,          oc_si_vals,  w3, color=COLOR_OC,  label="Option C SI (push-off intervals)", edgecolor="white")
b5 = ax2.bar(x3 + w3,     oc_hs_vals,  w3, color=COLOR_HS,  label="Option C SI (heel-strike intervals)", edgecolor="white")

ax2.axhline(3.0, color="red", linewidth=1.2, linestyle="--", label="3% tolerance")
ax2.set_xticks(x3); ax2.set_xticklabels(LABELS, fontsize=10)
ax2.set_ylabel("SI_interval (%)"); ax2.set_title("Symmetry Index — interval method (target <3%)")
ax2.set_ylim(0, max(max(std_si_vals), max(oc_si_vals), max(oc_hs_vals), 3.5) * 1.35)
ax2.legend(fontsize=8); ax2.grid(True, axis="y", alpha=0.3)

std_na  = [results[k]["std_si"]   is None for k in PROFILES_ORDER]
oc_na   = [results[k]["oc_si"]    is None for k in PROFILES_ORDER]
oc_hs_na= [results[k]["oc_hs_si"] is None for k in PROFILES_ORDER]

for bar, val, is_na in zip(
    list(b3) + list(b4) + list(b5),
    std_si_vals + oc_si_vals + oc_hs_vals,
    std_na + oc_na + oc_hs_na,
):
    label = "n/a" if is_na else f"{val:.2f}%"
    ax2.text(bar.get_x() + bar.get_width()/2, val + 0.05, label,
             ha="center", va="bottom", fontsize=8, fontweight="bold")

for i, key in enumerate(PROFILES_ORDER):
    for offset, si_val in [(-w3,    results[key]["std_si"]),
                           (0,      results[key]["oc_si"]),
                           (+w3,    results[key]["oc_hs_si"])]:
        ok = si_val is not None and si_val <= 3.0
        ax2.text(i + offset, -0.45, "✓" if ok else "✗",
                 ha="center", fontsize=13,
                 color="green" if ok else "red",
                 transform=ax2.get_xaxis_transform())

plt.tight_layout()
out = "docs/plots/option_c_si_comparison.png"
plt.savefig(out, dpi=150)
print(f"Saved → {out}")
