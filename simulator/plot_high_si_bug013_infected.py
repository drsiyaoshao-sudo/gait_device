"""
Plotter sub-agent — BUG-013 Infected Firmware Judicial Evidence
Generates: docs/executive_branch_document/plots/high_si_bug013_infected.png

Three-panel diagnostic plot for high_si walker profile vs BUG-013 infected firmware.
Dispatched by: Simulation Execution Standing Order (Amendment 11 / judicial evidence)

Panel 1: Per-step stance duration in ms (odd vs even steps), with reference lines
Panel 2: Running SI estimate per step pair from walker model vs true SI = 25%
Panel 3: Firmware-reported SI_stance% per snapshot vs true SI (25%) — labeled
         "BUG-013 infected firmware" to show VABS.F32 failure (SI always 0.0%)
"""
import sys
import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime

sys.path.insert(0, "/Users/siyaoshao/gait_device/simulator")

from walker_model import generate_imu_sequence, PROFILES, ODR_HZ

# ─── Load firmware results ────────────────────────────────────────────────────
results_path = "/tmp/high_si_bug013_infected_results.json"
with open(results_path) as f:
    results = json.load(f)

snapshots       = results["snapshots"]
fw_steps        = [s["anchor_step"] for s in snapshots]
fw_si           = [s["si_stance_pct"] for s in snapshots]
mean_fw_si      = results["mean_si_stance_pct"]
n_steps_det     = results["n_steps_detected"]
elf_path        = results["elf_path"]
elf_size        = results["elf_size_bytes"]
bug013_infected = results["bug013_infected"]

# ─── Numerical findings table ─────────────────────────────────────────────────
print("=" * 70)
print("[ plotter ] Numerical Findings Table — BUG-013 Infected Run")
print("=" * 70)
print(f"  ELF             : {elf_path}")
print(f"  ELF size        : {elf_size:,} bytes")
print(f"  BUG-013 infected: {bug013_infected}")
print(f"  Steps detected  : {n_steps_det}/100")
print(f"  Snapshots       : {len(snapshots)}")
print(f"  True SI         : 25.0%")
print(f"  Mean FW SI      : {mean_fw_si:.1f}%")
print()
print(f"  {'Snapshot':>10}  {'Step':>6}  {'FW SI%':>8}  {'True SI%':>9}  {'Delta':>8}")
print(f"  {'--------':>10}  {'------':>6}  {'------':>8}  {'---------':>9}  {'-----':>8}")
for i, sn in enumerate(snapshots):
    delta = sn["si_stance_pct"] - 25.0
    print(f"  {i+1:>10}  {sn['anchor_step']:>6}  "
          f"{sn['si_stance_pct']:>8.1f}  {'25.0':>9}  {delta:>+8.1f}")
print()
print(f"  DIAGNOSIS: fabsf() returns 0.0 in Renode 1.16.1 (VABS.F32 unsupported).")
print(f"             abs_diff = 0 in every compute_si_x10() call.")
print(f"             Result: SI = 200 * 0 / denom = 0.0% for all asymmetric walkers.")
print("=" * 70)

# ─── Reconstruct per-step stance durations ────────────────────────────────────
profile_key = "high_si"
profile = PROFILES[profile_key]

rng_timing = np.random.default_rng(42)

step_period_s = 60.0 / profile.cadence_spm
stance_nom_s  = step_period_s * profile.stance_frac
delta_s       = profile.si_stance_true_pct * stance_nom_s / 200.0

stance_nom_ms = stance_nom_s * 1000.0
delta_ms      = delta_s      * 1000.0
odd_expected  = (stance_nom_s + delta_s) * 1000.0
even_expected = (stance_nom_s - delta_s) * 1000.0

n_steps = 100
step_indices  = np.arange(n_steps)
stance_dur_ms = np.zeros(n_steps)

for i in range(n_steps):
    sign     = +1 if (i % 2 == 1) else -1
    noise    = rng_timing.normal(0, profile.step_variability_ms / 1000.0)
    stance_s = stance_nom_s + sign * delta_s + noise
    stance_s = max(stance_s, 0.10)
    stance_dur_ms[i] = stance_s * 1000.0
    _ = rng_timing.normal(0, profile.step_variability_ms * 0.5 / 1000.0)

# ─── Running SI estimate ──────────────────────────────────────────────────────
running_si = np.full(n_steps, np.nan)
for i in range(1, n_steps):
    if i % 2 == 0:
        t_odd  = stance_dur_ms[i - 1]
        t_even = stance_dur_ms[i]
    else:
        t_even = stance_dur_ms[i - 1]
        t_odd  = stance_dur_ms[i]
    si_val = 200.0 * abs(t_odd - t_even) / (t_odd + t_even)
    running_si[i] = si_val

true_si_mean = float(np.nanmean(running_si))

# ─── Plot ─────────────────────────────────────────────────────────────────────
odd_mask  = (step_indices % 2 == 1)
even_mask = (step_indices % 2 == 0)

fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
fig.suptitle(
    "BUG-013 INFECTED FIRMWARE — High SI Walker: Stance Timing Diagnostic\n"
    "Walker 5: Pathological Asymmetry, Flat, True SI = 25%  |  seed=42, 100 steps  |  "
    f"VABS.F32 failure — fabsf() = 0.0 in Renode 1.16.1  |  {run_date}",
    fontsize=12, fontweight="bold", y=0.99,
    color="#8b0000",
)

# ── Panel 1: Per-step stance duration ─────────────────────────────────────────
ax1 = axes[0]
ax1.scatter(step_indices[odd_mask],  stance_dur_ms[odd_mask],
            color="#e74c3c", s=40, zorder=5, label="Odd steps (affected limb)")
ax1.scatter(step_indices[even_mask], stance_dur_ms[even_mask],
            color="#3498db", s=40, zorder=5, label="Even steps (reference limb)")
ax1.plot(step_indices[odd_mask],  stance_dur_ms[odd_mask],
         color="#e74c3c", alpha=0.35, linewidth=1)
ax1.plot(step_indices[even_mask], stance_dur_ms[even_mask],
         color="#3498db", alpha=0.35, linewidth=1)

ax1.axhline(stance_nom_ms, color="black",   linestyle="--", linewidth=1.5,
            label=f"Nominal stance ({stance_nom_ms:.0f} ms)")
ax1.axhline(odd_expected,  color="#c0392b", linestyle=":",  linewidth=1.5,
            label=f"Expected odd ({odd_expected:.0f} ms, +{delta_ms:.0f} ms)")
ax1.axhline(even_expected, color="#2980b9", linestyle=":",  linewidth=1.5,
            label=f"Expected even ({even_expected:.0f} ms, -{delta_ms:.0f} ms)")

ax1.set_ylabel("Stance Duration (ms)", fontsize=11)
ax1.set_ylim(240, 490)
ax1.legend(loc="upper right", fontsize=9)
ax1.grid(True, alpha=0.3)
ax1.set_title("Panel 1: Per-Step Stance Duration (Walker Model — alternating asymmetry visible)",
              fontsize=10, loc="left")

# ── Panel 2: Running SI estimate ──────────────────────────────────────────────
ax2 = axes[1]
valid_mask = ~np.isnan(running_si)
ax2.plot(step_indices[valid_mask], running_si[valid_mask],
         color="#8e44ad", linewidth=2, marker="o", markersize=3,
         label=f"Running SI estimate (mean={true_si_mean:.1f}%)")
ax2.axhline(25.0, color="#2ecc71", linestyle="--", linewidth=2,
            label="True SI = 25% (ground truth)")
ax2.axhline(10.0, color="#e67e22", linestyle="-.", linewidth=2,
            label="Clinical threshold = 10%")
ax2.fill_between(step_indices[valid_mask], 10.0, running_si[valid_mask],
                 where=running_si[valid_mask] > 10.0,
                 alpha=0.15, color="#e74c3c", label="Above threshold region")

ax2.set_ylabel("Running SI Estimate (%)", fontsize=11)
ax2.set_ylim(0, 50)
ax2.legend(loc="upper right", fontsize=9)
ax2.grid(True, alpha=0.3)
ax2.set_title("Panel 2: Walker Model Running SI per Step Pair (signal is correct — 25% asymmetry present)",
              fontsize=10, loc="left")

# ── Panel 3: Firmware UART snapshots vs true SI ───────────────────────────────
ax3 = axes[2]

ax3.axhline(25.0, color="#2ecc71", linestyle=":", linewidth=2,
            label="Ground truth SI = 25%  (true asymmetry)")
ax3.axhline(10.0, color="#e67e22", linestyle="-.", linewidth=2,
            label="Clinical threshold = 10%")
ax3.axhline(true_si_mean, color="#8e44ad", linestyle="--", linewidth=1.5,
            label=f"Walker model SI mean = {true_si_mean:.1f}%")

# Firmware snapshots — all 0.0% due to BUG-013
ax3.step(fw_steps, fw_si, color="#8b0000", linewidth=2.5, where="post",
         label="BUG-013 infected firmware SI_stance%  (VABS.F32 → 0.0%)", zorder=5)
ax3.scatter(fw_steps, fw_si, color="#8b0000", s=100, zorder=6, marker="X")

# Annotate each snapshot
for sx, sv in zip(fw_steps, fw_si):
    ax3.annotate(f"{sv:.1f}%", (sx, sv),
                 textcoords="offset points", xytext=(0, 10),
                 fontsize=9, ha="center", color="#8b0000", fontweight="bold")

# Shaded gap: what the firmware SHOULD have reported
ax3.fill_between(range(max(fw_steps) + 1), 0, 25.0,
                 alpha=0.06, color="#8b0000",
                 label="Missed pathology zone (0–25%)")

# Bold annotation for the bug
ax3.text(50, 18,
         "BUG-013: fabsf() = 0.0 in Renode 1.16.1\n"
         "VABS.F32 instruction unsupported\n"
         "SI = 0.0% — pathology NOT reported\n"
         "(true SI = 25.6%, should ALERT)",
         fontsize=10, color="#8b0000", fontweight="bold",
         ha="center", va="center",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff0f0",
                   edgecolor="#8b0000", linewidth=2))

ax3.set_ylabel("Firmware Reported SI_stance% (%)", fontsize=11)
ax3.set_xlabel("Step Number", fontsize=11)
ax3.set_ylim(-2, 35)
ax3.legend(loc="upper right", fontsize=9)
ax3.grid(True, alpha=0.3)
ax3.set_title(
    "Panel 3: BUG-013 Infected Firmware UART Snapshots vs True SI  "
    "(all snapshots report 0.0% — VABS.F32 class failure)",
    fontsize=10, loc="left", color="#8b0000"
)

# Shared x-axis formatting
for ax in axes:
    ax.set_xlim(-2, 102)
    ax.tick_params(axis="both", labelsize=10)

plt.tight_layout(rect=[0, 0, 1, 0.95])

out_path = "/Users/siyaoshao/gait_device/docs/executive_branch_document/plots/high_si_bug013_infected.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
plt.close()

print(f"\n[ plotter ] Plot saved: {out_path}")
print(f"[ plotter ] True SI mean (walker model)       : {true_si_mean:.1f}%")
print(f"[ plotter ] Firmware mean SI_stance reported  : {mean_fw_si:.1f}%")
print(f"[ plotter ] All {len(fw_si)} firmware snapshots = 0.0%: "
      f"{'YES — BUG-013 confirmed' if all(v == 0.0 for v in fw_si) else 'NO'}")

# Open in Preview if GAITSENSE_DEMO=1
if os.environ.get("GAITSENSE_DEMO") == "1":
    os.system(f"open {out_path}")
