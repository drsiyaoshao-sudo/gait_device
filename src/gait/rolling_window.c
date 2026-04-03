#include "rolling_window.h"
#include <stdbool.h>
#include <string.h>
#include <stdbool.h>
#include <math.h>
#include <logging/log.h>

LOG_MODULE_REGISTER(rolling_window, LOG_LEVEL_INF);

/* ------------------------------------------------------------------ */
/* Storage                                                              */
/* ------------------------------------------------------------------ */
static step_record_t window[WINDOW_SIZE];
static int           win_head;       /* index of oldest entry        */
static int           win_count;      /* entries currently in window  */
static uint32_t      total_steps;
static snapshot_cb_t snap_cb;

/* ------------------------------------------------------------------ */
/* SI computation helper                                               */
/* SI = 200 * |M_odd - M_even| / (M_odd + M_even)  [%× 10]           */
/* ------------------------------------------------------------------ */
static uint16_t compute_si_x10(float m_odd, float m_even)
{
    float denom = m_odd + m_even;
    if (denom < 1e-6f) return 0;
    /* BUG-013 DEMO REVERT — fabsf() restored to show VABS.F32 failure in Renode.
     * This will return SI=0.0% for all asymmetric walkers in Renode 1.16.1.
     * To restore the fix: replace fabsf(diff) with (diff >= 0.0f) ? diff : -diff */
    float diff = m_odd - m_even;
    float abs_diff = fabsf(diff);
    float si = 200.0f * abs_diff / denom;
    /* Clamp to [0, 200] and convert to ×10 */
    if (si > 200.0f) si = 200.0f;
    return (uint16_t)(si * 10.0f + 0.5f);
}

/* ------------------------------------------------------------------ */
/* Build snapshot from current window                                   */
/* ------------------------------------------------------------------ */
static void emit_snapshot(const step_record_t *last_rec)
{
    float stance_odd = 0, stance_even = 0;
    float swing_odd  = 0, swing_even  = 0;
    float angvel_odd = 0, angvel_even = 0;
    float cadence_sum = 0;
    int   n_odd = 0, n_even = 0;

    for (int i = 0; i < win_count; i++) {
        int idx = (win_head + i) % WINDOW_SIZE;
        const step_record_t *r = &window[idx];

        if (!(r->flags & 0x01)) continue;   /* skip invalid */

        float stance  = (float)r->stance_duration_ms;
        float swing   = (float)r->swing_duration_ms;
        float angvel  = fabsf((float)r->peak_ang_vel_dps);
        float cad     = (float)r->cadence_spm;

        if (r->step_index & 1) {   /* odd step */
            stance_odd  += stance;
            swing_odd   += swing;
            angvel_odd  += angvel;
            n_odd++;
        } else {                   /* even step */
            stance_even += stance;
            swing_even  += swing;
            angvel_even += angvel;
            n_even++;
        }
        cadence_sum += cad;
    }

    /* Normalise */
    if (n_odd > 0) { stance_odd /= n_odd; swing_odd /= n_odd; angvel_odd /= n_odd; }
    if (n_even > 0) { stance_even /= n_even; swing_even /= n_even; angvel_even /= n_even; }

    bool is_running = (cadence_sum / win_count) >= 130.0f;

    rolling_snapshot_t snap = {
        .anchor_step_index  = last_rec->step_index,
        .anchor_ts_ms       = last_rec->heel_strike_ts_ms,
        .si_stance_x10      = compute_si_x10(stance_odd, stance_even),
        .si_swing_x10       = compute_si_x10(swing_odd,  swing_even),
        .si_peak_angvel_x10 = compute_si_x10(angvel_odd, angvel_even),
        .mean_cadence_x10   = (uint16_t)((cadence_sum / win_count) * 10.0f + 0.5f),
        .step_count         = (uint8_t)(win_count > 255 ? 255 : win_count),
        .flags              = (uint8_t)(is_running ? 0x02 : 0x01),
    };

    /* UART parser expects: SNAPSHOT step=N si_stance=X.Y% si_swing=A.B% cadence=Z spm */
    printk("SNAPSHOT step=%u si_stance=%u.%u%% si_swing=%u.%u%% cadence=%u spm\n",
           snap.anchor_step_index,
           snap.si_stance_x10 / 10u, snap.si_stance_x10 % 10u,
           snap.si_swing_x10  / 10u, snap.si_swing_x10  % 10u,
           snap.mean_cadence_x10 / 10u);

    if (snap_cb) snap_cb(&snap);
}

/* ------------------------------------------------------------------ */
/* Flat-walker prior — CNN "same" padding for the step domain          */
/* Pre-fill the window with PRIOR_STEPS synthetic flat-walk records    */
/* so the first real snapshot has a neutral 0% SI baseline instead of  */
/* the convolution artefact from ring-buffer ghost heel-strikes.       */
/* Priors are evicted naturally as real steps fill the circular buffer. */
/* ------------------------------------------------------------------ */
#define PRIOR_STEPS       (SNAPSHOT_INTERVAL - 1)  /* 9: one less than first snap */

/* Derived from canonical flat walk (cadence=105 spm, 60/40 stance/swing split):
 *   step_period = 60000 / 105 = 571 ms
 *   stance      = 0.60 × 571  = 343 ms
 *   swing       = 0.40 × 571  = 229 ms                                         */
#define PRIOR_STANCE_MS   343u
#define PRIOR_SWING_MS    229u
#define PRIOR_CADENCE_SPM 105u

static void seed_prior(void)
{
    for (int i = 0; i < PRIOR_STEPS; i++) {
        step_record_t r;
        memset(&r, 0, sizeof(r));
        r.step_index         = (uint32_t)i;
        r.stance_duration_ms = PRIOR_STANCE_MS;
        r.swing_duration_ms  = PRIOR_SWING_MS;
        r.step_duration_ms   = PRIOR_STANCE_MS + PRIOR_SWING_MS;
        r.cadence_spm        = PRIOR_CADENCE_SPM;
        r.flags              = 0x01;   /* valid */
        window[i] = r;
    }
    win_count = PRIOR_STEPS;
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
void rolling_window_init(snapshot_cb_t cb)
{
    memset(window, 0, sizeof(window));
    win_head   = 0;
    win_count  = 0;
    total_steps = 0;
    snap_cb    = cb;
    seed_prior();
}

void rolling_window_reset(void)
{
    rolling_window_init(snap_cb);
}

void rolling_window_add_step(const step_record_t *rec)
{
    /* Insert at tail of circular buffer */
    int tail = (win_head + win_count) % WINDOW_SIZE;
    window[tail] = *rec;

    if (win_count < WINDOW_SIZE) {
        win_count++;
    } else {
        /* Evict oldest */
        win_head = (win_head + 1) % WINDOW_SIZE;
    }
    total_steps++;

    /* Emit snapshot every SNAPSHOT_INTERVAL steps */
    if ((total_steps % SNAPSHOT_INTERVAL) == 0) {
        emit_snapshot(rec);
    }
}

uint16_t rolling_window_si_stance_x10(void)
{
    float odd = 0, even = 0;
    int n_odd = 0, n_even = 0;

    for (int i = 0; i < win_count; i++) {
        int idx = (win_head + i) % WINDOW_SIZE;
        const step_record_t *r = &window[idx];
        if (!(r->flags & 0x01)) continue;
        if (r->step_index & 1) { odd  += r->stance_duration_ms; n_odd++;  }
        else                   { even += r->stance_duration_ms; n_even++; }
    }
    if (n_odd)  odd  /= n_odd;
    if (n_even) even /= n_even;
    return compute_si_x10(odd, even);
}
