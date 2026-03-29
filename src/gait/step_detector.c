/*
 * step_detector.c — Terrain-Aware Step Detector (Option C)
 *
 * Algorithm: gyr_y_hp push-off burst (primary trigger) + acc_filt threshold
 * since last step (confirmation) + ring-buffer heel-strike inference.
 *
 * Change from original acc-primary detector:
 *   OLD: acc_filt > threshold  →  40 ms window  →  gyr_y zero-crossing
 *   NEW: gyr_y_hp > 30 dps (push-off entry)  →  falling edge fires step
 *        acc_filt > threshold at any point since last step (confirmation)
 *        ring buffer of 8 acc_filt crossings → retrospective heel-strike ts
 *
 * Why terrain-agnostic:
 *   Flat/slope/bad_wear: heel strikes produce both acc spike and push-off burst.
 *   Stairs (forefoot strike): no sharp acc spike at contact — the slow sigmoid
 *   loading means acc_filt peaks 141 ms into stance while the original 40 ms
 *   gyro confirmation window expired 126 ms earlier (0/100 steps detected).
 *   Push-off is universal: every terrain ends stance with plantar-flexion.
 *   gyr_y_hp always exceeds 30 dps at push-off (vs 9–14 dps phase-0.10 rebound).
 *
 * Option C heel-strike inference:
 *   The 8-entry ring buffer stores rejected acc_filt threshold crossings
 *   (below→above) since the last confirmed step — ~32 bytes RAM in C.
 *   On push-off, the oldest ring entry newer than last_step_ts is used as the
 *   retrospective heel-strike timestamp passed to phase_segmenter.c via
 *   on_heel_strike(). No event contract change; no terrain classifier.
 *
 * Filter chain (unchanged from original):
 *   acc_mag → HP(0.5 Hz) → LP(15 Hz walk / 30 Hz run) = acc_filt
 *   gyr_y   → HP(0.5 Hz)                               = gyr_y_hp
 *
 * Validated: Python 18/18 tests pass. Stance error: −18 ms (flat), −35 ms (stairs).
 */

#include "step_detector.h"
#include <stdbool.h>
#include <math.h>
#include <string.h>
#include <logging/log.h>

#ifdef CONFIG_GAIT_RENODE_SIM
/*
 * VSQRT.F32 is broken in Renode 1.16.1 — the instruction returns a wrong
 * result (~1.61e9 instead of 9.81 for input 96.24).  VMUL.F32 and VDIV.F32
 * are correct.  Replace sqrtf with a Newton-Raphson implementation that
 * uses only MUL+DIV so the bug is avoided in simulation.
 * Hardware builds keep the standard sqrtf (VSQRT.F32 hardware instruction).
 */
static float sim_sqrtf(float x)
{
    if (x <= 0.0f) return 0.0f;
    union { float f; unsigned int i; } u;
    u.f = x;
    u.i = 0x1fbb4f2eu + (u.i >> 1);
    float y = u.f;
    y = 0.5f * (y + x / y);
    y = 0.5f * (y + x / y);
    y = 0.5f * (y + x / y);
    y = 0.5f * (y + x / y);
    return y;
}
#define sqrtf sim_sqrtf
#endif /* CONFIG_GAIT_RENODE_SIM */

LOG_MODULE_REGISTER(step_detector, LOG_LEVEL_DBG);

/* ------------------------------------------------------------------ */
/* Configuration                                                        */
/* ------------------------------------------------------------------ */
#define ODR_HZ               208.0f
#define DT                   (1.0f / ODR_HZ)

#define LP_WALKING_HZ        15.0f
#define LP_RUNNING_HZ        30.0f
#define CADENCE_RUN_THRESH   130.0f
#define HP_CUTOFF_HZ         0.5f

#define PEAK_HISTORY         8
/* MIN_STEP_INTERVAL_MS — statistically derived from cadence primitive.
 * Population: human ambulation (walking + running), cadence ~ N(130, 30²) spm.
 * Bound: 2.5σ upper tail → 205 spm → minimum step period 293 ms → 250 ms with margin.
 * Excluded: running downhill (>210 spm), out of scope for SI measurement device.
 * Covers >98.8% of SI-relevant ambulation patterns (3-sigma rule).
 * Traces to: Cadence primitive (Article I). Amendment 15. */
#define MIN_STEP_INTERVAL_MS 250

/* Push-off detection threshold (dps).
 * Phase-0.10 rebound: 9–14 dps (peak × 0.05) — always below → blocked.
 * True push-off:   185–280 dps (peak × 1.0)  — always above → detected.
 * Minimum push-off at v=0.1 m/s: 100 + 65*0.1 = 106 dps >> 30 dps. */
#define GYR_PUSHOFF_THRESH_DPS  30.0f

/* Option C ring buffer — rejected acc_filt crossing timestamps.
 * 8 entries × 4 bytes = 32 bytes RAM. */
#define HS_RING_SIZE         8

/* ------------------------------------------------------------------ */
/* IIR filter helpers                                                   */
/* ------------------------------------------------------------------ */
typedef struct { float x1, y1; } iir1_t;

static float lp_alpha(float fc_hz)
{
    float rc = 1.0f / (2.0f * 3.14159265f * fc_hz);
    return DT / (rc + DT);
}

static float lp_alpha_hp(float fc_hz)
{
    float rc = 1.0f / (2.0f * 3.14159265f * fc_hz);
    return rc / (rc + DT);
}

static inline float iir_lp(iir1_t *f, float x, float alpha)
{
    f->y1 = alpha * x + (1.0f - alpha) * f->y1;
    return f->y1;
}

static inline float iir_hp(iir1_t *f, float x, float alpha)
{
    float y = alpha * (f->y1 + x - f->x1);
    f->x1 = x;
    f->y1 = y;
    return y;
}

/* ------------------------------------------------------------------ */
/* State                                                                */
/* ------------------------------------------------------------------ */
static struct {
    step_cb_t   cb;

    /* acc filter chain */
    iir1_t      hp_acc;
    iir1_t      lp_acc;

    /* gyr_y HP filter */
    iir1_t      hp_gyr;

    /* Adaptive threshold */
    float       step_max_history[PEAK_HISTORY];
    int         hist_idx;

    /* Per-stance tracking */
    float       acc_peak_this_step;
    bool        acc_above;          /* acc_filt exceeded threshold this stance */
    bool        acc_was_below;      /* tracks below→above crossing for ring */
    bool        in_pushoff;         /* gyr_y_hp is above push-off threshold */

    /* Option C: ring buffer of acc_filt threshold crossing timestamps */
    float       hs_ring[HS_RING_SIZE];
    int         hs_ring_head;       /* index of oldest entry */
    int         hs_ring_count;      /* valid entries (0..HS_RING_SIZE) */

    /* Step bookkeeping */
    uint32_t    last_step_ts_ms;
    uint32_t    step_count;

    /* Cadence */
    uint32_t    interval_history[4];
    int         interval_idx;
    float       cadence_spm;
} sd;

/* ------------------------------------------------------------------ */
/* Adaptive threshold                                                   */
/* ------------------------------------------------------------------ */
static float adaptive_threshold(void)
{
    float sum = 0.0f;
    for (int i = 0; i < PEAK_HISTORY; i++) sum += sd.step_max_history[i];
    return 0.5f * (sum / PEAK_HISTORY);
}

static void record_peak(float peak)
{
    sd.step_max_history[sd.hist_idx] = peak;
    sd.hist_idx = (sd.hist_idx + 1) % PEAK_HISTORY;
}

/* ------------------------------------------------------------------ */
/* Cadence                                                              */
/* ------------------------------------------------------------------ */
static void update_cadence(uint32_t interval_ms)
{
    sd.interval_history[sd.interval_idx] = interval_ms;
    sd.interval_idx = (sd.interval_idx + 1) % 4;
    uint32_t sum = 0;
    for (int i = 0; i < 4; i++) sum += sd.interval_history[i];
    float mean_ms = (float)sum / 4.0f;
    sd.cadence_spm = (mean_ms > 0.0f) ? (60000.0f / mean_ms) : 0.0f;
}

/* ------------------------------------------------------------------ */
/* Option C ring buffer helpers                                         */
/* ------------------------------------------------------------------ */

/* Push a timestamp into the ring. Evicts oldest if full. */
static void hs_ring_push(float ts_ms)
{
    if (sd.hs_ring_count < HS_RING_SIZE) {
        int idx = (sd.hs_ring_head + sd.hs_ring_count) % HS_RING_SIZE;
        sd.hs_ring[idx] = ts_ms;
        sd.hs_ring_count++;
    } else {
        /* Full: overwrite oldest slot, advance head */
        sd.hs_ring[sd.hs_ring_head] = ts_ms;
        sd.hs_ring_head = (sd.hs_ring_head + 1) % HS_RING_SIZE;
    }
}

/* Find oldest ring entry with timestamp > since_ms.
 * Returns that timestamp, or fallback if none found. */
static float hs_ring_find_oldest_after(float since_ms, float fallback)
{
    for (int i = 0; i < sd.hs_ring_count; i++) {
        float t = sd.hs_ring[(sd.hs_ring_head + i) % HS_RING_SIZE];
        if (t > since_ms) return t;
    }
    return fallback;
}

static void hs_ring_clear(void)
{
    sd.hs_ring_head  = 0;
    sd.hs_ring_count = 0;
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
void step_detector_init(step_cb_t cb)
{
    printk("SD_INIT addr=0x%x\n", (unsigned)(uintptr_t)&sd);
    memset(&sd, 0, sizeof(sd));
    sd.cb = cb;

    /* Seed peak history → initial threshold = 5.0 m/s² */
    for (int i = 0; i < PEAK_HISTORY; i++) sd.step_max_history[i] = 10.0f;

    /* Seed cadence history at ~100 spm */
    for (int i = 0; i < 4; i++) sd.interval_history[i] = 600;
    sd.cadence_spm = 100.0f;

    sd.acc_was_below  = true;
    sd.last_step_ts_ms = (uint32_t)(-(MIN_STEP_INTERVAL_MS + 1));
}

void step_detector_reset(void)
{
    step_detector_init(sd.cb);
}

float step_detector_cadence_spm(void)
{
    return sd.cadence_spm;
}

void step_detector_update(const imu_sample_t *s)
{
    /* ── acc_filt pipeline ──────────────────────────────────────────── */
    float acc_mag = sqrtf(s->acc_x * s->acc_x +
                          s->acc_y * s->acc_y +
                          s->acc_z * s->acc_z);

    float alpha_hp  = lp_alpha_hp(HP_CUTOFF_HZ);
    float acc_hp    = iir_hp(&sd.hp_acc, acc_mag, alpha_hp);

    float fc_lp     = (sd.cadence_spm >= CADENCE_RUN_THRESH)
                       ? LP_RUNNING_HZ : LP_WALKING_HZ;
    float acc_filt  = iir_lp(&sd.lp_acc, acc_hp, lp_alpha(fc_lp));

    /* ── gyr_y HP (terrain posture component removal) ───────────────── */
    float gyr_hp = iir_hp(&sd.hp_gyr, s->gyr_y, alpha_hp);

    float thresh = adaptive_threshold();

    /* ── acc confirmation + Option C ring buffer ────────────────────── */
    if (acc_filt > thresh) {
        sd.acc_above = true;
        if (acc_filt > sd.acc_peak_this_step) {
            sd.acc_peak_this_step = acc_filt;
        }
        /* Record first below→above crossing into ring buffer.
         * These are the heel-strike candidates (rejected by original 40ms gate). */
        if (sd.acc_was_below) {
            hs_ring_push((float)s->ts_ms);
            sd.acc_was_below = false;
        }
    } else {
        sd.acc_was_below = true;
    }

    /* ── Push-off detection ─────────────────────────────────────────── */
    if (gyr_hp > GYR_PUSHOFF_THRESH_DPS) {
        sd.in_pushoff = true;
    }

    if (sd.in_pushoff && gyr_hp <= GYR_PUSHOFF_THRESH_DPS) {
        /* Falling edge of push-off burst — end of stance */
        uint32_t elapsed = s->ts_ms - sd.last_step_ts_ms;

        if (sd.acc_above && elapsed >= MIN_STEP_INTERVAL_MS) {

            record_peak(sd.acc_peak_this_step);

            if (sd.step_count > 0) {
                update_cadence(elapsed);
            }

            /* Option C: find oldest ring entry newer than last step.
             * This is the first acc_filt threshold crossing since last
             * confirmed step — the retrospective heel-strike timestamp. */
            float heel_ts = hs_ring_find_oldest_after(
                (float)sd.last_step_ts_ms,
                (float)s->ts_ms   /* fallback: push-off ts */
            );

            heel_strike_t hs = {
                .ts_ms        = (uint32_t)heel_ts,
                .step_index   = sd.step_count,
                .peak_acc_mag = sd.acc_peak_this_step,
                .peak_gyr_y   = gyr_hp,
            };

            printk("STEP #%u ts=%u acc=%d gyr_y=%d cadence=%u spm\n",
                   hs.step_index,
                   hs.ts_ms,
                   (int)(hs.peak_acc_mag * 10.0f),
                   (int)(hs.peak_gyr_y   * 10.0f),
                   (unsigned)sd.cadence_spm);

            sd.last_step_ts_ms    = s->ts_ms;   /* push-off ts for interval */
            sd.step_count++;
            sd.acc_above          = false;
            sd.acc_peak_this_step = 0.0f;
            hs_ring_clear();

            if (sd.cb) sd.cb(&hs);
        }

        sd.in_pushoff = false;
    }
}
