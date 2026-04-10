/* step_detector.cpp — ported from src/gait/step_detector.c
 * Removed: Zephyr logging, CONFIG_GAIT_RENODE_SIM sqrtf override, printk
 * Unchanged: all algorithm logic, thresholds, filter chain
 */
#include "step_detector.h"
#include <math.h>
#include <string.h>

#define ODR_HZ               208.0f
#define DT                   (1.0f / ODR_HZ)
#define LP_WALKING_HZ        15.0f
#define LP_RUNNING_HZ        30.0f
#define CADENCE_RUN_THRESH   130.0f
#define HP_CUTOFF_HZ         0.5f
#define PEAK_HISTORY         8
#define MIN_STEP_INTERVAL_MS 250
#define GYR_PUSHOFF_THRESH_DPS 30.0f
#define HS_RING_SIZE         8

typedef struct { float x1, y1; } iir1_t;

static float lp_alpha(float fc_hz) {
    float rc = 1.0f / (2.0f * 3.14159265f * fc_hz);
    return DT / (rc + DT);
}
static float lp_alpha_hp(float fc_hz) {
    float rc = 1.0f / (2.0f * 3.14159265f * fc_hz);
    return rc / (rc + DT);
}
static inline float iir_lp(iir1_t *f, float x, float alpha) {
    f->y1 = alpha * x + (1.0f - alpha) * f->y1;
    return f->y1;
}
static inline float iir_hp(iir1_t *f, float x, float alpha) {
    float y = alpha * (f->y1 + x - f->x1);
    f->x1 = x; f->y1 = y;
    return y;
}

static struct {
    step_cb_t   cb;
    iir1_t      hp_acc, lp_acc, hp_gyr;
    float       step_max_history[PEAK_HISTORY];
    int         hist_idx;
    float       acc_peak_this_step;
    bool        acc_above, acc_was_below, in_pushoff;
    float       hs_ring[HS_RING_SIZE];
    int         hs_ring_head, hs_ring_count;
    uint32_t    last_step_ts_ms, step_count;
    uint32_t    interval_history[4];
    int         interval_idx;
    float       cadence_spm;
} sd;

static float adaptive_threshold(void) {
    float sum = 0;
    for (int i = 0; i < PEAK_HISTORY; i++) sum += sd.step_max_history[i];
    return 0.5f * (sum / PEAK_HISTORY);
}
static void record_peak(float p) {
    sd.step_max_history[sd.hist_idx] = p;
    sd.hist_idx = (sd.hist_idx + 1) % PEAK_HISTORY;
}
static void update_cadence(uint32_t interval_ms) {
    sd.interval_history[sd.interval_idx] = interval_ms;
    sd.interval_idx = (sd.interval_idx + 1) % 4;
    uint32_t sum = 0;
    for (int i = 0; i < 4; i++) sum += sd.interval_history[i];
    float mean_ms = (float)sum / 4.0f;
    sd.cadence_spm = (mean_ms > 0.0f) ? (60000.0f / mean_ms) : 0.0f;
}
static void hs_ring_push(float ts_ms) {
    if (sd.hs_ring_count < HS_RING_SIZE) {
        int idx = (sd.hs_ring_head + sd.hs_ring_count) % HS_RING_SIZE;
        sd.hs_ring[idx] = ts_ms;
        sd.hs_ring_count++;
    } else {
        sd.hs_ring[sd.hs_ring_head] = ts_ms;
        sd.hs_ring_head = (sd.hs_ring_head + 1) % HS_RING_SIZE;
    }
}
static float hs_ring_find_oldest_after(float since_ms, float fallback) {
    for (int i = 0; i < sd.hs_ring_count; i++) {
        float t = sd.hs_ring[(sd.hs_ring_head + i) % HS_RING_SIZE];
        if (t > since_ms) return t;
    }
    return fallback;
}
static void hs_ring_clear(void) { sd.hs_ring_head = 0; sd.hs_ring_count = 0; }

void step_detector_init(step_cb_t cb) {
    memset(&sd, 0, sizeof(sd));
    sd.cb = cb;
    for (int i = 0; i < PEAK_HISTORY; i++) sd.step_max_history[i] = 10.0f;
    for (int i = 0; i < 4; i++) sd.interval_history[i] = 600;
    sd.cadence_spm = 100.0f;
    sd.acc_was_below = true;
    sd.last_step_ts_ms = (uint32_t)(-(MIN_STEP_INTERVAL_MS + 1));
}
void step_detector_reset(void) { step_detector_init(sd.cb); }
float step_detector_cadence_spm(void) { return sd.cadence_spm; }

void step_detector_update(const imu_sample_t *s) {
    float acc_mag = sqrtf(s->acc_x*s->acc_x + s->acc_y*s->acc_y + s->acc_z*s->acc_z);
    float alpha_hp = lp_alpha_hp(HP_CUTOFF_HZ);
    float acc_hp   = iir_hp(&sd.hp_acc, acc_mag, alpha_hp);
    float fc_lp    = (sd.cadence_spm >= CADENCE_RUN_THRESH) ? LP_RUNNING_HZ : LP_WALKING_HZ;
    float acc_filt = iir_lp(&sd.lp_acc, acc_hp, lp_alpha(fc_lp));
    float gyr_hp   = iir_hp(&sd.hp_gyr, s->gyr_y, alpha_hp);
    float thresh   = adaptive_threshold();

    if (acc_filt > thresh) {
        sd.acc_above = true;
        if (acc_filt > sd.acc_peak_this_step) sd.acc_peak_this_step = acc_filt;
        if (sd.acc_was_below) { hs_ring_push((float)s->ts_ms); sd.acc_was_below = false; }
    } else {
        sd.acc_was_below = true;
    }

    if (gyr_hp > GYR_PUSHOFF_THRESH_DPS) sd.in_pushoff = true;

    if (sd.in_pushoff && gyr_hp <= GYR_PUSHOFF_THRESH_DPS) {
        uint32_t elapsed = s->ts_ms - sd.last_step_ts_ms;
        if (sd.acc_above && elapsed >= MIN_STEP_INTERVAL_MS) {
            record_peak(sd.acc_peak_this_step);
            if (sd.step_count > 0) update_cadence(elapsed);
            float heel_ts = hs_ring_find_oldest_after((float)sd.last_step_ts_ms, (float)s->ts_ms);
            heel_strike_t hs = {
                .ts_ms        = (uint32_t)heel_ts,
                .step_index   = sd.step_count,
                .peak_acc_mag = sd.acc_peak_this_step,
                .peak_gyr_y   = gyr_hp,
            };
            sd.last_step_ts_ms    = s->ts_ms;
            sd.step_count++;
            sd.acc_above          = false;
            sd.acc_peak_this_step = 0.0f;
            hs_ring_clear();
            if (sd.cb) sd.cb(&hs);
        }
        sd.in_pushoff = false;
    }
}
