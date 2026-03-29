#!/usr/bin/env python3
"""
Judicial Hearing Evidence: Step 2 Missing gyr_y Zero-Crossing Diagnostic

Bureaucracy Standing Order execution — Signal Plotting.
Generates a focused 2-panel diagnostic figure showing the missing gyr_y zero-crossing
on Step 2 of the stair walker profile, with explicit annotations and measurements.

Generated signals:
- Stair walker (healthy mode, seed=42)
- Time window: t=0.5s to t=3.5s (covers Steps 1–3)
- Filters applied:
  - acc_filt: 15 Hz low-pass Butterworth, 2nd order
  - gyr_y: raw (no filtering for zero-crossing detection)
"""

import sys
import math
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Add simulator to path
sys.path.insert(0, str(Path(__file__).parent / "simulator"))

from walker_model import generate_imu_sequence, PROFILES

# Constants
ODR_HZ = 208.0
G = 9.81

def design_filters():
    """Design the firmware-matched filters."""
    # 15 Hz low-pass for acc_z → acc_filt (2nd order Butterworth)
    sos_lp = butter(2, 15.0, btype='low', fs=ODR_HZ, output='sos')
    return sos_lp

def find_ground_contacts(acc_filt, window_ms=50):
    """
    Detect ground contact instants from acc_filt peaks.
    Returns indices where acc_filt reaches local maxima (ground contact peaks).
    """
    window_samples = int(window_ms * ODR_HZ / 1000.0)
    contacts = []
    i = 0
    while i < len(acc_filt):
        end = min(i + window_samples, len(acc_filt))
        if i == end:
            break
        peak_idx = i + np.argmax(acc_filt[i:end])
        contacts.append(peak_idx)
        i = peak_idx + window_samples
    return np.array(contacts, dtype=int)

def find_gyr_y_zerocross(gyr_y, contact_idx, window_ms=200):
    """
    Find the first gyr_y zero-crossing within window_ms after contact.
    Returns:
      - zerocross_idx: index of zero-crossing, or None if not found
      - zerocross_ms: time in ms, or None if not found
    """
    window_samples = int(window_ms * ODR_HZ / 1000.0)
    end_idx = min(contact_idx + window_samples, len(gyr_y) - 1)

    for i in range(contact_idx, end_idx):
        if gyr_y[i] * gyr_y[i + 1] < 0:  # sign change
            return i, (i / ODR_HZ) * 1000.0

    return None, None

def main():
    print("=" * 90)
    print("STEP 2 ZERO-CROSSING DIAGNOSTIC: Stair Walker Evidence for Judicial Hearing")
    print("=" * 90)
    print()

    # Design filter
    sos_lp = design_filters()
    print("[FILTER DESIGN]")
    print(f"  LP filter: 15 Hz, 2nd order Butterworth (acc_z → acc_filt)")
    print()

    # Generate stair walker IMU sequence
    print("[SIGNAL GENERATION]")
    stairs_profile = PROFILES['stairs']
    rng = np.random.default_rng(seed=42)
    stairs_imu = generate_imu_sequence(stairs_profile, n_steps=30, rng=rng)

    print(f"  Stairs walker: {len(stairs_imu)} samples ({stairs_imu.shape[0] / ODR_HZ:.1f}s)")
    print(f"  Cadence: {stairs_profile.cadence_spm} steps/min")
    print(f"  Step duration: {60000 / stairs_profile.cadence_spm:.1f} ms")
    print()

    # Extract raw signals
    acc_z = stairs_imu[:, 2]
    gyr_y = stairs_imu[:, 4]

    # Apply low-pass filter to acc_z
    acc_filt = sosfilt(sos_lp, acc_z)

    print("[FILTERING]")
    print(f"  acc_filt: min={acc_filt.min():.2f}, max={acc_filt.max():.2f} m/s²")
    print(f"  gyr_y: min={gyr_y.min():.1f}, max={gyr_y.max():.1f} dps")
    print()

    # Detect ground contacts
    print("[GROUND CONTACT DETECTION]")
    contacts = find_ground_contacts(acc_filt, window_ms=50)

    # Skip stationary prefix (1 second = 208 samples)
    stationary_samples = int(ODR_HZ)
    contacts = contacts[contacts > stationary_samples]

    print(f"  Total contacts detected: {len(contacts)}")
    print()

    # Analyze first 3 steps
    print("[STEP TIMING ANALYSIS — Steps 1–3]")
    print()

    step_data = []
    for i in range(min(3, len(contacts))):
        contact_idx = contacts[i]
        contact_ms = (contact_idx / ODR_HZ) * 1000.0

        # Get acc_filt peak in 200ms window after contact
        window_samples = int(200 * ODR_HZ / 1000.0)
        search_end = min(contact_idx + window_samples, len(acc_filt))
        peak_idx = contact_idx + np.argmax(acc_filt[contact_idx:search_end])
        peak_ms = (peak_idx / ODR_HZ) * 1000.0
        peak_value = acc_filt[peak_idx]

        # Find gyr_y zero-crossing within 200ms window
        zcross_idx, zcross_ms = find_gyr_y_zerocross(gyr_y, contact_idx, window_ms=200)

        step_data.append({
            'step': i + 1,
            'contact_idx': contact_idx,
            'contact_ms': contact_ms,
            'peak_idx': peak_idx,
            'peak_ms': peak_ms,
            'peak_value': peak_value,
            'zcross_idx': zcross_idx,
            'zcross_ms': zcross_ms,
        })

    # Print detailed table
    print(f"{'Step':<6} {'Contact (ms)':<15} {'Peak Time (ms)':<16} {'Peak Value':<14} {'Zero-Cross (ms)':<18} {'Status':<25}")
    print("-" * 95)

    for step in step_data:
        zcross_str = f"{step['zcross_ms']:.2f}" if step['zcross_ms'] is not None else "NOT FOUND"
        status = "DETECTED" if step['zcross_ms'] is not None else "MISSING"
        print(f"{step['step']:<6} {step['contact_ms']:<15.2f} {step['peak_ms']:<16.2f} {step['peak_value']:<14.2f} {zcross_str:<18} {status:<25}")

    print()
    print()

    # Time window for the plot
    t_start_ms = 500.0
    t_end_ms = 3500.0
    t_start_idx = int(t_start_ms * ODR_HZ / 1000.0)
    t_end_idx = int(t_end_ms * ODR_HZ / 1000.0)

    time_axis = (np.arange(t_end_idx - t_start_idx) / ODR_HZ)

    print("[GENERATING DIAGNOSTIC PLOT]")
    print(f"  Time window: {t_start_ms:.1f}ms to {t_end_ms:.1f}ms")
    print(f"  Samples: {t_start_idx} to {t_end_idx} ({t_end_idx - t_start_idx} samples)")
    print()

    # Create figure with 2 panels
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Stair Walker Steps 1–3: gyr_y Zero-Crossing Detection Diagnostic',
                 fontsize=14, fontweight='bold')

    # PANEL 1: gyr_y raw with zero-crossing markers
    ax = axes[0]
    ax.plot(time_axis, gyr_y[t_start_idx:t_end_idx], 'r-', linewidth=1.5, label='gyr_y (raw)')

    # Draw zero line
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5, label='Zero line')

    # Mark step contact times with vertical dashed lines
    colors_step = ['blue', 'green', 'orange']
    for i, step in enumerate(step_data):
        if step['contact_ms'] >= t_start_ms and step['contact_ms'] <= t_end_ms:
            contact_time = (step['contact_ms'] - t_start_ms) / 1000.0
            ax.axvline(x=contact_time, color=colors_step[i], linestyle='--', linewidth=1, alpha=0.6)
            ax.text(contact_time, ax.get_ylim()[1] * 0.95, f"Step {step['step']}",
                   rotation=90, fontsize=10, fontweight='bold', color=colors_step[i],
                   verticalalignment='top', horizontalalignment='right')

    # Mark zero-crossings or missing window
    for i, step in enumerate(step_data):
        if step['contact_ms'] >= t_start_ms and step['contact_ms'] <= t_end_ms:
            contact_time_s = (step['contact_ms'] - t_start_ms) / 1000.0
            window_end_time_s = (step['contact_ms'] + 200 - t_start_ms) / 1000.0

            if window_end_time_s > 0 and contact_time_s < time_axis[-1]:
                if step['zcross_ms'] is not None and step['zcross_ms'] <= step['contact_ms'] + 200:
                    # Zero-crossing found: mark with green circle
                    zcross_time_s = (step['zcross_ms'] - t_start_ms) / 1000.0
                    zcross_value = gyr_y[step['zcross_idx']]
                    ax.plot(zcross_time_s, zcross_value, 'go', markersize=10,
                           markerfacecolor='none', markeredgewidth=2, label=f'Zero-cross (Step {step["step"]})')
                    ax.annotate('✓ Zero-crossing\ndetected',
                               xy=(zcross_time_s, zcross_value),
                               xytext=(10, -20), textcoords='offset points',
                               fontsize=9, color='green', fontweight='bold',
                               bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7),
                               arrowprops=dict(arrowstyle='->', color='green', lw=1.5))
                else:
                    # Zero-crossing NOT found in window: shade the search window
                    window_start_s = contact_time_s
                    window_end_s = min(window_end_time_s, time_axis[-1])
                    ax.axvspan(window_start_s, window_end_s, alpha=0.2, color='red', zorder=1)

                    # Add annotation arrow and text
                    mid_window_s = (window_start_s + window_end_s) / 2
                    mid_y = gyr_y[int((step['contact_ms'] + 100) * ODR_HZ / 1000.0)]

                    ax.annotate('✗ NO zero-crossing\ndetected in window',
                               xy=(mid_window_s, mid_y),
                               xytext=(20, 30), textcoords='offset points',
                               fontsize=9, color='red', fontweight='bold',
                               bbox=dict(boxstyle='round', facecolor='#ffcccc', alpha=0.9),
                               arrowprops=dict(arrowstyle='->', color='red', lw=2))

    ax.set_ylabel('gyr_y (dps)', fontsize=12, fontweight='bold')
    ax.set_title('Panel 1: gyr_y — Stair Walker Steps 1–3 (raw) | Zero-Crossing Detection',
                fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, time_axis[-1]])
    ax.legend(loc='upper right', fontsize=9)

    # PANEL 2: acc_filt with peak markers
    ax = axes[1]
    ax.plot(time_axis, acc_filt[t_start_idx:t_end_idx], 'r-', linewidth=1.5, label='acc_filt')

    # Draw threshold line at 5.0 m/s²
    ax.axhline(y=5.0, color='green', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Threshold (5.0 m/s²)')

    # Mark step contact times with vertical dashed lines and peak values
    for i, step in enumerate(step_data):
        if step['contact_ms'] >= t_start_ms and step['contact_ms'] <= t_end_ms:
            contact_time = (step['contact_ms'] - t_start_ms) / 1000.0
            ax.axvline(x=contact_time, color=colors_step[i], linestyle='--', linewidth=1, alpha=0.6)

            # Mark peak with red dot
            peak_time = (step['peak_ms'] - t_start_ms) / 1000.0
            ax.plot(peak_time, step['peak_value'], 'ro', markersize=8)

            # Annotate peak value and time
            ax.annotate(f"Step {step['step']}\n{step['peak_value']:.2f} m/s² @ {step['peak_ms']:.0f}ms",
                       xy=(peak_time, step['peak_value']),
                       xytext=(5, 10), textcoords='offset points',
                       fontsize=9, color='darkred',
                       bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    ax.set_ylabel('acc_filt (m/s²)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Time (s)', fontsize=12, fontweight='bold')
    ax.set_title('Panel 2: acc_filt — Stair Walker Steps 1–3 | Peak Detection',
                fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, time_axis[-1]])
    ax.legend(loc='upper right', fontsize=9)

    plt.tight_layout()

    # Save plot
    plot_dir = Path('/Users/siyaoshao/gait_device/docs/executive_branch_document/plots')
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plot_dir / 'stair_step2_missing_zerocross.png'
    fig.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"  Plot saved: {plot_path}")
    plt.close(fig)

    print()
    print("=" * 90)
    print("EVIDENCE COLLECTION COMPLETE")
    print("=" * 90)
    print()
    print(f"Output: {plot_path}")
    print()

if __name__ == '__main__':
    main()
