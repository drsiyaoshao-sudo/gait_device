"""
Plotter sub-agent — BUG-013 Judicial Hearing Evidence
Generates: docs/executive_branch_document/plots/high_si_stance_timing.png

Three-panel stance timing diagnostic plot for the high_si walker profile.
Dispatched by: Simulation Execution Standing Order (Amendment 11 / judicial evidence)

Panel 1: Per-step stance duration in ms (odd vs even steps), with reference lines
Panel 2: Running SI estimate per step (true alternating pattern)
Panel 3: Reported firmware SI_stance% from UART snapshots overlaid on true SI line
"""
import sys
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, "/Users/siyaoshao/gait_device/simulator")

from walker_model import generate_imu_sequence, PROFILES, ODR_HZ

# ─── Load firmware results ────────────────────────────────────────────────────
results_path = "/tmp/high_si_renode_results.json"
with open(results_path) as f:
    results = json.load(f)

snapshots = results["snapshots"]
fw_steps  = [s["anchor_step"] for s in snapshots]
fw_si     = [s["si_stance_pct"] for s in snapshots]

# ─── Reconstruct per-step stance durations from walker model ─────────────────
profile_key = "high_si"
profile = PROFILES[profile_key]

# Re-generate with seed=42 to reproduce the same timing as the Renode run
rng_timing = np.random.default_rng(42)

# Derive timing parameters from profile (same formula as walker_model._generate_step)
step_period_s  = 60.0 / profile.cadence_spm          # 0.600 s
stance_nom_s   = step_period_s * profile.stance_frac  # 0.360 s
delta_s        = profile.si_stance_true_pct * stance_nom_s / 200.0  # 0.045 s

stance_nom_ms  = stance_nom_s   * 1000.0   # 360 ms
delta_ms       = delta_s        * 1000.0   # 45  ms
odd_expected   = (stance_nom_s + delta_s)  * 1000.0   # 405 ms
even_expected  = (stance_nom_s - delta_s)  * 1000.0   # 315 ms

n_steps = 100
step_indices  = np.arange(n_steps)
stance_dur_ms = np.zeros(n_steps)

for i in range(n_steps):
    sign      = +1 if (i % 2 == 1) else -1
    noise     = rng_timing.normal(0, profile.step_variability_ms / 1000.0)
    stance_s  = stance_nom_s + sign * delta_s + noise
    stance_s  = max(stance_s, 0.10)
    stance_dur_ms[i] = stance_s * 1000.0
    # Consume swing noise too (to keep RNG state in sync with walker_model)
    _ = rng_timing.normal(0, profile.step_variability_ms * 0.5 / 1000.0)

# ─── Running SI estimate per step ────────────────────────────────────────────
# SI = 200 * |odd_stance - even_stance| / (odd_stance + even_stance)  per pair
running_si = np.full(n_steps, np.nan)
for i in range(1, n_steps):
    if i % 2 == 0:   # completed a pair (odd i-1, even i)
        t_odd  = stance_dur_ms[i - 1]   # step i-1 is odd (1-indexed parity)
        t_even = stance_dur_ms[i]
    else:             # completed a pair (even i-1, odd i)
        t_even = stance_dur_ms[i - 1]
        t_odd  = stance_dur_ms[i]
    si_val = 200.0 * abs(t_odd - t_even) / (t_odd + t_even)
    running_si[i] = si_val

# ─── Plot ─────────────────────────────────────────────────────────────────────
odd_mask  = (step_indices % 2 == 1)
even_mask = (step_indices % 2 == 0)

fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
fig.suptitle(
    "BUG-013 Judicial Evidence — High SI Walker: Stance Timing Diagnostic\n"
    "Walker 5: Pathological Asymmetry, Flat, True SI = 25%  |  seed=42, 100 steps",
    fontsize=13, fontweight="bold", y=0.98,
)

# ── Panel 1: Per-step stance duration ─────────────────────────────────────────
ax1 = axes[0]
ax1.scatter(step_indices[odd_mask],  stance_dur_ms[odd_mask],
            color="#e74c3c", s=40, zorder=5, label="Odd steps (affected limb)")
ax1.scatter(step_indices[even_mask], stance_dur_ms[even_mask],
            color="#3498db", s=40, zorder=5, label="Even steps (reference limb)")
ax1.plot(step_indices[odd_mask],  stance_dur_ms[odd_mask],
         color="#e74c3c", alpha=0.4, linewidth=1)
ax1.plot(step_indices[even_mask], stance_dur_ms[even_mask],
         color="#3498db", alpha=0.4, linewidth=1)

ax1.axhline(stance_nom_ms, color="black",   linestyle="--", linewidth=1.5,
            label=f"Nominal stance ({stance_nom_ms:.0f} ms)")
ax1.axhline(odd_expected,  color="#c0392b", linestyle=":",  linewidth=1.5,
            label=f"Expected odd ({odd_expected:.0f} ms)")
ax1.axhline(even_expected, color="#2980b9", linestyle=":",  linewidth=1.5,
            label=f"Expected even ({even_expected:.0f} ms)")

ax1.set_ylabel("Stance Duration (ms)", fontsize=11)
ax1.set_ylim(250, 470)
ax1.legend(loc="upper right", fontsize=9)
ax1.grid(True, alpha=0.3)
ax1.set_title("Panel 1: Per-Step Stance Duration", fontsize=11, loc="left")

# ── Panel 2: Running SI estimate per step ─────────────────────────────────────
ax2 = axes[1]
valid_mask = ~np.isnan(running_si)
ax2.plot(step_indices[valid_mask], running_si[valid_mask],
         color="#8e44ad", linewidth=2, marker="o", markersize=3, label="True SI estimate")
ax2.axhline(25.0, color="#2ecc71", linestyle="--", linewidth=2,
            label="True SI = 25% (ground truth)")
ax2.axhline(10.0, color="#e67e22", linestyle="-.", linewidth=2,
            label="Clinical threshold = 10%")
ax2.fill_between(step_indices[valid_mask], 10.0, running_si[valid_mask],
                 where=running_si[valid_mask] > 10.0,
                 alpha=0.15, color="#e74c3c", label="Above threshold region")
ax2.set_ylabel("Running SI Estimate (%)", fontsize=11)
ax2.set_ylim(0, 45)
ax2.legend(loc="upper right", fontsize=9)
ax2.grid(True, alpha=0.3)
ax2.set_title("Panel 2: Running SI Estimate per Step Pair", fontsize=11, loc="left")

# ── Panel 3: Firmware UART snapshots vs true SI ───────────────────────────────
ax3 = axes[2]

# True SI baseline (mean of running_si where valid)
true_si_mean = np.nanmean(running_si)
ax3.axhline(true_si_mean, color="#8e44ad", linestyle="--", linewidth=1.5,
            label=f"True SI mean = {true_si_mean:.1f}%")
ax3.axhline(25.0, color="#2ecc71", linestyle=":", linewidth=1.5,
            label="Ground truth SI = 25%")
ax3.axhline(10.0, color="#e67e22", linestyle="-.", linewidth=2,
            label="Clinical threshold = 10%")

# Firmware snapshots
ax3.step(fw_steps, fw_si, color="#e74c3c", linewidth=2.5, where="post",
         label="Firmware SI_stance% (UART)", zorder=5)
ax3.scatter(fw_steps, fw_si, color="#e74c3c", s=80, zorder=6, marker="D")

# Annotate each snapshot value
for sx, sv in zip(fw_steps, fw_si):
    ax3.annotate(f"{sv:.1f}%", (sx, sv),
                 textcoords="offset points", xytext=(0, 8),
                 fontsize=8, ha="center", color="#c0392b", fontweight="bold")

ax3.fill_between(fw_steps, 10.0, fw_si,
                 where=[v > 10.0 for v in fw_si],
                 alpha=0.15, color="#e74c3c")

ax3.set_ylabel("Firmware Reported SI_stance% (%)", fontsize=11)
ax3.set_xlabel("Step Number", fontsize=11)
ax3.set_ylim(0, 35)
ax3.legend(loc="upper right", fontsize=9)
ax3.grid(True, alpha=0.3)
ax3.set_title("Panel 3: Firmware UART Snapshots vs True SI", fontsize=11, loc="left")

# Shared x-axis formatting
for ax in axes:
    ax.set_xlim(-2, 102)
    ax.tick_params(axis="both", labelsize=10)

plt.tight_layout(rect=[0, 0, 1, 0.96])

out_path = "/Users/siyaoshao/gait_device/docs/executive_branch_document/plots/high_si_stance_timing.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
plt.close()

print(f"[ plotter ] Plot saved: {out_path}")
print(f"[ plotter ] True SI mean (running estimate) : {true_si_mean:.1f}%")
print(f"[ plotter ] Firmware final SI_stance reported: {fw_si[-1]:.1f}%")
print(f"[ plotter ] All {len(fw_si)} firmware snapshots above 10% threshold: "
      f"{'YES' if all(v > 10.0 for v in fw_si) else 'NO'}")
