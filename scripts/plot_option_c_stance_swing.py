"""
Option C validation plot — stance and swing accuracy with ring-buffer heel-strike inference.

Shows for all 4 walker profiles:
  Panel 1: Mean stance_duration_ms (Option C) vs ground truth — error bar chart
  Panel 2: Mean swing_duration_ms (Option C) vs ground truth — error bar chart
  Panel 3: Stance error improvement table
           (push-off only: +295ms error  →  Option C: -50 to -100ms)
  Panel 4: Per-step stance_duration scatter (stairs closeup)

Saved to docs/executive_branch_document/plots/option_c_stance_swing_accuracy.png
"""

import sys, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))
from walker_model import PROFILES, generate_imu_sequence
from terrain_aware_step_detector import TerrainAwareStepDetector, ODR_HZ

PROFILES_ORDER = ["flat", "bad_wear", "slope", "stairs"]
LABELS         = ["Flat", "Bad wear", "Slope (10°)", "Stairs"]
COLORS         = {"flat": "#2196F3", "bad_wear": "#FF9800",
                  "slope": "#4CAF50", "stairs":   "#F44336"}

# Ground truth from walker_model (step_period × stance_frac / swing_frac)
GT = {
    "flat":     {"period": 571.0, "stance": 343.0, "swing": 229.0},
    "bad_wear": {"period": 571.0, "stance": 343.0, "swing": 229.0},
    "slope":    {"period": 632.0, "stance": 392.0, "swing": 240.0},
    "stairs":   {"period": 857.0, "stance": 557.0, "swing": 300.0},
}

WARMUP = 4


def run(profile_key, n_steps=100, seed=42):
    profile = PROFILES[profile_key]
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)
    det     = TerrainAwareStepDetector()
    for i, row in enumerate(samples):
        ts = i / ODR_HZ * 1000.0
        det.update(ts, row[0], row[1], row[2], row[4])
    return det.steps


# ── Collect results ───────────────────────────────────────────────────────────

results = {}
for key, label in zip(PROFILES_ORDER, LABELS):
    steps = run(key)
    core  = [s for s in steps if s.step_index >= WARMUP]
    # Exclude last step from swing (not yet backfilled)
    core_swing = [s for s in core if s.step_index < len(steps) - 1]

    mean_stance = (sum(s.stance_duration_ms for s in core) / len(core)) if core else 0
    mean_swing  = (sum(s.swing_duration_ms  for s in core_swing) / len(core_swing)) if core_swing else 0

    gt = GT[key]
    stance_err = mean_stance - gt["stance"]
    swing_err  = mean_swing  - gt["swing"]

    results[key] = dict(
        label=label,
        mean_stance=mean_stance, stance_err=stance_err,
        mean_swing=mean_swing,   swing_err=swing_err,
        gt_stance=gt["stance"],  gt_swing=gt["swing"],
        gt_period=gt["period"],
        # Per-step arrays for scatter (stairs)
        stance_per_step=[s.stance_duration_ms for s in core],
        swing_per_step=[s.swing_duration_ms   for s in core_swing],
        n_steps=len(steps),
    )

    print(f"{'─'*60}")
    print(f"  {label}")
    print(f"  GT  stance={gt['stance']:.0f}ms  swing={gt['swing']:.0f}ms  period={gt['period']:.0f}ms")
    print(f"  OC  stance={mean_stance:.1f}ms (err={stance_err:+.1f}ms)  "
          f"swing={mean_swing:.1f}ms (err={swing_err:+.1f}ms)")

print()

# ── Plot ──────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle(
    "Option C — Stance/Swing Accuracy After Ring-Buffer Heel-Strike Inference\n"
    "All 4 Walker Profiles  |  100 steps each  |  seed=42",
    fontsize=13,
)

x = np.arange(len(PROFILES_ORDER))
w = 0.3

# ─── Panel 1: Stance duration ─────────────────────────────────────────────────
ax1 = axes[0, 0]
ax1.set_title("Stance Duration: Option C vs Ground Truth", fontsize=10)

gt_s  = [results[k]["gt_stance"]   for k in PROFILES_ORDER]
oc_s  = [results[k]["mean_stance"] for k in PROFILES_ORDER]

b0 = ax1.bar(x - w/2, gt_s, w, color="lightgrey", label="Ground truth", edgecolor="white")
b1 = ax1.bar(x + w/2, oc_s, w, color="#1565C0",   label="Option C",     edgecolor="white")

for bar, v in zip(b0, gt_s):
    ax1.text(bar.get_x() + bar.get_width()/2, v + 5, f"{v:.0f}",
             ha="center", va="bottom", fontsize=8)
for bar, v, err in zip(b1, oc_s, [results[k]["stance_err"] for k in PROFILES_ORDER]):
    ax1.text(bar.get_x() + bar.get_width()/2, v + 5,
             f"{v:.0f}\n({err:+.0f}ms)", ha="center", va="bottom", fontsize=7.5)

ax1.set_xticks(x); ax1.set_xticklabels(LABELS, fontsize=9)
ax1.set_ylabel("Duration (ms)"); ax1.legend(fontsize=8)
ax1.grid(True, axis="y", alpha=0.3)
ax1.set_ylim(0, max(gt_s) * 1.35)

# ─── Panel 2: Swing duration ──────────────────────────────────────────────────
ax2 = axes[0, 1]
ax2.set_title("Swing Duration: Option C vs Ground Truth", fontsize=10)

gt_w  = [results[k]["gt_swing"]   for k in PROFILES_ORDER]
oc_w  = [results[k]["mean_swing"] for k in PROFILES_ORDER]

b2 = ax2.bar(x - w/2, gt_w, w, color="lightgrey", label="Ground truth", edgecolor="white")
b3 = ax2.bar(x + w/2, oc_w, w, color="#388E3C",   label="Option C",     edgecolor="white")

for bar, v in zip(b2, gt_w):
    ax2.text(bar.get_x() + bar.get_width()/2, v + 5, f"{v:.0f}",
             ha="center", va="bottom", fontsize=8)
for bar, v, err in zip(b3, oc_w, [results[k]["swing_err"] for k in PROFILES_ORDER]):
    ax2.text(bar.get_x() + bar.get_width()/2, v + 5,
             f"{v:.0f}\n({err:+.0f}ms)", ha="center", va="bottom", fontsize=7.5)

ax2.set_xticks(x); ax2.set_xticklabels(LABELS, fontsize=9)
ax2.set_ylabel("Duration (ms)"); ax2.legend(fontsize=8)
ax2.grid(True, axis="y", alpha=0.3)
ax2.set_ylim(0, max(gt_w) * 1.5)

# ─── Panel 3: Error improvement table ─────────────────────────────────────────
ax3 = axes[1, 0]
ax3.set_title("Stance Error: Push-Off Only vs Option C", fontsize=10)
ax3.axis("off")

# Push-off only error = TA detected period - GT stance (from algorithm_hunting doc)
po_only_err = {
    "flat":     +224, "bad_wear": +224, "slope": +232, "stairs": +295
}

rows = [["Profile", "GT stance (ms)", "Push-off only err", "Option C mean", "Option C err", "Improvement"]]
for key in PROFILES_ORDER:
    r   = results[key]
    po  = po_only_err[key]
    oc  = r["stance_err"]
    imp = po - oc   # positive = Option C is better (less overshoot)
    rows.append([
        r["label"],
        f"{r['gt_stance']:.0f}",
        f"+{po}ms",
        f"{r['mean_stance']:.0f}ms",
        f"{oc:+.0f}ms",
        f"−{imp:.0f}ms better",
    ])

table = ax3.table(cellText=rows[1:], colLabels=rows[0], loc="center", cellLoc="center")
table.auto_set_font_size(False); table.set_fontsize(9)
table.scale(1.1, 2.2)

# Red push-off error, green option C error
for row_idx in range(1, len(rows)):
    table[row_idx, 2].set_facecolor("#FFCDD2")   # push-off only — red
    table[row_idx, 4].set_facecolor("#C8E6C9")   # option C      — green
    table[row_idx, 5].set_facecolor("#E3F2FD")   # improvement   — blue

ax3.text(0.5, 0.04,
    "Push-off only: phase_segmenter receives stance ≈ full step period\n"
    "Option C: first acc_filt crossing used as heel-strike → stance error < 100ms",
    ha="center", va="bottom", transform=ax3.transAxes,
    fontsize=8.5, color="#1B5E20",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#F1F8E9", edgecolor="#A5D6A7"))

# ─── Panel 4: Per-step stance scatter — stairs closeup ───────────────────────
ax4 = axes[1, 1]
ax4.set_title("Per-Step Stance Duration — Stairs (Option C vs GT)", fontsize=10)

stairs_stance = results["stairs"]["stance_per_step"]
step_indices  = list(range(WARMUP, WARMUP + len(stairs_stance)))

ax4.scatter(step_indices, stairs_stance, color="#F44336", s=18, label="Option C stance", zorder=3)
ax4.axhline(GT["stairs"]["stance"], color="green", linewidth=1.5, linestyle="--",
            label=f"GT stance = {GT['stairs']['stance']:.0f}ms")
ax4.axhline(GT["stairs"]["period"], color="grey", linewidth=1.0, linestyle=":",
            label=f"GT period = {GT['stairs']['period']:.0f}ms (push-off-only error)")
ax4.fill_between([step_indices[0], step_indices[-1]],
                 GT["stairs"]["stance"] - 150, GT["stairs"]["stance"] + 150,
                 alpha=0.10, color="green", label="±150ms tolerance")

ax4.set_xlabel("Step index"); ax4.set_ylabel("Stance duration (ms)")
ax4.legend(fontsize=8); ax4.grid(True, alpha=0.3)
ax4.set_ylim(0, GT["stairs"]["period"] * 1.1)

plt.tight_layout()
out = "docs/executive_branch_document/plots/option_c_stance_swing_accuracy.png"
plt.savefig(out, dpi=150)
print(f"Saved → {out}")
print()
print("Human review checkpoint:")
print("  - Stance error < 100ms for flat/bad_wear/slope?")
print("  - Stairs stance error < 150ms (Option C: -50 to -100ms expected)?")
print("  - Swing populated correctly (non-zero, reasonable values)?")
print("  - Per-step stairs scatter clustered around GT line (not at 852ms period line)?")
