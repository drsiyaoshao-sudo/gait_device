/* rolling_window.cpp — ported from src/gait/rolling_window.c
 * Removed: Zephyr logging, printk
 * Unchanged: all SI computation, circular buffer, snapshot logic
 * Note: fabsf() used directly (hardware build — no Renode workaround needed)
 */
#include "rolling_window.h"
#include <math.h>
#include <string.h>

static step_record_t window[WINDOW_SIZE];
static int           win_head, win_count;
static uint32_t      total_steps;
static snapshot_cb_t snap_cb;

static uint16_t compute_si_x10(float m_odd, float m_even) {
    float denom = m_odd + m_even;
    if (denom < 1e-6f) return 0;
    float diff = m_odd - m_even;
    float si   = 200.0f * fabsf(diff) / denom;
    if (si > 200.0f) si = 200.0f;
    return (uint16_t)(si * 10.0f + 0.5f);
}

static void emit_snapshot(const step_record_t *last_rec) {
    float stance_odd=0, stance_even=0, swing_odd=0, swing_even=0;
    float angvel_odd=0, angvel_even=0, cadence_sum=0;
    int n_odd=0, n_even=0;

    for (int i=0; i<win_count; i++) {
        int idx = (win_head + i) % WINDOW_SIZE;
        const step_record_t *r = &window[idx];
        if (!(r->flags & 0x01)) continue;
        float stance = (float)r->stance_duration_ms;
        float swing  = (float)r->swing_duration_ms;
        float angvel = fabsf((float)r->peak_ang_vel_dps);
        float cad    = (float)r->cadence_spm;
        if (r->step_index & 1) { stance_odd+=stance; swing_odd+=swing; angvel_odd+=angvel; n_odd++; }
        else                   { stance_even+=stance; swing_even+=swing; angvel_even+=angvel; n_even++; }
        cadence_sum += cad;
    }
    if (n_odd)  { stance_odd/=n_odd;  swing_odd/=n_odd;  angvel_odd/=n_odd; }
    if (n_even) { stance_even/=n_even; swing_even/=n_even; angvel_even/=n_even; }

    rolling_snapshot_t snap = {
        .anchor_step_index  = last_rec->step_index,
        .anchor_ts_ms       = last_rec->heel_strike_ts_ms,
        .si_stance_x10      = compute_si_x10(stance_odd, stance_even),
        .si_swing_x10       = compute_si_x10(swing_odd,  swing_even),
        .si_peak_angvel_x10 = compute_si_x10(angvel_odd, angvel_even),
        .mean_cadence_x10   = (win_count>0) ? (uint16_t)((cadence_sum/win_count)*10.0f+0.5f) : 0,
        .step_count         = (uint8_t)(win_count>255 ? 255 : win_count),
        .flags              = (uint8_t)(((cadence_sum/win_count)>=130.0f) ? 0x02 : 0x01),
    };
    if (snap_cb) snap_cb(&snap);
}

#define PRIOR_STEPS       (SNAPSHOT_INTERVAL - 1)
#define PRIOR_STANCE_MS   343u
#define PRIOR_SWING_MS    229u
#define PRIOR_CADENCE_SPM 105u

static void seed_prior(void) {
    for (int i=0; i<PRIOR_STEPS; i++) {
        step_record_t r; memset(&r, 0, sizeof(r));
        r.step_index=i; r.stance_duration_ms=PRIOR_STANCE_MS;
        r.swing_duration_ms=PRIOR_SWING_MS;
        r.step_duration_ms=PRIOR_STANCE_MS+PRIOR_SWING_MS;
        r.cadence_spm=PRIOR_CADENCE_SPM; r.flags=0x01;
        window[i]=r;
    }
    win_count=PRIOR_STEPS;
}

void rolling_window_init(snapshot_cb_t cb) {
    memset(window, 0, sizeof(window));
    win_head=0; win_count=0; total_steps=0;
    snap_cb=cb; seed_prior();
}
void rolling_window_reset(void) { rolling_window_init(snap_cb); }

void rolling_window_add_step(const step_record_t *rec) {
    int tail = (win_head + win_count) % WINDOW_SIZE;
    window[tail] = *rec;
    if (win_count < WINDOW_SIZE) win_count++;
    else win_head = (win_head + 1) % WINDOW_SIZE;
    total_steps++;
    if ((total_steps % SNAPSHOT_INTERVAL) == 0) emit_snapshot(rec);
}

uint16_t rolling_window_si_stance_x10(void) {
    float odd=0, even=0; int n_odd=0, n_even=0;
    for (int i=0; i<win_count; i++) {
        int idx=(win_head+i)%WINDOW_SIZE;
        const step_record_t *r=&window[idx];
        if (!(r->flags & 0x01)) continue;
        if (r->step_index & 1) { odd+=r->stance_duration_ms; n_odd++; }
        else                   { even+=r->stance_duration_ms; n_even++; }
    }
    if (n_odd) odd/=n_odd; if (n_even) even/=n_even;
    return compute_si_x10(odd, even);
}
