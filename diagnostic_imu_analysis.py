#!/usr/bin/env python3
"""
Diagnostic IMU analysis: stair vs flat walker comparison.
Bureaucracy Standing Order execution — Signal Plotting.
Evidence for Judicial Hearing on acc_filt peak degradation and timing relationships.

Generated signals:
- flat: healthy adult, flat ground (baseline reference)
- stairs: healthy adult, ascending stairs

Filtering applied:
- acc_filt: 15 Hz low-pass Butterworth, 2nd order (matches firmware)
- gyr_y_hp: 30 Hz high-pass Butterworth, 2nd order (matches firmware step detector)
"""

import os
import sys
import math
import subprocess
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

    # 30 Hz high-pass for gyr_y → gyr_y_hp (2nd order Butterworth)
    sos_hp = butter(2, 30.0, btype='high', fs=ODR_HZ, output='sos')

    return sos_lp, sos_hp


def apply_filters(imu_data, sos_lp, sos_hp):
    """
    Apply filters to IMU data.

    Parameters
    ----------
    imu_data : ndarray, shape (N, 6)
        [ax, ay, az, gx, gy, gz]
    sos_lp : ndarray
        Low-pass SOS coefficients
    sos_hp : ndarray
        High-pass SOS coefficients

    Returns
    -------
    acc_filt, gyr_y_hp : ndarray, ndarray
        Filtered acc_z and gyr_y
    """
    acc_z = imu_data[:, 2]
    gyr_y = imu_data[:, 4]

    acc_filt = sosfilt(sos_lp, acc_z)
    gyr_y_hp = sosfilt(sos_hp, gyr_y)

    return acc_filt, gyr_y_hp


def find_ground_contacts(acc_filt, window_ms=50):
    """
    Detect ground contact instants from acc_filt peaks.

    Returns indices where acc_filt reaches local maxima (ground contact peaks).
    Uses a minimum window to separate detections.
    """
    window_samples = int(window_ms * ODR_HZ / 1000.0)

    contacts = []
    i = 0
    while i < len(acc_filt):
        # Find the peak in the next window
        end = min(i + window_samples, len(acc_filt))
        if i == end:
            break

        peak_idx = i + np.argmax(acc_filt[i:end])
        contacts.append(peak_idx)
        i = peak_idx + window_samples

    return np.array(contacts, dtype=int)


def analyze_step_timing(acc_filt, gyr_y, gyr_y_hp, contact_idx, step_num,
                        window_pre_ms=50, window_post_ms=200):
    """
    Analyze a single step's timing relationships.

    For the step starting at contact_idx:
    - Find acc_filt peak in the 200ms window after contact
    - Find gyr_y zero-crossing after contact
    - Compute gap between them
    - Check if gap <= 40ms (window_fires criterion)
    """
    window_pre_samples = int(window_pre_ms * ODR_HZ / 1000.0)
    window_post_samples = int(window_post_ms * ODR_HZ / 1000.0)

    start_idx = max(0, contact_idx - window_pre_samples)
    end_idx = min(len(acc_filt), contact_idx + window_post_samples)

    # acc_filt peak in the 200ms window after contact
    search_start = contact_idx
    search_end = min(contact_idx + window_post_samples, len(acc_filt))
    if search_end <= search_start:
        return None

    peak_in_window = np.argmax(acc_filt[search_start:search_end]) + search_start
    peak_value = acc_filt[peak_in_window]
    peak_ms = (peak_in_window / ODR_HZ) * 1000.0

    # gyr_y zero-crossing: first sign change after contact
    gyr_y_zero_cross_idx = None
    for i in range(contact_idx, min(contact_idx + window_post_samples, len(gyr_y) - 1)):
        if gyr_y[i] * gyr_y[i + 1] < 0:  # sign change
            gyr_y_zero_cross_idx = i
            break

    if gyr_y_zero_cross_idx is None:
        gyr_y_zero_cross_ms = None
    else:
        gyr_y_zero_cross_ms = (gyr_y_zero_cross_idx / ODR_HZ) * 1000.0

    # Gap between zero-crossing and peak
    if gyr_y_zero_cross_ms is not None:
        gap_ms = abs(gyr_y_zero_cross_ms - peak_ms)
        window_fires = gap_ms <= 40.0
    else:
        gap_ms = None
        window_fires = False

    return {
        'step': step_num,
        'contact_idx': contact_idx,
        'peak_value': peak_value,
        'peak_ms': peak_ms,
        'gyr_y_zero_cross_ms': gyr_y_zero_cross_ms,
        'gap_ms': gap_ms,
        'window_fires': window_fires,
    }


def main():
    print("=" * 80)
    print("DIAGNOSTIC IMU ANALYSIS: Stair vs Flat Walker Comparison")
    print("=" * 80)
    print()

    # Design filters
    sos_lp, sos_hp = design_filters()
    print("[FILTER DESIGN]")
    print(f"  LP filter: 15 Hz, 2nd order Butterworth (acc_z → acc_filt)")
    print(f"  HP filter: 30 Hz, 2nd order Butterworth (gyr_y → gyr_y_hp)")
    print()

    # Generate IMU sequences
    print("[SIGNAL GENERATION]")
    flat_profile = PROFILES['flat']
    stairs_profile = PROFILES['stairs']

    rng = np.random.default_rng(seed=42)
    flat_imu = generate_imu_sequence(flat_profile, n_steps=30, rng=rng)

    rng = np.random.default_rng(seed=42)
    stairs_imu = generate_imu_sequence(stairs_profile, n_steps=30, rng=rng)

    print(f"  Flat walker:   {len(flat_imu)} samples ({flat_imu.shape[0] / ODR_HZ:.1f}s)")
    print(f"  Stairs walker: {len(stairs_imu)} samples ({stairs_imu.shape[0] / ODR_HZ:.1f}s)")
    print()

    # Apply filters
    print("[FILTERING]")
    acc_filt_flat, gyr_y_hp_flat = apply_filters(flat_imu, sos_lp, sos_hp)
    acc_filt_stairs, gyr_y_hp_stairs = apply_filters(stairs_imu, sos_lp, sos_hp)

    gyr_y_flat = flat_imu[:, 4]
    gyr_y_stairs = stairs_imu[:, 4]

    acc_z_flat = flat_imu[:, 2]
    acc_z_stairs = stairs_imu[:, 2]

    print(f"  acc_filt_flat:   min={acc_filt_flat.min():.2f}, max={acc_filt_flat.max():.2f} m/s²")
    print(f"  acc_filt_stairs: min={acc_filt_stairs.min():.2f}, max={acc_filt_stairs.max():.2f} m/s²")
    print(f"  gyr_y_flat:      min={gyr_y_flat.min():.1f}, max={gyr_y_flat.max():.1f} dps")
    print(f"  gyr_y_stairs:    min={gyr_y_stairs.min():.1f}, max={gyr_y_stairs.max():.1f} dps")
    print()

    # Detect ground contacts and analyze timing
    print("[GROUND CONTACT DETECTION]")
    contacts_flat = find_ground_contacts(acc_filt_flat, window_ms=50)
    contacts_stairs = find_ground_contacts(acc_filt_stairs, window_ms=50)

    # Skip the stationary prefix (1 second = 208 samples)
    stationary_samples = int(ODR_HZ)
    contacts_flat = contacts_flat[contacts_flat > stationary_samples]
    contacts_stairs = contacts_stairs[contacts_stairs > stationary_samples]

    print(f"  Flat walker contacts detected: {len(contacts_flat)}")
    print(f"  Stairs walker contacts detected: {len(contacts_stairs)}")
    print()

    # Analyze timing for first 5 steps
    print("[TIMING ANALYSIS — First 5 steps]")
    print()

    flat_analysis = []
    for i in range(min(5, len(contacts_flat))):
        result = analyze_step_timing(acc_filt_flat, gyr_y_flat, gyr_y_hp_flat,
                                      contacts_flat[i], i + 1)
        if result:
            flat_analysis.append(result)

    stairs_analysis = []
    for i in range(min(5, len(contacts_stairs))):
        result = analyze_step_timing(acc_filt_stairs, gyr_y_stairs, gyr_y_hp_stairs,
                                      contacts_stairs[i], i + 1)
        if result:
            stairs_analysis.append(result)

    # Print table header
    print(f"{'Profile':<8} {'Step':<5} {'acc_filt_peak':<16} {'gyr_y_zcross':<16} {'peak_ms':<10} {'gap_ms':<10} {'window_fires':<14}")
    print(f"{'':8} {'':5} {'(m/s²)':<16} {'(ms)':<16} {'(ms)':<10} {'(ms)':<10} {'(bool)':<14}")
    print("-" * 90)

    for result in flat_analysis:
        peak_str = f"{result['peak_value']:.2f}"
        zcross_str = f"{result['gyr_y_zero_cross_ms']:.2f}" if result['gyr_y_zero_cross_ms'] is not None else "N/A"
        gap_str = f"{result['gap_ms']:.2f}" if result['gap_ms'] is not None else "N/A"
        print(f"{'flat':<8} {result['step']:<5} {peak_str:<16} {zcross_str:<16} {result['peak_ms']:<10.2f} {gap_str:<10} {str(result['window_fires']):<14}")

    print()

    for result in stairs_analysis:
        peak_str = f"{result['peak_value']:.2f}"
        zcross_str = f"{result['gyr_y_zero_cross_ms']:.2f}" if result['gyr_y_zero_cross_ms'] is not None else "N/A"
        gap_str = f"{result['gap_ms']:.2f}" if result['gap_ms'] is not None else "N/A"
        print(f"{'stairs':<8} {result['step']:<5} {peak_str:<16} {zcross_str:<16} {result['peak_ms']:<10.2f} {gap_str:<10} {str(result['window_fires']):<14}")

    print()
    print()

    # Generate diagnostic plot
    print("[PLOT GENERATION]")

    # Use first 10 steps worth of samples for the first three panels
    step_duration_flat_ms = (60000 / flat_profile.cadence_spm)  # ~571ms per step at 105 spm
    step_duration_stairs_ms = (60000 / stairs_profile.cadence_spm)  # ~857ms per step at 70 spm

    # For comparison, use 10 steps of flat time duration for both
    n_samples_10_steps = int(10 * step_duration_flat_ms * ODR_HZ / 1000.0)
    time_axis_flat = np.arange(n_samples_10_steps) / ODR_HZ
    time_axis_stairs = np.arange(min(n_samples_10_steps, len(acc_z_stairs))) / ODR_HZ

    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    fig.suptitle('IMU Diagnostic: Stair vs Flat Walker (First 10 Steps)',
                 fontsize=14, fontweight='bold')

    # Panel 1: acc_z raw
    ax = axes[0]
    ax.plot(time_axis_flat, acc_z_flat[:n_samples_10_steps], 'b-', linewidth=1, label='Flat', alpha=0.7)
    ax.plot(time_axis_stairs, acc_z_stairs[:len(time_axis_stairs)], 'r-', linewidth=1, label='Stairs', alpha=0.7)
    ax.set_ylabel('acc_z (m/s²)', fontsize=11, fontweight='bold')
    ax.set_title('Panel 1: Raw acc_z (First 10 Steps)', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, time_axis_flat[-1]])

    # Panel 2: acc_filt (LP filtered) with threshold line
    ax = axes[1]
    ax.plot(time_axis_flat, acc_filt_flat[:n_samples_10_steps], 'b-', linewidth=1.5, label='Flat', alpha=0.8)
    ax.plot(time_axis_stairs, acc_filt_stairs[:len(time_axis_stairs)], 'r-', linewidth=1.5, label='Stairs', alpha=0.8)

    # Annotate peaks for flat
    for i, result in enumerate(flat_analysis):
        if i < 5:
            peak_time = result['peak_ms'] / 1000.0
            if peak_time < time_axis_flat[-1]:
                ax.plot(peak_time, result['peak_value'], 'bo', markersize=6, alpha=0.7)
                ax.annotate(f"{result['peak_value']:.2f}",
                           xy=(peak_time, result['peak_value']),
                           xytext=(5, 5), textcoords='offset points', fontsize=8,
                           color='blue', alpha=0.7)

    # Annotate peaks for stairs
    for i, result in enumerate(stairs_analysis):
        if i < 5:
            peak_time = result['peak_ms'] / 1000.0
            if peak_time < time_axis_stairs[-1]:
                ax.plot(peak_time, result['peak_value'], 'ro', markersize=6, alpha=0.7)
                ax.annotate(f"{result['peak_value']:.2f}",
                           xy=(peak_time, result['peak_value']),
                           xytext=(5, -15), textcoords='offset points', fontsize=8,
                           color='red', alpha=0.7)

    # Threshold line
    ax.axhline(y=5.0, color='green', linestyle='--', linewidth=1.5, label='Threshold (5.0 m/s²)', alpha=0.6)
    ax.set_ylabel('acc_filt (m/s²)', fontsize=11, fontweight='bold')
    ax.set_title('Panel 2: acc_filt (15 Hz LP) with Peak Annotations', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, time_axis_flat[-1]])

    # Panel 3: gyr_y raw
    ax = axes[2]
    ax.plot(time_axis_flat, gyr_y_flat[:n_samples_10_steps], 'b-', linewidth=1, label='Flat', alpha=0.7)
    ax.plot(time_axis_stairs, gyr_y_stairs[:len(time_axis_stairs)], 'r-', linewidth=1, label='Stairs', alpha=0.7)
    ax.set_ylabel('gyr_y (dps)', fontsize=11, fontweight='bold')
    ax.set_title('Panel 3: Raw gyr_y (First 10 Steps)', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, time_axis_flat[-1]])
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)

    # Panel 4: gyr_y_hp (HP filtered) with threshold line
    ax = axes[3]
    ax.plot(time_axis_flat, gyr_y_hp_flat[:n_samples_10_steps], 'b-', linewidth=1.5, label='Flat', alpha=0.8)
    ax.plot(time_axis_stairs, gyr_y_hp_stairs[:len(time_axis_stairs)], 'r-', linewidth=1.5, label='Stairs', alpha=0.8)

    # Threshold line
    ax.axhline(y=30.0, color='green', linestyle='--', linewidth=1.5, label='Threshold (30 dps)', alpha=0.6)
    ax.axhline(y=-30.0, color='green', linestyle='--', linewidth=1.5, alpha=0.6)

    ax.set_ylabel('gyr_y_hp (dps)', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax.set_title('Panel 4: gyr_y_hp (30 Hz HP) with Push-Off Threshold', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, time_axis_flat[-1]])
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)

    plt.tight_layout()

    # Save plot
    plot_dir = Path('/Users/siyaoshao/gait_device/docs/executive_branch_document/plots')
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plot_dir / 'stair_vs_flat_imu_diagnostic.png'
    fig.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"  Plot saved: {plot_path}")
    if os.environ.get('GAITSENSE_DEMO'):
        subprocess.Popen(['open', str(plot_path)])
    plt.close(fig)

    print()
    print("=" * 80)
    print("EVIDENCE COLLECTION COMPLETE")
    print("=" * 80)
    print()
    print(f"Plot file: {plot_path}")
    print()
    print("[SUMMARY FOR JUDICIAL HEARING]")
    print()
    print("Key Findings:")
    print()

    # Compute summary statistics
    flat_peaks = [r['peak_value'] for r in flat_analysis]
    stairs_peaks = [r['peak_value'] for r in stairs_analysis]

    if flat_peaks:
        print(f"  Flat walker acc_filt peaks (first 5 steps):   mean={np.mean(flat_peaks):.2f} m/s², "
              f"range=[{np.min(flat_peaks):.2f}, {np.max(flat_peaks):.2f}] m/s²")
    if stairs_peaks:
        print(f"  Stairs walker acc_filt peaks (first 5 steps): mean={np.mean(stairs_peaks):.2f} m/s², "
              f"range=[{np.min(stairs_peaks):.2f}, {np.max(stairs_peaks):.2f}] m/s²")

    if flat_peaks and stairs_peaks:
        degradation_pct = 100 * (np.mean(flat_peaks) - np.mean(stairs_peaks)) / np.mean(flat_peaks)
        print(f"  Peak degradation (stairs vs flat): {degradation_pct:.1f}%")

    print()

    # Window firing analysis
    flat_fires = sum(1 for r in flat_analysis if r['window_fires'])
    stairs_fires = sum(1 for r in stairs_analysis if r['window_fires'])

    print(f"  Flat walker: {flat_fires}/{len(flat_analysis)} steps have gyr_y zero-cross ≤40ms from acc_filt peak (window fires)")
    print(f"  Stairs walker: {stairs_fires}/{len(stairs_analysis)} steps have gyr_y zero-cross ≤40ms from acc_filt peak (window fires)")

    print()


if __name__ == '__main__':
    main()
