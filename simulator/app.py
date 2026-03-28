"""
Gait Digital Twin Simulator — Streamlit UI

Run:  streamlit run simulator/app.py
      (from the gait_device/ root directory)

Layout
------
Sidebar   : profile selector, n_steps slider, run button
Panel 1   : Raw IMU signal — acc_z and gyr_y with detected step markers
Panel 2   : SI time series — all 4 walkers overlaid (the key comparison)
Panel 3   : Per-step phase timing bars (stance / swing)
Panel 4   : Profile derived parameter table + detection summary
"""
import sys
import os

# Allow imports from simulator/ when run via `streamlit run simulator/app.py`
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import Optional

from walker_model import PROFILES
from pipeline import run_profile, run_all_profiles, PipelineResult, renode_status


# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Gait Digital Twin",
    page_icon="🦶",
    layout="wide",
)

WALKER_COLORS = {
    "flat":     "#2196F3",   # blue
    "bad_wear": "#FF5722",   # orange-red
    "stairs":   "#4CAF50",   # green
    "slope":    "#9C27B0",   # purple
}

DISPLAY_PROFILES = ["flat", "bad_wear", "stairs", "slope"]

SI_CLINICAL_THRESHOLD = 10.0   # Robinson et al. 1987

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

st.sidebar.title("Gait Digital Twin")
st.sidebar.caption("Agentic algorithm search & validation across terrain profiles")

st.sidebar.markdown("---")

profile_labels = {
    "flat":     "Walker 1 — Flat ground (reference)",
    "bad_wear": "Walker 2 — Poor device fit",
    "stairs":   "Walker 3 — Ascending stairs",
    "slope":    "Walker 4 — Inclined surface (10°)",
}

selected_key = st.sidebar.selectbox(
    "Detail view",
    options=DISPLAY_PROFILES,
    format_func=lambda k: profile_labels[k],
)

pathological = st.sidebar.toggle(
    "Simulate gait asymmetry (SI ≈ 25%)",
    value=False,
    help="Inject a clinically significant asymmetry (25% true SI) into all four "
         "profiles by alternating stance duration between limbs. "
         "Healthy walkers show SI ≈ 0%.",
)
si_override = 25.0 if pathological else None

show_comparison = st.sidebar.toggle(
    "Show algorithm comparison",
    value=False,
    help="Overlay original dual-confirmation algorithm (dashed) vs "
         "terrain-aware algorithm (solid) for all four profiles. "
         "Available in algorithm simulation mode only. "
         "The stair walker is the key story: the original algorithm detects "
         "0 steps on stairs — the terrain-aware algorithm detects 100/100.",
)

n_steps = st.sidebar.slider("Steps to simulate", min_value=50, max_value=500,
                             value=200, step=50)

seed = st.sidebar.number_input("Random seed", min_value=0, max_value=9999,
                                value=42, step=1)

run_clicked = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)

st.sidebar.markdown("---")

# ── Simulation engine panel ───────────────────────────────────────────────────
_rn = renode_status()
if _rn["available"]:
    use_renode = st.sidebar.toggle(
        "Validate on embedded firmware",
        value=False,
        help="Run the actual compiled firmware on a virtual microcontroller "
             "instead of the algorithm model. Requires Renode and a built firmware.",
    )
    st.sidebar.success("Embedded firmware available")
else:
    use_renode = False
    st.sidebar.info("Algorithm simulation mode")

_mode_label = "Embedded firmware" if use_renode else "Algorithm simulation"
st.sidebar.caption(f"Engine: {_mode_label}")

# Algorithm comparison only applies to the Python simulation path
if use_renode:
    show_comparison = False

# ─────────────────────────────────────────────────────────────────────────────
# Session state — persist results across reruns
# ─────────────────────────────────────────────────────────────────────────────

if "results" not in st.session_state:
    st.session_state.results = None
if "legacy_results" not in st.session_state:
    st.session_state.legacy_results = None
if "n_steps_run" not in st.session_state:
    st.session_state.n_steps_run = 0
if "via_renode" not in st.session_state:
    st.session_state.via_renode = False
if "pathological" not in st.session_state:
    st.session_state.pathological = False
if "show_comparison_run" not in st.session_state:
    st.session_state.show_comparison_run = False

if run_clicked:
    _label = "Running simulation on embedded firmware..." if use_renode \
             else "Running simulation..."
    with st.spinner(_label):
        import warnings
        with warnings.catch_warnings(record=True) as _warns:
            warnings.simplefilter("always")
            st.session_state.results = run_all_profiles(
                n_steps=n_steps, seed=int(seed), use_renode=use_renode,
                si_override=si_override, profile_keys=DISPLAY_PROFILES,
            )
            if show_comparison and not use_renode:
                st.session_state.legacy_results = run_all_profiles(
                    n_steps=n_steps, seed=int(seed), use_renode=False,
                    si_override=si_override, profile_keys=DISPLAY_PROFILES,
                    use_legacy=True,
                )
            else:
                st.session_state.legacy_results = None
        st.session_state.n_steps_run = n_steps
        st.session_state.via_renode = use_renode
        st.session_state.pathological = pathological
        st.session_state.show_comparison_run = show_comparison and not use_renode
        for w in _warns:
            st.warning(f"⚠️ {w.message}", icon="⚠️")

results: Optional[dict] = st.session_state.results

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

_mode_badge = (
    " — :green[Embedded firmware]" if st.session_state.via_renode
    else " — :blue[Algorithm simulation]"
)
st.title("Gait Digital Twin Simulator" + _mode_badge)

if st.session_state.pathological:
    st.caption(
        "Simulated asymmetry: true SI = 25% for all walkers. "
        "Readings above the clinical threshold are true positives — "
        "the device should flag these as abnormal."
    )
else:
    st.caption(
        "All walkers are healthy and symmetric (true SI = 0%). "
        "The question: does the developed gait algorithm correctly report SI ≈ 0% "
        "across all terrains, or does terrain corrupt the output?"
    )

if results is None:
    st.info("Configure parameters in the sidebar and click **Run Simulation**.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Panel 2 — SI time series, all 4 walkers (shown first — it's the key output)
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Symmetry Index Over Time — All Walkers")
if st.session_state.pathological:
    st.caption(
        f"Clinical threshold (Robinson et al.): SI > {SI_CLINICAL_THRESHOLD}% = asymmetric gait. "
        "**Asymmetry mode active** — all walkers carry a 25% true SI. Lines above the threshold are correct detections."
    )
else:
    st.caption(
        f"Clinical threshold (Robinson et al.): SI > {SI_CLINICAL_THRESHOLD}% = asymmetric gait. "
        "**Healthy mode** — all walkers are symmetric. Any line above the threshold is a false positive."
    )

fig_si = go.Figure()

fig_si.add_hline(
    y=SI_CLINICAL_THRESHOLD,
    line_dash="dash", line_color="red", line_width=1.5,
    annotation_text=f"Clinical threshold ({SI_CLINICAL_THRESHOLD}%)",
    annotation_position="bottom right",
)
fig_si.add_hrect(y0=SI_CLINICAL_THRESHOLD, y1=60,
                 fillcolor="red", opacity=0.05, line_width=0)

for key, res in results.items():
    if not res.snapshots:
        continue
    fig_si.add_trace(go.Scatter(
        x=res.snapshot_steps,
        y=res.snapshot_si_stance,
        mode="lines+markers",
        name=profile_labels[key],
        line=dict(color=WALKER_COLORS[key], width=2),
        marker=dict(size=5),
    ))

fig_si.update_layout(
    xaxis_title="Step count",
    yaxis_title="Symmetry Index — stance (%)",
    yaxis=dict(range=[0, max(60, SI_CLINICAL_THRESHOLD * 2)]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=380,
    margin=dict(t=10, b=40),
)
st.plotly_chart(fig_si, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Algorithm comparison panel (algorithm simulation mode only)
# ─────────────────────────────────────────────────────────────────────────────

legacy_results: Optional[dict] = st.session_state.legacy_results

if st.session_state.show_comparison_run and legacy_results is not None:
    st.subheader("Algorithm Comparison — Terrain-Aware vs. Original")
    st.caption(
        "**Solid lines** — terrain-aware algorithm (push-off primary trigger, ring-buffer heel-strike inference). "
        "**Dashed lines** — original dual-confirmation algorithm (acc peak → 40 ms window → gyr_y zero-cross). "
        "The stair walker reveals the original algorithm's failure: missed steps and corrupted SI. "
        "On the embedded firmware path the original algorithm detects **0/100 steps** on stairs — "
        "the full failure mode is only visible in Renode bare-metal simulation."
    )

    fig_cmp = go.Figure()
    fig_cmp.add_hline(
        y=SI_CLINICAL_THRESHOLD,
        line_dash="dash", line_color="red", line_width=1,
        annotation_text=f"Clinical threshold ({SI_CLINICAL_THRESHOLD}%)",
        annotation_position="bottom right",
    )
    fig_cmp.add_hrect(y0=SI_CLINICAL_THRESHOLD, y1=60,
                      fillcolor="red", opacity=0.05, line_width=0)

    for key in DISPLAY_PROFILES:
        color = WALKER_COLORS[key]
        label = profile_labels[key]

        # New terrain-aware (solid)
        res_new = results.get(key)
        if res_new and res_new.snapshots:
            fig_cmp.add_trace(go.Scatter(
                x=res_new.snapshot_steps,
                y=res_new.snapshot_si_stance,
                mode="lines+markers",
                name=f"{label} — terrain-aware",
                line=dict(color=color, width=2),
                marker=dict(size=5),
                legendgroup=key,
            ))

        # Legacy dual-confirmation (dashed)
        res_leg = legacy_results.get(key)
        if res_leg and res_leg.snapshots:
            fig_cmp.add_trace(go.Scatter(
                x=res_leg.snapshot_steps,
                y=res_leg.snapshot_si_stance,
                mode="lines+markers",
                name=f"{label} — original",
                line=dict(color=color, width=2, dash="dot"),
                marker=dict(size=4, symbol="circle-open"),
                legendgroup=key,
            ))
        elif res_leg and not res_leg.snapshots:
            # Zero steps detected — show annotation at y=0
            fig_cmp.add_annotation(
                x=0.5, xref="paper",
                y=2, yref="y",
                text=f"{label} (original): 0 steps detected",
                showarrow=False,
                font=dict(color=color, size=11),
                xanchor="center",
            )

    # Step count comparison table beneath chart
    step_data: dict = {"Walker": [], "Steps (terrain-aware)": [], "Steps (original)": []}
    for key in DISPLAY_PROFILES:
        step_data["Walker"].append(profile_labels[key])
        step_data["Steps (terrain-aware)"].append(
            str(results[key].step_count) if key in results else "—"
        )
        step_data["Steps (original)"].append(
            str(legacy_results[key].step_count) if key in legacy_results else "—"
        )

    fig_cmp.update_layout(
        xaxis_title="Step count",
        yaxis_title="Symmetry Index — stance (%)",
        yaxis=dict(range=[0, max(60, SI_CLINICAL_THRESHOLD * 2)]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
        margin=dict(t=10, b=40),
    )
    st.plotly_chart(fig_cmp, use_container_width=True)
    st.table(step_data)

elif show_comparison and not st.session_state.show_comparison_run:
    st.info(
        "Algorithm comparison is enabled. Click **Run Simulation** to generate "
        "both algorithm paths and display the overlay."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Detail panels for selected walker
# ─────────────────────────────────────────────────────────────────────────────

res = results[selected_key]
color = WALKER_COLORS[selected_key]
odr = 208.0
true_si = 25.0 if st.session_state.pathological else 0.0

st.markdown("---")
st.subheader(f"Detail — {profile_labels[selected_key]}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Steps detected", res.step_count, f"/ {n_steps} generated")
col2.metric("Snapshots", len(res.snapshots))

final_si = res.snapshot_si_stance[-1] if res.snapshots else 0.0
col3.metric(
    "Final SI (stance)",
    f"{final_si:.1f}%",
    delta=f"{final_si - true_si:+.1f}% vs true {true_si:.0f}%",
    delta_color="inverse",
)
col4.metric("Mounting alerts", res.mounting_suspect_count)

# ─────────────────────────────────────────────────────────────────────────────
# Panel 1 — Raw IMU signal + step markers
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Raw Sensor Signal")

MAX_DISPLAY_SAMPLES = 4000   # ~19s at 208 Hz — keep chart responsive
samples_display = res.samples[:MAX_DISPLAY_SAMPLES]
t_ms = np.arange(len(samples_display)) / odr * 1000.0

fig_imu = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    subplot_titles=("Vertical acceleration  (m/s²)", "Ankle angular velocity  (dps)"),
    vertical_spacing=0.08,
)

fig_imu.add_trace(
    go.Scatter(x=t_ms, y=samples_display[:, 2],
               line=dict(color=color, width=1), name="acc_z", showlegend=False),
    row=1, col=1,
)
fig_imu.add_trace(
    go.Scatter(x=t_ms, y=samples_display[:, 4],
               line=dict(color=color, width=1, dash="dot"), name="gyr_y", showlegend=False),
    row=2, col=1,
)

# Step markers
for ev in res.steps:
    if ev.ts_ms > t_ms[-1]:
        break
    fig_imu.add_vline(
        x=ev.ts_ms, line_color="rgba(255,0,0,0.35)", line_width=1,
        row="all",
    )

fig_imu.update_xaxes(title_text="Time (ms)", row=2, col=1)
fig_imu.update_layout(height=420, margin=dict(t=30, b=40))
st.plotly_chart(fig_imu, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Panel 3 — Phase timing bars (stance / swing per step)
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Gait Phase Timing — Stance / Swing per Step")

valid_records = [r for r in res.records if r.valid]

if valid_records:
    MAX_BARS = 80
    recs = valid_records[:MAX_BARS]

    stance_vals = [r.stance_duration_ms for r in recs]
    swing_vals  = [r.swing_duration_ms  for r in recs]
    step_ids    = [str(r.step_index)    for r in recs]
    suspect     = [r.mounting_suspect   for r in recs]

    fig_phase = go.Figure()
    fig_phase.add_trace(go.Bar(
        name="Stance", x=step_ids, y=stance_vals,
        marker_color=[("rgba(255,87,34,0.8)" if s else color) for s in suspect],
    ))
    fig_phase.add_trace(go.Bar(
        name="Swing", x=step_ids, y=swing_vals,
        marker_color="rgba(180,180,180,0.6)",
    ))
    fig_phase.update_layout(
        barmode="stack",
        xaxis_title="Step",
        yaxis_title="Duration (ms)",
        height=320,
        margin=dict(t=10, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    if any(suspect):
        st.caption("Orange bars: device mounting alert flagged on that step.")
    st.plotly_chart(fig_phase, use_container_width=True)
else:
    st.warning("No phase records available for this profile.")

# ─────────────────────────────────────────────────────────────────────────────
# Panel 4 — Profile derived parameters
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Profile Summary")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Biomechanical parameters**")
    params = res.summary
    rows = [[k, str(v)] for k, v in params.items()]
    st.table({"Parameter": [r[0] for r in rows],
              "Value":     [r[1] for r in rows]})

with col_b:
    st.markdown("**Detection results**")
    detection_rate = res.step_count / n_steps * 100 if n_steps > 0 else 0
    si_values = res.snapshot_si_stance
    above_threshold = any(s > SI_CLINICAL_THRESHOLD for s in si_values)
    threshold_label = "True positive" if (above_threshold and st.session_state.pathological) \
                      else ("False positive" if above_threshold else "No")
    st.table({
        "Metric": [
            "Steps generated",
            "Steps detected",
            "Detection rate",
            "Above clinical threshold",
            "Mean SI (stance)",
            "Max SI (stance)",
            "Mounting alerts",
        ],
        "Value": [
            str(n_steps),
            str(res.step_count),
            f"{detection_rate:.1f}%",
            threshold_label,
            f"{res.si_mean():.1f}%" if si_values else "—",
            f"{res.si_max():.1f}%" if si_values else "—",
            str(res.mounting_suspect_count),
        ],
    })
