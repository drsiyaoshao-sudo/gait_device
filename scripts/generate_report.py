"""
Full work report — Gait Device Simulation Bench to Option C Validation.
Generates a multi-page PDF with embedded plots and narrative text.

Output: docs/executive_branch_document/reports/gait_simulation_report_2026-03-27.pdf
"""

import sys, math, textwrap
from pathlib import Path
from datetime import date
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Patch
import matplotlib.image as mpimg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))
from walker_model import PROFILES, generate_imu_sequence
from terrain_aware_step_detector import TerrainAwareStepDetector, ODR_HZ

Path("docs/executive_branch_document/reports").mkdir(parents=True, exist_ok=True)

PLOT_DIR  = Path("docs/executive_branch_document/plots")
OUT_PDF   = Path("docs/executive_branch_document/reports/gait_simulation_report_2026-03-27.pdf")

# ── Colour palette ────────────────────────────────────────────────────────────
C_BLUE   = "#1565C0"
C_GREEN  = "#2E7D32"
C_RED    = "#C62828"
C_ORANGE = "#E65100"
C_GREY   = "#455A64"
C_LIGHT  = "#ECEFF1"
C_ACCENT = "#0288D1"

# ── Text helpers ──────────────────────────────────────────────────────────────

def wrap(text, width=100):
    return "\n".join(textwrap.wrap(text, width))

def heading(ax, text, y=0.97, size=14, color=C_BLUE, weight="bold"):
    ax.text(0.0, y, text, transform=ax.transAxes,
            fontsize=size, fontweight=weight, color=color, va="top")

def body(ax, text, y=0.90, size=9.5, color="#212121", linespacing=1.55):
    ax.text(0.0, y, text, transform=ax.transAxes,
            fontsize=size, color=color, va="top",
            linespacing=linespacing, wrap=False)

def hline(ax, y=0.96, color=C_BLUE, lw=1.5):
    ax.plot([0, 1], [y, y], color=color, linewidth=lw,
            transform=ax.transAxes, clip_on=False)

def text_page(fig, title, sections):
    """Single full-page text layout. sections = [(heading_str, body_str), ...]"""
    ax = fig.add_axes([0.08, 0.06, 0.84, 0.88])
    ax.axis("off")
    y = 0.99
    ax.text(0.0, y, title, transform=ax.transAxes,
            fontsize=13, fontweight="bold", color=C_BLUE, va="top")
    y -= 0.03
    ax.plot([0, 1], [y, y], color=C_BLUE, linewidth=1.5,
            transform=ax.transAxes, clip_on=False)
    y -= 0.03
    for sec_title, sec_body in sections:
        if y < 0.04:
            break
        ax.text(0.0, y, sec_title, transform=ax.transAxes,
                fontsize=10.5, fontweight="bold", color=C_GREY, va="top")
        y -= 0.025
        for line in sec_body.split("\n"):
            ax.text(0.015, y, line, transform=ax.transAxes,
                    fontsize=9, color="#212121", va="top")
            y -= 0.022
        y -= 0.012


def embed_image(ax, path, title=None):
    """Embed a PNG into an axes."""
    try:
        img = mpimg.imread(str(path))
        ax.imshow(img, aspect="auto")
        ax.axis("off")
        if title:
            ax.set_title(title, fontsize=9, color=C_GREY, pad=4)
    except Exception as e:
        ax.axis("off")
        ax.text(0.5, 0.5, f"[image not found: {path.name}]",
                ha="center", va="center", fontsize=9, color="red",
                transform=ax.transAxes)


# ══════════════════════════════════════════════════════════════════════════════
#  PDF ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

with PdfPages(OUT_PDF) as pdf:

    # ── PAGE 1: TITLE PAGE ────────────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    ax  = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_facecolor(C_BLUE)
    ax.axis("off")

    # White title block
    fig.text(0.5, 0.72, "Gait Symmetry Device",
             ha="center", fontsize=28, fontweight="bold", color="white")
    fig.text(0.5, 0.63, "Simulation Bench to Algorithm Validation",
             ha="center", fontsize=18, color="#BBDEFB")
    fig.text(0.5, 0.55, "Full Work Report",
             ha="center", fontsize=15, color="#90CAF9")

    fig.text(0.5, 0.42,
             "Stair Walker Failure Mode (BUG-010) — Root Cause Analysis,\n"
             "Terrain-Aware Algorithm Design, and Option C Heel-Strike\n"
             "Ring-Buffer Validation",
             ha="center", fontsize=11, color="white", linespacing=1.7)

    fig.text(0.5, 0.24, "2026-03-27", ha="center", fontsize=12, color="#BBDEFB")
    fig.text(0.5, 0.19, "Stage 2 — Python Signal-Level Validation Complete",
             ha="center", fontsize=11, color="#90CAF9")
    fig.text(0.5, 0.13,
             "Platform: XIAO nRF52840 Sense  ·  IMU: LSM6DS3TR-C  ·  ODR: 208 Hz\n"
             "Pipeline: walker_model → imu_model → Renode nRF52840 → UART → signal_analysis",
             ha="center", fontsize=9, color="#B0BEC5", linespacing=1.7)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 2: EXECUTIVE SUMMARY ─────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    text_page(fig, "Executive Summary", [
        ("Objective",
         "Demonstrate that a 7-layer Physics-Native Digital Twin can capture the 'Stair Walker'\n"
         "step-detection failure mode entirely in simulation — before any PCB fabrication or\n"
         "hardware prototype — and validate the algorithmic fix at the Python signal level."),

        ("Failure Mode Captured (BUG-010)",
         "The standard gait algorithm (step_detector.c) detects 0/100 steps on stair climbing.\n"
         "Root cause: a dual-confirmation timing mismatch. The algorithm requires an acc_filt\n"
         "threshold crossing AND a gyr_y zero-crossing within 40 ms. On stairs (forefoot strike),\n"
         "the gyr_y crosses at 53 ms while acc_filt peaks 188 ms later — a 135 ms gap that\n"
         "permanently exceeds the 40 ms window. 427 acc peaks fire and time out per 100 steps."),

        ("Algorithm Fix — Terrain-Aware Step Detector",
         "Inverted the confirmation logic: gyr_y_hp push-off burst (neg→pos, >30 dps) becomes\n"
         "the primary trigger; acc_filt threshold exceeded at any point since last step serves\n"
         "as confirmation. Push-off is biomechanically universal — no terrain allows walking\n"
         "without plantar-flexion. The confirmation window expands from 40 ms to the full step\n"
         "period. 10/10 unit tests pass. Stairs: 0 → 100 steps. SI < 3% on all 4 profiles."),

        ("Option C — Ring-Buffer Heel-Strike Inference",
         "Direct C port of the push-off detector would corrupt phase_segmenter.c output:\n"
         "stance duration would be reported as the full step period (+295 ms error on stairs).\n"
         "Option C: an 8-entry ring buffer (~32 bytes RAM) stores rejected acc_filt crossing\n"
         "timestamps since the last confirmed step. On push-off, the oldest entry is used as\n"
         "the retrospective heel-strike — no event contract change. Measured stance error:\n"
         "−18 ms (flat/bad_wear), −21 ms (slope), −35 ms (stairs). All within ±150 ms tolerance."),

        ("Status",
         "Python validation complete. 18/18 tests pass. 7 diagnostic plots generated.\n"
         "Awaiting human sign-off on Option C plots before porting to step_detector.c."),
    ])
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 3: SIMULATION BENCH ARCHITECTURE ─────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    text_page(fig, "1. Simulation Bench Architecture — 7-Layer Digital Twin", [
        ("Design Principle",
         "Never inject raw sensor readings. Inject first-order measurable walking pattern\n"
         "quantities (vertical oscillation, cadence, step length). All signal shape parameters\n"
         "are derived from these three primitives — no magic numbers."),

        ("Layer Stack",
         "Layer 1  walker_model.py         WalkerProfile → (N,6) float32 [ax ay az gx gy gz]\n"
         "                                  Biomechanics from 3 primitives: vert_osc, cadence, step_length\n"
         "Layer 2  imu_model.py             Quantize to LSM6DS3TR-C register format\n"
         "                                  Accel ±16g @ 0.488 mg/LSB  ·  Gyro ±2000 dps @ 70 mdps/LSB\n"
         "Layer 3  lsm6ds3_stub.py          I2C register protocol, 32-sample FIFO watermark\n"
         "Layer 4  Renode 1.16.1            nRF52840 Cortex-M4F — actual firmware ELF\n"
         "Layer 5  signal_analysis.py       UART → typed Python event objects\n"
         "Layer 6  BLE bypass (UART export) Binary rolling_snapshot_t structs over UART\n"
         "Layer 7  app.py                   Streamlit display only — no computation"),

        ("Four Walker Profiles",
         "flat      80 spm, vert_osc=3 cm, step_length=0.75 m  — baseline reference\n"
         "bad_wear  80 spm, vert_osc=3 cm, step_length=0.75 m  — worn sole (signal morphology change)\n"
         "slope     78 spm, vert_osc=3 cm, step_length=0.72 m  — 10° incline (DC gravity offset)\n"
         "stairs    70 spm, vert_osc=6 cm, step_length=0.45 m  — forefoot strike (FAILURE MODE)"),

        ("Three Primitive Derivation Chain",
         "vertical_oscillation + cadence  →  heel strike impact magnitude, acc_z modulation depth\n"
         "step_length + cadence           →  walking speed → push-off angular velocity (gyr_y peak)\n"
         "terrain_slope_deg               →  DC gravity offset on acc_x / acc_z (not oscillation)\n"
         "terrain_type                    →  signal morphology (sinusoidal vs non-sinusoidal)"),

        ("Enforcement",
         "Layer boundaries are strictly enforced. Each layer owns exactly one transformation.\n"
         "Algorithm execution lives in Renode (real C firmware). Python is signal generation\n"
         "and parsing only — it never simulates algorithm logic except in Stage 2 mirrors."),
    ])
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 4: STAIR WALKER SIGNAL DIAGNOSTIC ────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.suptitle("2. Stair Walker Failure Mode — Signal Diagnostic",
                 fontsize=13, fontweight="bold", color=C_BLUE, y=0.97)

    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[2.2, 1], hspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.05)

    ax_img = fig.add_subplot(gs[0])
    embed_image(ax_img, PLOT_DIR / "stair_walker_signal_check.png",
                "Figure 1 — Stair walker raw signal: acc_filt peak at phase 0.164 (141 ms), "
                "gyr_y crossing at phase 0.017 (14 ms) — 126 ms gap exceeds 40 ms gate")

    ax_txt = fig.add_subplot(gs[1])
    ax_txt.axis("off")
    heading(ax_txt, "Key Measurements", y=0.98, size=10)
    hline(ax_txt, y=0.94, lw=1)
    body(ax_txt, (
        "Signal amplitude is NOT the problem — acc_filt peaks at 7.44 m/s² on stairs (above 5.0 m/s² threshold).\n"
        "427 acc peaks fire and time out per 100 steps. 0 steps confirmed.\n\n"
        "  Event                    Flat walker      Stair walker\n"
        "  ─────────────────────────────────────────────────────\n"
        "  acc_filt peak phase      0.026 (15 ms)    0.164 (141 ms)\n"
        "  gyr_y zero-crossing      0.017 (10 ms)    0.017  (14 ms)\n"
        "  Temporal gap             19 ms → PASS     126 ms → TIMEOUT\n\n"
        "Root cause: forefoot/midfoot contact pre-dorsiflexes the foot. gyr_y crosses zero immediately\n"
        "at contact; acc_filt builds slowly (sigmoid loading) and peaks 126 ms after the window closed."
    ), y=0.89, size=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 5: EMD TERRAIN COMPARISON ────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.suptitle("3. Algorithm Hunting — EMD Signal Observation",
                 fontsize=13, fontweight="bold", color=C_BLUE, y=0.97)

    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[2.2, 1], hspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.05)

    ax_img = fig.add_subplot(gs[0])
    embed_image(ax_img, PLOT_DIR / "gyr_emd_terrain_comparison.png",
                "Figure 2 — EMD terrain comparison: HP-filtered gyr_y (Panel 2) shows consistent "
                "width across all 4 profiles — human confirmed 'consistent width is a good sign'")

    ax_txt = fig.add_subplot(gs[1])
    ax_txt.axis("off")
    heading(ax_txt, "EMD Framing and Algorithm Inversion Hypothesis", y=0.98, size=10)
    hline(ax_txt, y=0.94, lw=1)
    body(ax_txt, (
        "Empirical Mode Decomposition reveals two separable modes in raw gyr_y:\n"
        "  IMF1  step-cycle oscillation: dorsiflexion → push-off  (HP filter at 0.5 Hz approximates extraction)\n"
        "  IMF2  terrain posture drift:  slow inter-step variation (removed by HP filter)\n\n"
        "Human observation (Panel 2): 'the width of the signals are pretty consistent — this is a good sign.'\n"
        "The push-off zero-crossing of IMF1 occurs at consistent phase (~0.75) regardless of terrain.\n\n"
        "Algorithm inversion hypothesis:\n"
        "  OLD (acc-primary):  acc_filt threshold → open 40 ms window → wait for gyr_y zero-crossing\n"
        "  NEW (gyr-primary):  gyr_y_hp push-off event → verify acc_filt exceeded threshold since last step\n\n"
        "Push-off is universal — no terrain allows walking without plantar-flexion. The confirmation window\n"
        "expands from 40 ms to the full step period. Terrain-agnostic by construction."
    ), y=0.89, size=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 6: PUSH-OFF AMPLITUDE THRESHOLD DERIVATION ──────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    text_page(fig, "4. Push-Off Amplitude Threshold — Physical Derivation", [
        ("Feature Selection Problem",
         "Two candidate gyr_y_hp events could trigger step detection:\n"
         "  (a) Phase-0.10 rebound — small positive peak immediately after initial dorsiflexion\n"
         "  (b) Phase-0.75 push-off burst — full plantar-flexion at stance end\n\n"
         "Zero-crossing approach rejected: swing phase from previous step extends the 'negative duration'\n"
         "to ~355 ms on stairs (vs ~80 ms on flat), making duration-based gates terrain-coupled."),

        ("Amplitude Ratio — 20× Separation",
         "                          Phase-0.10 rebound     Phase-0.75 push-off\n"
         "  Flat walker (185 dps)   +9.3 dps (×0.05)       +185 dps (×1.0)\n"
         "  Stair walker (280 dps)  +14.0 dps (×0.05)      +280 dps (×1.0)\n"
         "  Ratio                   1×                      20×\n\n"
         "The rebound peaks at ~5% of the push-off peak amplitude across all terrains."),

        ("Threshold Choice — GYR_PUSHOFF_THRESH_DPS = 30 dps",
         "Physical grounding:\n"
         "  Minimum push-off velocity: 100 + 65 × v_min = 106 dps  at v = 0.1 m/s → well above 30 dps\n"
         "  Phase-0.10 rebound: 9–14 dps across all profiles          → always BELOW 30 dps → blocked ✓\n"
         "  Push-off burst:  185–280 dps across all profiles          → always ABOVE 30 dps → detected ✓\n\n"
         "Detection gate (falling edge of push-off burst):\n"
         "  gyr_y_hp was > 30 dps (push-off entry confirmed)\n"
         "  gyr_y_hp drops ≤ 30 dps (falling edge — push-off complete)\n"
         "  acc_filt > adaptive_threshold at any point since last step\n"
         "  elapsed since last step ≥ 250 ms (240 spm max cadence)"),

        ("Filter Chain (identical to step_detector.c)",
         "  acc_mag → HP(0.5 Hz) → LP(15 Hz walk / 30 Hz run)  =  acc_filt\n"
         "  gyr_y   → HP(0.5 Hz)                                =  gyr_y_hp\n\n"
         "HP at 0.5 Hz removes inter-step posture drift (terrain DC component).\n"
         "LP at 15/30 Hz anti-aliases while preserving impact transients.\n"
         "Adaptive threshold: 50% of 8-step peak history, seeded at 10 m/s².\n"
         "All coefficients identical to existing firmware — no filter retuning required."),
    ])
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 7: SI COMPARISON PLOT ────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.suptitle("5. Python Validation — Standard vs Terrain-Aware Step Detector",
                 fontsize=13, fontweight="bold", color=C_BLUE, y=0.97)

    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[2.4, 1], hspace=0.30,
                           left=0.06, right=0.96, top=0.92, bottom=0.05)

    ax_img = fig.add_subplot(gs[0])
    embed_image(ax_img, PLOT_DIR / "si_comparison_standard_vs_terrain.png",
                "Figure 3 — Step count (left) and SI (right): standard vs terrain-aware. "
                "Stairs: 0 → 100 steps. SI < 3% on all 4 profiles.")

    ax_txt = fig.add_subplot(gs[1])
    ax_txt.axis("off")
    heading(ax_txt, "Validation Results", y=0.98, size=10)
    hline(ax_txt, y=0.94, lw=1)
    body(ax_txt, (
        "Baseline confirmed first: standard Python pipeline (mirrors step_detector.c) on stairs → 0 steps, 427 timeouts.\n\n"
        "  Profile       Standard steps   Terrain-aware steps   Standard SI%   Terrain-aware SI%\n"
        "  ─────────────────────────────────────────────────────────────────────────────────────\n"
        "  Flat                100                 100              0.02%             0.09%\n"
        "  Bad wear            100                 100              0.02%             0.09%\n"
        "  Slope (10°)         100                 100              0.82%             1.24%\n"
        "  Stairs                0                 100              n/a               0.69%\n\n"
        "Terrain-aware SI slightly higher than standard on flat/slope — expected: push-off timestamps the end\n"
        "of stance (not start), introducing a consistent offset that cancels in the interval SI computation."
    ), y=0.89, size=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 8: ARCHITECTURAL FINDING ─────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.suptitle("6. Critical Architectural Finding — Phase Segmenter Contract",
                 fontsize=13, fontweight="bold", color=C_BLUE, y=0.97)

    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[2.2, 1], hspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.05)

    ax_img = fig.add_subplot(gs[0])
    embed_image(ax_img, PLOT_DIR / "swing_stance_comparison.png",
                "Figure 4 — Swing/stance architectural impact. "
                "Without Option C, on_heel_strike() fires at push-off: "
                "computed stance = full step period (+295 ms error on stairs).")

    ax_txt = fig.add_subplot(gs[1])
    ax_txt.axis("off")
    heading(ax_txt, "The Problem and Three Options", y=0.98, size=10)
    hline(ax_txt, y=0.94, lw=1)
    body(ax_txt, (
        "phase_segmenter.c uses on_heel_strike() as its clock. Standard detector fires at heel-strike (start of stance).\n"
        "Terrain-aware fires at push-off (end of stance). Direct C swap silently corrupts all stance/swing output:\n\n"
        "  Profile    GT stance    GT swing    Computed 'stance' if TA used    Error\n"
        "  ─────────────────────────────────────────────────────────────────────────\n"
        "  Flat         343 ms      229 ms            567 ms                  +224 ms (+65%)\n"
        "  Stairs        557 ms     300 ms            852 ms                  +295 ms (+53%)\n\n"
        "Option A: Two-event architecture (heel_strike + push_off). Medium complexity.\n"
        "Option B: Terrain classifier disables phase segmenter on stairs. Medium complexity.\n"
        "Option C: Ring buffer of rejected acc_filt timestamps → retrospective heel-strike. LOW complexity. ← SELECTED"
    ), y=0.89, size=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 9: OPTION C RATIONALE ────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    text_page(fig, "7. Option C — Ring-Buffer Heel-Strike Inference: Design and Rationale", [
        ("Core Insight",
         "The standard detector already computes 427 rejected acc_filt crossings for 100 stair steps.\n"
         "The timestamps exist — they are simply not stored. A ring buffer of 8 entries (~32 bytes RAM)\n"
         "captures the most recent threshold crossings since the last confirmed step. On push-off,\n"
         "the oldest ring entry newer than last_step_ts is used as the retrospective heel-strike."),

        ("Implementation",
         "New state: _hs_ring (list of float, max HS_RING_SIZE=8) + _acc_was_below (bool)\n\n"
         "Each sample: if acc_filt crosses below→above threshold, append ts_ms to ring (cap at 8).\n"
         "             if acc_filt drops below threshold, set _acc_was_below = True.\n\n"
         "On push-off: iterate _hs_ring in chronological order,\n"
         "             find first entry > last_step_ts_ms → heel_strike_ts\n"
         "             stance_duration_ms = push_off_ts − heel_strike_ts\n"
         "             swing_duration_ms of previous step = heel_strike_ts − prev.ts_ms\n"
         "             clear _hs_ring after confirmed step."),

        ("Why It Preserves the on_heel_strike() Contract",
         "phase_segmenter.c receives heel_strike_ts from the ring buffer — a timestamp that is\n"
         "physically early in stance (first acc_filt loading crossing), not at push-off.\n"
         "The contract on_heel_strike(ts) → PHASE_LOADING is preserved semantically.\n"
         "No new event types. No terrain classifier. No BOM change."),

        ("Accuracy Expectation vs Actual",
         "Predicted: −50 to −100 ms error on stairs (conservative HP+LP filter rise estimate).\n"
         "Actual:    −18 ms (flat/bad_wear), −21 ms (slope), −35 ms (stairs).\n\n"
         "Filter rise time is faster than predicted. The first acc_filt crossing arrives at\n"
         "~20–35 ms into true stance — not 50–100 ms. Option C exceeds its own design target.\n\n"
         "RAM cost: 8 × 4 bytes = 32 bytes. Zero firmware structural changes."),
    ])
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 10: OPTION C VALIDATION PLOTS (stance/swing) ─────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.suptitle("8. Option C Validation — Stance and Swing Accuracy",
                 fontsize=13, fontweight="bold", color=C_BLUE, y=0.97)

    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[2.2, 1], hspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.05)

    ax_img = fig.add_subplot(gs[0])
    embed_image(ax_img, PLOT_DIR / "option_c_stance_swing_accuracy.png",
                "Figure 5 — Option C stance/swing accuracy. "
                "Stairs stance error: −35 ms vs push-off-only +295 ms. All 4 profiles within tolerance.")

    ax_txt = fig.add_subplot(gs[1])
    ax_txt.axis("off")
    heading(ax_txt, "Measured Results vs Ground Truth", y=0.98, size=10)
    hline(ax_txt, y=0.94, lw=1)
    body(ax_txt, (
        "  Profile       GT stance   OC stance   Stance err   GT swing   OC swing   Swing err\n"
        "  ──────────────────────────────────────────────────────────────────────────────────\n"
        "  Flat            343 ms     324.6 ms     −18 ms       229 ms    242.0 ms    +13 ms\n"
        "  Bad wear        343 ms     324.6 ms     −18 ms       229 ms    242.0 ms    +13 ms\n"
        "  Slope (10°)     392 ms     370.8 ms     −21 ms       240 ms    252.9 ms    +13 ms\n"
        "  Stairs          557 ms     522.3 ms     −35 ms       300 ms    329.8 ms    +30 ms\n\n"
        "Stance undercount and swing overcount are complementary — the ring buffer heel-strike\n"
        "fires ~20–35 ms into actual stance, shifting the boundary consistently. Clinically\n"
        "acceptable: ±35 ms on stairs vs the +295 ms error without Option C."
    ), y=0.89, size=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 11: OPTION C SI COMPARISON ───────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.suptitle("9. Option C Final Comparison — Step Count and Symmetry Index",
                 fontsize=13, fontweight="bold", color=C_BLUE, y=0.97)

    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[2.2, 1], hspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.05)

    ax_img = fig.add_subplot(gs[0])
    embed_image(ax_img, PLOT_DIR / "option_c_si_comparison.png",
                "Figure 6 — Three-algorithm comparison: standard / Option C push-off SI / "
                "Option C heel-strike SI. All 4 profiles, 100 steps each.")

    ax_txt = fig.add_subplot(gs[1])
    ax_txt.axis("off")
    heading(ax_txt, "Final Algorithm Comparison", y=0.98, size=10)
    hline(ax_txt, y=0.94, lw=1)
    body(ax_txt, (
        "  Profile       Std steps   OC steps   Std SI%   OC push-off SI%   OC heel-strike SI%\n"
        "  ──────────────────────────────────────────────────────────────────────────────────\n"
        "  Flat               100        100      0.02%          0.09%              0.02%\n"
        "  Bad wear           100        100      0.02%          0.09%              0.02%\n"
        "  Slope (10°)        100        100      0.82%          1.24%              0.82%\n"
        "  Stairs               0        100      n/a            0.69%              0.40%\n\n"
        "The heel-strike SI (green bars) recovers to match standard algo values on flat/slope.\n"
        "This makes sense: ring buffer timestamps are consistent early-stance references, which\n"
        "is the same physical event the standard detector uses on flat terrain.\n"
        "18/18 tests pass. Python Stage 2 milestone complete."
    ), y=0.89, size=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 12: TEST SUMMARY ─────────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    text_page(fig, "10. Test Coverage Summary — 18/18 Pass", [
        ("Original Stage 2 Tests (10/10)",
         "test_step_count[flat-100-5]           PASS   100 steps detected, tolerance ±5\n"
         "test_step_count[bad_wear-100-5]        PASS   100 steps detected, tolerance ±5\n"
         "test_step_count[slope-100-5]           PASS   100 steps detected, tolerance ±5\n"
         "test_step_count[stairs-100-5]          PASS   100 steps detected (was 0) ← KEY FIX\n"
         "test_si_interval[flat-100]             PASS   SI = 0.09% < 3%\n"
         "test_si_interval[bad_wear-100]         PASS   SI = 0.09% < 3%\n"
         "test_si_interval[slope-100]            PASS   SI = 1.24% < 3%\n"
         "test_si_interval[stairs-100]           PASS   SI = 0.69% < 3% (was n/a)\n"
         "test_no_false_positives_stationary     PASS   0 steps on 5s stationary signal\n"
         "test_minimum_step_interval             PASS   No interval < 250 ms"),

        ("Option C Stance Tests (4/4)",
         "test_option_c_stance_duration[flat-343-80]     PASS   mean=324.6 ms, err=−18 ms, tol ±80 ms\n"
         "test_option_c_stance_duration[bad_wear-343-80] PASS   mean=324.6 ms, err=−18 ms, tol ±80 ms\n"
         "test_option_c_stance_duration[slope-392-80]    PASS   mean=370.8 ms, err=−21 ms, tol ±80 ms\n"
         "test_option_c_stance_duration[stairs-557-150]  PASS   mean=522.3 ms, err=−35 ms, tol ±150 ms"),

        ("Option C Swing Tests (4/4)",
         "test_option_c_swing_duration[flat-229-100]     PASS   mean=242.0 ms, err=+13 ms, tol ±100 ms\n"
         "test_option_c_swing_duration[bad_wear-229-100] PASS   mean=242.0 ms, err=+13 ms, tol ±100 ms\n"
         "test_option_c_swing_duration[slope-240-100]    PASS   mean=252.9 ms, err=+13 ms, tol ±100 ms\n"
         "test_option_c_swing_duration[stairs-300-150]   PASS   mean=329.8 ms, err=+30 ms, tol ±150 ms"),

        ("Key Test Properties",
         "Seed=42 for all walker runs — deterministic, reproducible.\n"
         "Warmup: first 4 steps excluded from SI and stance/swing measurement (filter settling).\n"
         "Swing: last step excluded (swing_duration_ms not backfilled until next push-off fires).\n"
         "Stationary test: 5 seconds × 208 Hz = 1040 samples, gravity + 10 mdps noise."),
    ])
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── PAGE 13: NEXT STEPS ───────────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    text_page(fig, "11. Next Steps — C Port and Renode Validation", [
        ("Stage 2 Status: COMPLETE (pending human sign-off on Option C plots)",
         "All Python signal-level exit criteria met.\n"
         "Human checkpoint: review docs/executive_branch_document/plots/option_c_stance_swing_accuracy.png\n"
         "                  review docs/executive_branch_document/plots/option_c_si_comparison.png\n"
         "Sign-off required before C port begins (per CLAUDE.md learner-in-the-loop protocol)."),

        ("C Port — src/gait/step_detector.c (Option C only, surgical change)",
         "1. Add constant:    #define HS_RING_SIZE 8\n"
         "2. Add ring buffer: float hs_ring[HS_RING_SIZE]; int hs_ring_head; int hs_ring_count;\n"
         "                    bool acc_was_below;\n"
         "3. Per-sample:      on acc_filt below→above crossing: push ts_ms into ring (oldest evicted)\n"
         "                    on acc_filt above→below: set acc_was_below = true\n"
         "4. On push-off:     find oldest ring entry > last_step_ts → heel_strike_ts\n"
         "                    emit on_heel_strike(heel_strike_ts) to phase_segmenter\n"
         "                    then emit step confirmed event as before\n"
         "                    clear ring\n"
         "No change to on_heel_strike() signature or phase_segmenter.c."),

        ("Stage 3 — Renode Validation (after C port)",
         "Rebuild firmware ELF:  pio run -e xiaoble_sense\n"
         "Run all 4 profiles through Renode: test_all_profiles.py\n"
         "Confirm stairs ≥ 95/100 steps and SI < 3% in bare-metal simulation\n"
         "Confirm phase segmenter stance/swing within ±20 ms of ground truth (all 4 profiles)\n"
         "Update memory/bugs.md — BUG-010 status: RESOLVED"),

        ("BOM Impact",
         "None. The ring buffer costs 32 bytes RAM and 8 comparisons per step confirmation.\n"
         "No additional sensors, no BOM changes, no firmware structural changes.\n"
         "Algorithm runs within existing XIAO nRF52840 Sense + LSM6DS3TR-C platform constraints."),

        ("Files Produced in This Work Session",
         "simulator/terrain_aware_step_detector.py     Python reference implementation\n"
         "simulator/tests/test_terrain_aware_detector.py  18-test validation suite\n"
         "scripts/run_standard_stairs.py               Baseline: 0 steps, 427 timeouts confirmed\n"
         "scripts/plot_gyr_terrain_emd.py              EMD signal comparison (4 walkers)\n"
         "scripts/plot_si_comparison.py                Standard vs terrain-aware SI\n"
         "scripts/plot_swing_stance_comparison.py      Architectural impact analysis\n"
         "scripts/plot_option_c_stance_swing.py        Option C stance/swing accuracy\n"
         "scripts/plot_option_c_si_comparison.py       Three-algorithm SI comparison\n"
         "docs/executive_branch_document/algorithm_hunting_stair_walker.md       Full hunting procedure + decisions\n"
         "docs/executive_branch_document/reports/gait_simulation_report_2026-03-27.pdf  This report"),
    ])
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # ── Set PDF metadata ──────────────────────────────────────────────────────
    d = pdf.infodict()
    d["Title"]   = "Gait Device — Simulation Bench to Option C Validation"
    d["Author"]  = "Gait Device Agentic CI/CD Pipeline"
    d["Subject"] = "BUG-010 Stair Walker Fix — Python Stage 2 Complete"
    d["Keywords"] = "gait symmetry, step detection, EMD, terrain-aware, Option C, nRF52840"
    d["CreationDate"] = "2026-03-27"

print(f"Report written → {OUT_PDF}  ({OUT_PDF.stat().st_size // 1024} KB)")
print(f"Pages: 13")
