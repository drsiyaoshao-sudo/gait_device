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
st.sidebar.caption("Standard gait imbalance algorithm — terrain efficacy study")

st.sidebar.markdown("---")

profile_labels = {
    "flat":     "Walker 1 — Flat (reference)",
    "bad_wear": "Walker 2 — Bad wearing",
    "stairs":   "Walker 3 — Stairs",
    "slope":    "Walker 4 — Slope (10°)",
}

selected_key = st.sidebar.selectbox(
    "Detail view",
    options=DISPLAY_PROFILES,
    format_func=lambda k: profile_labels[k],
)

pathological = st.sidebar.toggle(
    "Pathological asymmetry (SI ≈ 25%)",
    value=False,
    help="Inject a 25% true SI into all four profiles by alternating "
         "odd/even stance duration. Healthy walkers show SI ≈ 0%.",
)
si_override = 25.0 if pathological else None

n_steps = st.sidebar.slider("Steps to simulate", min_value=50, max_value=500,
                             value=200, step=50)

seed = st.sidebar.number_input("Random seed", min_value=0, max_value=9999,
                                value=42, step=1)

run_clicked = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)

st.sidebar.markdown("---")

# ── Renode status panel ──────────────────────────────────────────────────────
_rn = renode_status()
if _rn["available"]:
    use_renode = st.sidebar.toggle(
        "Use Renode (embedded firmware)",
        value=False,
        help="Run the actual firmware ELF inside Renode instead of the Python algorithm. "
             "Requires `renode` on PATH and a built firmware.elf.",
    )
    st.sidebar.success(
        f"Renode found: `{_rn['renode_path']}`  \n"
        f"ELF: `{_rn['elf_path']}`"
    )
else:
    use_renode = False
    missing = []
    if not _rn["renode_found"]:
        missing.append("renode binary")
    if not _rn["elf_found"]:
        missing.append("firmware.elf")
    st.sidebar.info(
        "**Python path active** (Renode unavailable)  \n"
        f"Missing: {', '.join(missing)}  \n"
        "_Build firmware (`pio run`) and install Renode to enable._"
    )

_path_label = (
    "walker\\_model → **Renode** (firmware.elf)"
    if use_renode
    else "walker\\_model → gait\\_algorithm (Python)"
)
st.sidebar.caption(f"Pipeline: {_path_label}")

# ─────────────────────────────────────────────────────────────────────────────
# Session state — persist results across reruns
# ─────────────────────────────────────────────────────────────────────────────

if "results" not in st.session_state:
    st.session_state.results = None
if "n_steps_run" not in st.session_state:
    st.session_state.n_steps_run = 0
if "via_renode" not in st.session_state:
    st.session_state.via_renode = False
if "pathological" not in st.session_state:
    st.session_state.pathological = False

if run_clicked:
    _label = "Running Renode simulation for all 4 walkers..." if use_renode \
             else "Running simulation for all 4 walkers..."
    with st.spinner(_label):
        import warnings
        with warnings.catch_warnings(record=True) as _warns:
            warnings.simplefilter("always")
            st.session_state.results = run_all_profiles(
                n_steps=n_steps, seed=int(seed), use_renode=use_renode,
                si_override=si_override, profile_keys=DISPLAY_PROFILES,
            )
        st.session_state.n_steps_run = n_steps
        st.session_state.via_renode = use_renode
        st.session_state.pathological = pathological
        for w in _warns:
            st.warning(f"⚠️ {w.message}", icon="⚠️")

from typing import Optional
results: Optional[dict] = st.session_state.results

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

_pipeline_badge = (
    " — :green[Renode path (firmware.elf)]" if st.session_state.via_renode
    else " — :blue[Python path (gait\\_algorithm)]"
)
st.title("Gait Digital Twin Simulator" + _pipeline_badge)
st.caption(
    "All walkers are healthy and symmetric (true SI = 0%). "
    "The question: does the standard single-ankle gait algorithm correctly report SI ≈ 0% "
    "across different terrains?"
)

if results is None:
    st.info("Configure parameters in the sidebar and click **Run Simulation**.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Panel 2 — SI time series, all 4 walkers (shown first — it's the key output)
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Detected Symmetry Index — All Walkers")
if st.session_state.pathological:
    st.caption(
        f"Clinical threshold: SI > {SI_CLINICAL_THRESHOLD}% = asymmetric. "
        "**Pathological mode:** true SI = 25% for all walkers. Readings above threshold are true positives."
    )
else:
    st.caption(
        f"Clinical threshold: SI > {SI_CLINICAL_THRESHOLD}% = asymmetric. "
        "**Healthy mode:** true SI = 0% for all walkers. Any reading above threshold is a false positive."
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
    xaxis_title="Step index (anchor)",
    yaxis_title="SI stance (%)",
    yaxis=dict(range=[0, max(60, SI_CLINICAL_THRESHOLD * 2)]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=380,
    margin=dict(t=10, b=40),
)
st.plotly_chart(fig_si, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Detail panels for selected walker
# ─────────────────────────────────────────────────────────────────────────────

res = results[selected_key]
color = WALKER_COLORS[selected_key]
odr = 208.0

st.markdown("---")
st.subheader(f"Detail — {profile_labels[selected_key]}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Steps detected", res.step_count, f"/ {n_steps} generated")
col2.metric("Snapshots", len(res.snapshots))

final_si = res.snapshot_si_stance[-1] if res.snapshots else 0.0
col3.metric(
    "Final SI stance",
    f"{final_si:.1f}%",
    delta=f"{final_si - 0:.1f}% vs true 0%",
    delta_color="inverse",
)
col4.metric("Mounting suspect steps", res.mounting_suspect_count)

# ─────────────────────────────────────────────────────────────────────────────
# Panel 1 — Raw IMU signal + step markers
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Raw IMU Signal — acc_z and gyr_y")

MAX_DISPLAY_SAMPLES = 4000   # ~19s at 208 Hz — keep chart responsive
samples_display = res.samples[:MAX_DISPLAY_SAMPLES]
t_ms = np.arange(len(samples_display)) / odr * 1000.0

fig_imu = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    subplot_titles=("acc_z  (m/s²)", "gyr_y  (dps)"),
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

st.subheader("Phase Timing — Stance / Swing per Step")

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
        xaxis_title="Step index",
        yaxis_title="Duration (ms)",
        height=320,
        margin=dict(t=10, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    if any(suspect):
        st.caption("Red bars: `mounting_suspect` flag set on that step.")
    st.plotly_chart(fig_phase, use_container_width=True)
else:
    st.warning("No valid phase records — step detector found no steps.")

# ─────────────────────────────────────────────────────────────────────────────
# Panel 4 — Profile derived parameters
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Derived Physical Parameters")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Profile parameters (derived from three primitives)**")
    params = res.summary
    rows = [[k, str(v)] for k, v in params.items()]
    st.table({"Parameter": [r[0] for r in rows],
              "Value":     [r[1] for r in rows]})

with col_b:
    st.markdown("**Detection summary**")
    detection_rate = res.step_count / n_steps * 100 if n_steps > 0 else 0
    si_values = res.snapshot_si_stance
    st.table({
        "Metric": [
            "Steps generated",
            "Steps detected",
            "Detection rate",
            "False positive (SI > 10%)",
            "Mean SI stance",
            "Max SI stance",
            "Mounting suspect steps",
        ],
        "Value": [
            str(n_steps),
            str(res.step_count),
            f"{detection_rate:.1f}%",
            "Yes" if any(s > SI_CLINICAL_THRESHOLD for s in si_values) else "No",
            f"{res.si_mean():.1f}%" if si_values else "—",
            f"{res.si_max():.1f}%" if si_values else "—",
            str(res.mounting_suspect_count),
        ],
    })
