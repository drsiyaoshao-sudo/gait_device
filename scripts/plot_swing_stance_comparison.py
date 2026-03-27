"""
Swing/stance analysis — standard vs terrain-aware detector, all 4 walkers.

Key question before C port:
  Standard detector fires at heel-strike → stance = heel_strike[N] to toe-off
  Terrain-aware detector fires at push-off → stance measurement shifts by one phase

What this plot shows:
  Panel 1: Step period (push-off to push-off) vs ground truth (walker model)
  Panel 2: Odd/even step interval breakdown — symmetry check
  Panel 3: Inferred stance fraction — does the detector preserve stance/swing ratio?
  Panel 4: Architectural implication — what the phase_segmenter.c would receive
           if the heel_strike callback is fired at push-off instead of heel-strike

Ground truth from walker_model:
  step_period  = 60 / cadence_spm  (seconds)
  stance_dur   = step_period * stance_frac
  swing_dur    = step_period * (1 - stance_frac)
"""

import sys, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))
from walker_model import PROFILES, generate_imu_sequence
from terrain_aware_step_detector import TerrainAwareStepDetector, ODR_HZ
from terrain_aware_step_detector import (
    _alpha_hp, _alpha_lp, HP_CUTOFF_HZ, LP_WALKING_HZ, LP_RUNNING_HZ,
    CADENCE_RUN_THRESH,
)

# ── Standard detector (Python mirror) ────────────────────────────────────────

GYR_CONFIRM_MS = 40; GYR_MIN_DPS = 5.0; MIN_IV_MS = 250
PEAK_H = 8; ACC_SEED = 10.0
IDLE, RISING, FALLING, CONFIRMED = 0, 1, 2, 3

class StandardDetector:
    def __init__(self):
        self._hx=self._hy=self._ly=0.0; self._st=IDLE
        self._pc=self._pt=self._pg=0.0
        self._hist=[ACC_SEED]*PEAK_H; self._hi=0
        self._lt=-(MIN_IV_MS+1); self._steps=[]; self._n=0
        self._iv=[600.]*4; self._ii=0; self._cad=100.
    def _hp(self,x):
        a=_alpha_hp(HP_CUTOFF_HZ); y=a*(self._hy+x-self._hx)
        self._hx,self._hy=x,y; return y
    def _lp(self,x):
        a=_alpha_lp(LP_RUNNING_HZ if self._cad>=CADENCE_RUN_THRESH else LP_WALKING_HZ)
        self._ly=a*x+(1-a)*self._ly; return self._ly
    def _th(self): return 0.5*sum(self._hist)/PEAK_H
    def _rec(self,p): self._hist[self._hi]=p; self._hi=(self._hi+1)%PEAK_H
    def update(self,ts,ax,ay,az,gy):
        mag=math.sqrt(ax*ax+ay*ay+az*az); af=self._lp(self._hp(mag)); th=self._th()
        if self._st in (IDLE,CONFIRMED):
            if self._st==CONFIRMED and ts-self._lt<MIN_IV_MS: return None
            if af>th: self._st=RISING; self._pc=af; self._pt=ts; self._pg=gy
        elif self._st==RISING:
            if af>self._pc: self._pc=af; self._pt=ts; self._pg=gy
            else: self._st=FALLING
        elif self._st==FALLING:
            el=ts-self._pt
            if self._pg*gy<0 and el<=GYR_CONFIRM_MS and abs(self._pg)>=GYR_MIN_DPS:
                self._rec(self._pc)
                if self._n>0:
                    self._iv[self._ii]=(self._pt-self._lt); self._ii=(self._ii+1)%4
                    self._cad=60000./((sum(self._iv)/4) or 1)
                self._steps.append({"ts":self._pt,"idx":self._n}); self._lt=self._pt; self._n+=1; self._st=CONFIRMED
            elif el>GYR_CONFIRM_MS: self._st=IDLE
        return None
    @property
    def steps(self): return self._steps

# ── Run both detectors ────────────────────────────────────────────────────────

def run(profile_key, n_steps=100, seed=42):
    profile = PROFILES[profile_key]
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)

    std = StandardDetector()
    new = TerrainAwareStepDetector()

    for i, row in enumerate(samples):
        ts = i / ODR_HZ * 1000.0
        std.update(ts, *row[:3], row[4])
        new.update(ts, *row[:3], row[4])

    return profile, std.steps, new.steps

# ── Compute intervals ─────────────────────────────────────────────────────────

def intervals(steps, ts_key="ts", warmup=4):
    if len(steps) < warmup + 2: return [], []
    ts  = sorted(steps, key=lambda s: s[ts_key] if isinstance(s, dict) else s.ts_ms)
    tms = [s[ts_key] if isinstance(s, dict) else s.ts_ms for s in ts]
    ivs = [tms[i+1]-tms[i] for i in range(len(tms)-1)]
    odd  = [ivs[i] for i in range(len(ivs)) if i >= warmup and i % 2 == 1]
    even = [ivs[i] for i in range(len(ivs)) if i >= warmup and i % 2 == 0]
    return odd, even

PROFILES_ORDER = ["flat", "bad_wear", "slope", "stairs"]
LABELS = ["Flat", "Bad wear", "Slope (10°)", "Stairs"]
COLORS = {"flat":"#2196F3","bad_wear":"#FF9800","slope":"#4CAF50","stairs":"#F44336"}

results = {}
for key, label in zip(PROFILES_ORDER, LABELS):
    profile, std_steps, new_steps = run(key)

    gt_period_ms  = (60.0 / profile.cadence_spm) * 1000.0
    gt_stance_ms  = gt_period_ms * profile.stance_frac
    gt_swing_ms   = gt_period_ms * (1 - profile.stance_frac)

    std_odd, std_even = intervals(std_steps, ts_key="ts")
    new_odd, new_even = intervals(new_steps)

    std_mean = (sum(std_odd+std_even)/(len(std_odd+std_even))) if std_odd or std_even else 0
    new_mean = (sum(new_odd+new_even)/(len(new_odd+new_even))) if new_odd or new_even else 0

    results[key] = dict(
        label=label, profile=profile,
        gt_period=gt_period_ms, gt_stance=gt_stance_ms, gt_swing=gt_swing_ms,
        std_steps=std_steps, new_steps=new_steps,
        std_odd=std_odd, std_even=std_even,
        new_odd=new_odd, new_even=new_even,
        std_mean=std_mean, new_mean=new_mean,
    )

    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"{'─'*60}")
    print(f"  Ground truth   period={gt_period_ms:.0f}ms  stance={gt_stance_ms:.0f}ms  swing={gt_swing_ms:.0f}ms")
    print(f"  Standard       steps={len(std_steps)}  mean_interval={std_mean:.0f}ms")
    print(f"  Terrain-aware  steps={len(new_steps)}  mean_interval={new_mean:.0f}ms")
    if new_odd and new_even:
        T_o=sum(new_odd)/len(new_odd); T_e=sum(new_even)/len(new_even)
        si=200*abs(T_o-T_e)/(T_o+T_e)
        print(f"  TA odd={T_o:.0f}ms  even={T_e:.0f}ms  SI={si:.2f}%")

print()
print("="*60)
print("  ARCHITECTURAL NOTE")
print("="*60)
print("  Terrain-aware fires at push-off (end of stance).")
print("  Standard fires at heel-strike (start of stance).")
print("  If phase_segmenter.c on_heel_strike() fires at push-off:")
print("    → PHASE_LOADING starts at wrong time")
print("    → stance_duration = push-off[N] to push-off[N+1]")
print("      ≈ swing[N] + stance[N+1]  (NOT stance[N])")
print("  C port requires rethinking phase_segmenter event contract.")
print()

# ── Plot ──────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle(
    "Swing/Stance Analysis — Standard vs Terrain-Aware Detector\n"
    "All 4 Walker Profiles  |  100 steps each  |  seed=42",
    fontsize=13
)

x = np.arange(len(PROFILES_ORDER))
w = 0.25

# ─── Panel 1 (top-left): Step period vs ground truth ─────────────────────────
ax1 = axes[0, 0]
ax1.set_title("Step Period: Ground Truth vs Detected", fontsize=10)

gt_vals  = [results[k]["gt_period"]  for k in PROFILES_ORDER]
std_vals = [results[k]["std_mean"]   for k in PROFILES_ORDER]
new_vals = [results[k]["new_mean"]   for k in PROFILES_ORDER]

b0 = ax1.bar(x - w, gt_vals,  w, color="lightgrey", label="Ground truth", edgecolor="white")
b1 = ax1.bar(x,     std_vals, w, color="#90CAF9",   label="Standard",     edgecolor="white")
b2 = ax1.bar(x + w, new_vals, w, color="#1565C0",   label="Terrain-aware",edgecolor="white")

for bars, vals in [(b0,gt_vals),(b1,std_vals),(b2,new_vals)]:
    for bar, v in zip(bars, vals):
        if v > 0:
            ax1.text(bar.get_x()+bar.get_width()/2, v+5, f"{v:.0f}",
                     ha="center", va="bottom", fontsize=8)

ax1.set_xticks(x); ax1.set_xticklabels(LABELS, fontsize=9)
ax1.set_ylabel("Step period (ms)"); ax1.legend(fontsize=8); ax1.grid(True, axis="y", alpha=0.3)
ax1.set_ylim(0, max(gt_vals)*1.25)

# ─── Panel 2 (top-right): Odd vs even intervals — terrain-aware ──────────────
ax2 = axes[0, 1]
ax2.set_title("Terrain-Aware: Odd vs Even Step Intervals\n(symmetry check — should be equal)", fontsize=10)

for i, key in enumerate(PROFILES_ORDER):
    r = results[key]
    if r["new_odd"] and r["new_even"]:
        T_o = sum(r["new_odd"])  / len(r["new_odd"])
        T_e = sum(r["new_even"]) / len(r["new_even"])
        ax2.bar(i - w/2, T_o, w, color=COLORS[key], alpha=0.9, label=r["label"])
        ax2.bar(i + w/2, T_e, w, color=COLORS[key], alpha=0.4)
        ax2.text(i - w/2, T_o+4, f"{T_o:.0f}", ha="center", fontsize=8)
        ax2.text(i + w/2, T_e+4, f"{T_e:.0f}", ha="center", fontsize=8)

ax2.set_xticks(x); ax2.set_xticklabels(LABELS, fontsize=9)
ax2.set_ylabel("Interval (ms)")
ax2.legend(fontsize=8); ax2.grid(True, axis="y", alpha=0.3)
ax2.set_ylim(0, max(gt_vals)*1.25)
# Dark = odd, light = even label
from matplotlib.patches import Patch
ax2.legend(handles=[
    Patch(facecolor="grey", alpha=0.9, label="Odd steps (dark)"),
    Patch(facecolor="grey", alpha=0.4, label="Even steps (light)"),
], fontsize=8, loc="upper right")

# ─── Panel 3 (bottom-left): Ground truth stance/swing vs detected period ──────
ax3 = axes[1, 0]
ax3.set_title("Ground Truth Stance & Swing vs Terrain-Aware Period\n"
              "(push-off detection: period ≈ stance + swing of NEXT step)", fontsize=10)

for i, key in enumerate(PROFILES_ORDER):
    r = results[key]
    # Stacked bar: stance + swing = ground truth period
    ax3.bar(i - w/2, r["gt_stance"], w, color=COLORS[key], alpha=0.9, label="Stance")
    ax3.bar(i - w/2, r["gt_swing"],  w, bottom=r["gt_stance"],
            color=COLORS[key], alpha=0.35, label="Swing")
    # Terrain-aware detected period
    if r["new_mean"] > 0:
        ax3.bar(i + w/2, r["new_mean"], w, color=COLORS[key], alpha=0.6,
                hatch="///", edgecolor="white")
    ax3.text(i - w/2, r["gt_period"]+5,
             f"S:{r['gt_stance']:.0f}\nW:{r['gt_swing']:.0f}", ha="center", fontsize=7)
    ax3.text(i + w/2, r["new_mean"]+5, f"{r['new_mean']:.0f}", ha="center", fontsize=8)

ax3.set_xticks(x); ax3.set_xticklabels(LABELS, fontsize=9)
ax3.set_ylabel("Duration (ms)")
ax3.grid(True, axis="y", alpha=0.3); ax3.set_ylim(0, max(gt_vals)*1.3)
ax3.legend(handles=[
    Patch(facecolor="grey", alpha=0.9, label="GT stance"),
    Patch(facecolor="grey", alpha=0.35, label="GT swing"),
    Patch(facecolor="grey", alpha=0.6, hatch="///", label="TA detected period"),
], fontsize=8, loc="upper right")

# ─── Panel 4 (bottom-right): Phase segmenter impact ─────────────────────────
ax4 = axes[1, 1]
ax4.set_title("Phase Segmenter Impact of Push-Off Detection\n"
              "(what phase_segmenter.c would compute if on_heel_strike fires at push-off)",
              fontsize=10)
ax4.axis("off")

rows = [["Profile", "GT stance (ms)", "GT swing (ms)", "TA period (ms)",
         "Computed stance*", "Error"]]
for key in PROFILES_ORDER:
    r = results[key]
    # If on_heel_strike fires at push-off[N], next fires at push-off[N+1]
    # phase_segmenter computes stance = push-off[N+1] - push-off[N]
    # = step_period ≈ swing[N] + stance[N+1]  (not stance[N])
    computed_stance = r["new_mean"]  # what phase_segmenter would record
    error_ms = computed_stance - r["gt_stance"]
    rows.append([
        r["label"],
        f"{r['gt_stance']:.0f}",
        f"{r['gt_swing']:.0f}",
        f"{r['new_mean']:.0f}" if r["new_mean"] > 0 else "n/a",
        f"{computed_stance:.0f}" if r["new_mean"] > 0 else "n/a",
        f"+{error_ms:.0f}ms" if r["new_mean"] > 0 else "n/a",
    ])

table = ax4.table(cellText=rows[1:], colLabels=rows[0],
                   loc="center", cellLoc="center")
table.auto_set_font_size(False); table.set_fontsize(9)
table.scale(1.2, 2.0)

# Highlight error column red
for row_idx in range(1, len(rows)):
    table[row_idx, 5].set_facecolor("#FFCDD2")

ax4.text(0.5, 0.08,
    "* Computed stance = push-off period ≈ swing[N] + stance[N+1]\n"
    "  This is ~full step period, not stance duration.\n"
    "  C port must decouple step detection from phase_segmenter event contract.",
    ha="center", va="bottom", transform=ax4.transAxes,
    fontsize=8.5, color="#B71C1C",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFEBEE", edgecolor="#EF9A9A"))

plt.tight_layout()
out = "docs/plots/swing_stance_comparison.png"
plt.savefig(out, dpi=150)
print(f"Saved → {out}")
