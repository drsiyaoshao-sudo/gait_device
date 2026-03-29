"""
gyr_y terrain EMD diagnostic — all 4 walkers, phase-normalised.

Shows:
  Panel 1: Raw gyr_y (phase normalised) — all 4 walkers overlaid.
            Zero-crossing markers at the two key events:
              • Early rebound (phase ~0.10) — what the current detector uses on flat
              • Push-off onset  (phase ~0.75) — the only crossing available on stairs
  Panel 2: HP-filtered gyr_y (EMD terrain component removed).
            HP cutoff = 0.5 Hz (one-step period ~0.7 s → removes inter-step drift).
  Panel 3: acc_filt (HP 0.5 Hz → LP 15 Hz applied to |acc|) — same pipeline as
            step_detector.c.  Shows where the confirmation window opens (peak).
  Panel 4: Timing gap diagnostic.
            For each walker: measures elapsed time from acc_filt peak → push-off
            gyr_y zero-crossing.  GYR_CONFIRM_MS=40ms line plotted for reference.
            Separates the two confirmation modes:
              flat/slope/bad_wear: early crossing, gap < 40ms → PASS
              stairs: push-off crossing, gap >> 40ms → TIMEOUT

Saved to docs/executive_branch_document/plots/gyr_emd_terrain_comparison.png
"""

import sys
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "simulator"))
from walker_model import PROFILES, generate_imu_sequence

ODR = 208.0
DT  = 1.0 / ODR

# ── Filter helpers (mirrors step_detector.c) ─────────────────────────────────

def hp_filter(sig, fc_hz=0.5):
    rc    = 1.0 / (2.0 * math.pi * fc_hz)
    alpha = rc / (rc + DT)
    out   = np.zeros_like(sig)
    out[0] = sig[0]
    for i in range(1, len(sig)):
        out[i] = alpha * (out[i-1] + sig[i] - sig[i-1])
    return out

def lp_filter(sig, fc_hz=15.0):
    rc    = 1.0 / (2.0 * math.pi * fc_hz)
    alpha = DT / (rc + DT)
    out   = np.zeros_like(sig)
    out[0] = sig[0]
    for i in range(1, len(sig)):
        out[i] = alpha * sig[i] + (1.0 - alpha) * out[i-1]
    return out

def acc_filt_pipeline(samples):
    """acc_mag → HP 0.5 Hz → LP 15 Hz  (same as step_detector.c SD_FALLING pipeline)."""
    ax, ay, az = samples[:, 0], samples[:, 1], samples[:, 2]
    mag = np.sqrt(ax**2 + ay**2 + az**2)
    return lp_filter(hp_filter(mag))

def gyr_hp(samples):
    """gyr_y → HP 0.5 Hz  (EMD terrain-component removal)."""
    return hp_filter(samples[:, 4])

# ── Phase-normalise one step segment → N_PHASE points ────────────────────────

N_PHASE = 1000   # points per normalised step

def phase_normalise(seg):
    """Resample seg to N_PHASE points (phase 0→1)."""
    t_old = np.linspace(0, 1, len(seg))
    t_new = np.linspace(0, 1, N_PHASE)
    return np.interp(t_new, t_old, seg)

# ── Extract 3 clean steps from generated sequence ────────────────────────────

def extract_steps(profile, n_extract=3, seed=42):
    """
    Returns list of per-step arrays (gyr_y_raw, gyr_y_hp, acc_filt),
    each phase-normalised to N_PHASE points.
    """
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_extract + 2, rng=rng)

    # Step duration in samples (nominal)
    step_dur_s   = 60.0 / profile.cadence_spm
    step_n       = int(step_dur_s * ODR)
    prefix_n     = int(ODR)   # 1-s stationary prefix

    af = acc_filt_pipeline(samples)
    gh = gyr_hp(samples)
    gy = samples[:, 4]

    steps = []
    for k in range(n_extract):
        start = prefix_n + k * step_n
        end   = start + step_n
        if end > len(samples):
            break
        steps.append({
            "gyr_raw": phase_normalise(gy[start:end]),
            "gyr_hp":  phase_normalise(gh[start:end]),
            "acc_filt": phase_normalise(af[start:end]),
        })
    return steps

# ── Timing diagnostics (absolute ms, one representative step) ────────────────

def timing_diagnostic(profile, seed=42):
    """
    Returns dict with timing info for one representative step (step index 2).
    Keys: acc_peak_phase, gyr_early_zx_phase, gyr_pushoff_zx_phase,
          gap_early_ms, gap_pushoff_ms
    """
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, 5, rng=rng)

    step_dur_s = 60.0 / profile.cadence_spm
    step_n     = int(step_dur_s * ODR)
    prefix_n   = int(ODR)

    k     = 2   # third step (skip warmup)
    start = prefix_n + k * step_n
    end   = start + step_n

    af = acc_filt_pipeline(samples)[start:end]
    gy = samples[start:end, 4]
    gh = gyr_hp(samples)[start:end]

    phases = np.linspace(0, 1, len(af))

    # acc_filt peak phase
    acc_peak_idx   = np.argmax(af)
    acc_peak_phase = phases[acc_peak_idx]

    # gyr_y sign at peak (determines which crossing direction to hunt)
    sign_at_peak = np.sign(gy[acc_peak_idx])

    # Early zero-crossing (first crossing from neg to pos after step start)
    early_zx = None
    for i in range(1, len(gy)):
        if gy[i-1] < 0 and gy[i] >= 0:
            early_zx = phases[i]
            break

    # Push-off zero-crossing (neg→pos crossing AFTER acc_filt peak)
    pushoff_zx = None
    for i in range(acc_peak_idx + 1, len(gy)):
        if gy[i-1] < 0 and gy[i] >= 0:
            pushoff_zx = phases[i]
            break

    step_dur_ms = step_dur_s * 1000.0

    gap_early_ms   = abs(acc_peak_phase - (early_zx or 0)) * step_dur_ms
    gap_pushoff_ms = abs((pushoff_zx or 1.0) - acc_peak_phase) * step_dur_ms

    return {
        "acc_peak_phase":    acc_peak_phase,
        "early_zx_phase":    early_zx,
        "pushoff_zx_phase":  pushoff_zx,
        "gap_early_ms":      gap_early_ms,
        "gap_pushoff_ms":    gap_pushoff_ms,
        "step_dur_ms":       step_dur_ms,
    }

# ── Plotting ──────────────────────────────────────────────────────────────────

WALKER_ORDER  = ["flat", "bad_wear", "slope", "stairs"]
COLORS        = {"flat": "#2196F3", "bad_wear": "#FF9800", "slope": "#4CAF50", "stairs": "#F44336"}
LABELS        = {"flat": "Flat", "bad_wear": "Bad wear", "slope": "Slope (10°)", "stairs": "Stairs"}

phase_ax = np.linspace(0, 1, N_PHASE)

fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=False)
fig.suptitle(
    "gyr_y EMD Terrain Analysis — All 4 Walkers\n"
    "Phase-normalised (0 = heel/toe strike, 1 = next strike)\n"
    "Objective: identify a gyr_y feature that co-occurs with acc_filt peak across all terrains",
    fontsize=13, y=0.98
)

# ─── Panel 1: Raw gyr_y ──────────────────────────────────────────────────────
ax1 = axes[0]
ax1.set_title("Panel 1 — Raw gyr_y  (3-step mean ± shading)", fontsize=11)
ax1.axhline(0, color="black", linewidth=0.8, linestyle="--")
ax1.axhline(-10, color="purple", linewidth=0.8, linestyle=":", label="MID→TERM gate (−10 dps)")
ax1.axvline(0.10, color="grey", linewidth=0.8, linestyle=":", alpha=0.6)
ax1.axvline(0.75, color="grey", linewidth=0.8, linestyle=":", alpha=0.6)
ax1.text(0.105, -5, "phase 0.10\n(early zx)", fontsize=7, color="grey")
ax1.text(0.755, -5, "phase 0.75\n(push-off onset)", fontsize=7, color="grey")

for key in WALKER_ORDER:
    steps = extract_steps(PROFILES[key])
    mat   = np.stack([s["gyr_raw"] for s in steps])  # (3, N_PHASE)
    mean  = mat.mean(0)
    std   = mat.std(0)
    ax1.plot(phase_ax, mean, color=COLORS[key], label=LABELS[key], linewidth=2)
    ax1.fill_between(phase_ax, mean - std, mean + std, color=COLORS[key], alpha=0.15)

ax1.set_ylabel("gyr_y (dps)")
ax1.set_xlim(0, 1)
ax1.legend(loc="upper left", fontsize=9)
ax1.grid(True, alpha=0.3)

# ─── Panel 2: HP-filtered gyr_y ──────────────────────────────────────────────
ax2 = axes[1]
ax2.set_title("Panel 2 — HP-filtered gyr_y (0.5 Hz cutoff) — Terrain drift removed (EMD approximation)", fontsize=11)
ax2.axhline(0, color="black", linewidth=0.8, linestyle="--")
ax2.axvline(0.10, color="grey", linewidth=0.8, linestyle=":", alpha=0.6)
ax2.axvline(0.75, color="grey", linewidth=0.8, linestyle=":", alpha=0.6)

for key in WALKER_ORDER:
    steps = extract_steps(PROFILES[key])
    mat   = np.stack([s["gyr_hp"] for s in steps])
    mean  = mat.mean(0)
    std   = mat.std(0)
    ax2.plot(phase_ax, mean, color=COLORS[key], label=LABELS[key], linewidth=2)
    ax2.fill_between(phase_ax, mean - std, mean + std, color=COLORS[key], alpha=0.15)

ax2.set_ylabel("gyr_y HP (dps)")
ax2.set_xlim(0, 1)
ax2.legend(loc="upper left", fontsize=9)
ax2.grid(True, alpha=0.3)

# ─── Panel 3: acc_filt ───────────────────────────────────────────────────────
ax3 = axes[2]
ax3.set_title("Panel 3 — acc_filt (HP 0.5 Hz → LP 15 Hz) — Confirmation window opens at peak", fontsize=11)
ax3.axhline(5.0, color="red", linewidth=0.9, linestyle="--", label="Initial threshold (5 m/s²)")

diag_all = {}
for key in WALKER_ORDER:
    steps = extract_steps(PROFILES[key])
    mat   = np.stack([s["acc_filt"] for s in steps])
    mean  = mat.mean(0)
    std   = mat.std(0)
    ax3.plot(phase_ax, mean, color=COLORS[key], label=LABELS[key], linewidth=2)
    ax3.fill_between(phase_ax, mean - std, mean + std, color=COLORS[key], alpha=0.15)

    d = timing_diagnostic(PROFILES[key])
    diag_all[key] = d
    ax3.axvline(d["acc_peak_phase"], color=COLORS[key], linewidth=1.2, linestyle="--", alpha=0.7)

ax3.set_ylabel("acc_filt (m/s²)")
ax3.set_xlim(0, 1)
ax3.legend(loc="upper right", fontsize=9)
ax3.grid(True, alpha=0.3)

# ─── Panel 4: Timing gap bar chart ───────────────────────────────────────────
ax4 = axes[3]
ax4.set_title(
    "Panel 4 — Temporal gap: acc_filt peak → push-off gyr_y zero-crossing\n"
    "Current GYR_CONFIRM_MS = 40 ms  |  gap > 40ms → step rejected",
    fontsize=11
)

bar_labels = [LABELS[k] for k in WALKER_ORDER]
gaps       = []
early_gaps = []
for key in WALKER_ORDER:
    d = diag_all[key]
    gaps.append(d["gap_pushoff_ms"])
    early_gaps.append(d["gap_early_ms"])
    print(f"{key:12s}  acc_peak={d['acc_peak_phase']:.3f}  "
          f"early_zx={d['early_zx_phase'] or 0:.3f}  "
          f"pushoff_zx={d['pushoff_zx_phase'] or 0:.3f}  "
          f"gap_early={d['gap_early_ms']:.0f}ms  "
          f"gap_pushoff={d['gap_pushoff_ms']:.0f}ms")

x     = np.arange(len(WALKER_ORDER))
w     = 0.35
bars1 = ax4.bar(x - w/2, early_gaps, w,
                color=[COLORS[k] for k in WALKER_ORDER], alpha=0.5,
                label="Gap: acc_peak ↔ early zx (phase 0.10)")
bars2 = ax4.bar(x + w/2, gaps, w,
                color=[COLORS[k] for k in WALKER_ORDER], alpha=0.9,
                label="Gap: acc_peak → push-off zx (phase 0.75+)")

ax4.axhline(40, color="red", linewidth=1.5, linestyle="--", label="GYR_CONFIRM_MS = 40 ms")
ax4.set_xticks(x)
ax4.set_xticklabels(bar_labels, fontsize=11)
ax4.set_ylabel("Time gap (ms)")
ax4.set_xlabel("Walker profile")
ax4.legend(fontsize=9)
ax4.grid(True, axis="y", alpha=0.3)

# Annotate bar values
for rect, val in zip(list(bars1) + list(bars2), early_gaps + gaps):
    ax4.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 3,
             f"{val:.0f}ms", ha="center", va="bottom", fontsize=9)

# Colour verdict text
for i, key in enumerate(WALKER_ORDER):
    verdict = "PASS" if early_gaps[i] < 40 else "FAIL"
    color   = "green" if verdict == "PASS" else "red"
    ax4.text(i - w/2, -25, verdict, ha="center", fontsize=9,
             color=color, fontweight="bold",
             transform=ax4.get_xaxis_transform())

ax4.set_ylim(bottom=0)

plt.tight_layout(rect=[0, 0, 1, 0.96])
out_path = "docs/executive_branch_document/plots/gyr_emd_terrain_comparison.png"
plt.savefig(out_path, dpi=150)
print(f"\nSaved → {out_path}")
