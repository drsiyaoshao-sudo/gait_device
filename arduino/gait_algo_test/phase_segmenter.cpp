/* phase_segmenter.cpp — ported from src/gait/phase_segmenter.c
 * Removed: Zephyr logging, foot_angle (stub returns 0), printk
 * Unchanged: all FSM logic, thresholds
 */
#include "phase_segmenter.h"
#include <math.h>
#include <string.h>

#define ACC_MID_STANCE_FRAC     0.85f
#define GYR_LOADING_TO_MID_DPS  20.0f
#define GYR_MID_TO_TERM_DPS    (-10.0f)
#define PUSH_OFF_GYR_DEFAULT    80.0f
#define ACC_Z_TOE_OFF           2.94f

typedef enum { PHASE_IDLE, PHASE_LOADING, PHASE_MID_STANCE, PHASE_TERMINAL, PHASE_TOE_OFF, PHASE_SWING } gait_phase_t;

static struct {
    step_record_cb_t cb;
    gait_phase_t     phase;
    step_record_t    cur, prev;
    uint32_t         phase_entry_ts;
    float            acc_z_lp_prev;
    uint32_t         acc_z_neg_deriv_start_ts;
    float            pushoff_thresh_history[4];
    int              pushoff_idx;
    float            pushoff_thresh;
    bool             first_step;
} ps;

static float pushoff_adaptive_thresh(void) {
    float sum = 0;
    for (int i = 0; i < 4; i++) sum += ps.pushoff_thresh_history[i];
    return sum / 4.0f;
}
static void record_pushoff(float g) {
    ps.pushoff_thresh_history[ps.pushoff_idx] = g;
    ps.pushoff_idx = (ps.pushoff_idx + 1) % 4;
    ps.pushoff_thresh = pushoff_adaptive_thresh();
}
static void transition(gait_phase_t next, uint32_t ts) { ps.phase = next; ps.phase_entry_ts = ts; }

static void emit_step(uint32_t swing_end_ts) {
    ps.cur.swing_duration_ms = (uint16_t)(swing_end_ts - ps.phase_entry_ts);
    ps.cur.step_duration_ms  = ps.cur.stance_duration_ms + ps.cur.swing_duration_ms;
    ps.cur.flags |= 0x01;
    if (ps.cb) ps.cb(&ps.cur);
    ps.prev = ps.cur;
    memset(&ps.cur, 0, sizeof(ps.cur));
}

void phase_segmenter_init(step_record_cb_t cb) {
    memset(&ps, 0, sizeof(ps));
    ps.cb = cb;
    ps.phase = PHASE_IDLE;
    ps.first_step = true;
    ps.pushoff_thresh = PUSH_OFF_GYR_DEFAULT;
    for (int i = 0; i < 4; i++) ps.pushoff_thresh_history[i] = PUSH_OFF_GYR_DEFAULT;
    ps.acc_z_lp_prev = 9.81f;
}
void phase_segmenter_reset(void) { phase_segmenter_init(ps.cb); }

void phase_segmenter_on_heel_strike(const heel_strike_t *hs) {
    if (ps.phase == PHASE_SWING || ps.phase == PHASE_IDLE) {
        if (ps.phase == PHASE_SWING) emit_step(hs->ts_ms);
        ps.cur.step_index        = hs->step_index;
        ps.cur.heel_strike_ts_ms = hs->ts_ms;
        ps.cur.peak_ang_vel_dps  = (int16_t)hs->peak_gyr_y;
        ps.cur.foot_angle_ic_cdeg = 0;  /* foot_angle stub */
        transition(PHASE_LOADING, hs->ts_ms);
    }
}

void phase_segmenter_update(const imu_sample_t *s) {
    float acc_z    = s->acc_z;
    float gyr_y    = s->gyr_y;
    float acc_z_lp = 0.5f * ps.acc_z_lp_prev + 0.5f * acc_z;

    if (fabsf(gyr_y) > fabsf((float)ps.cur.peak_ang_vel_dps))
        ps.cur.peak_ang_vel_dps = (int16_t)gyr_y;

    switch (ps.phase) {
    case PHASE_LOADING:
        if (acc_z_lp > (0.85f * 9.81f) && fabsf(gyr_y) < GYR_LOADING_TO_MID_DPS)
            transition(PHASE_MID_STANCE, s->ts_ms);
        break;
    case PHASE_MID_STANCE:
        if (acc_z_lp < ps.acc_z_lp_prev && gyr_y < GYR_MID_TO_TERM_DPS) {
            if (ps.acc_z_neg_deriv_start_ts == 0) {
                ps.acc_z_neg_deriv_start_ts = s->ts_ms;
            } else if ((s->ts_ms - ps.acc_z_neg_deriv_start_ts) >= 5) {
                ps.acc_z_neg_deriv_start_ts = 0;
                transition(PHASE_TERMINAL, s->ts_ms);
            }
        } else { ps.acc_z_neg_deriv_start_ts = 0; }
        break;
    case PHASE_TERMINAL: {
        bool push_off = fabsf(gyr_y) > ps.pushoff_thresh;
        bool leaving  = acc_z_lp < ACC_Z_TOE_OFF;
        if (push_off || leaving) {
            record_pushoff(fabsf(gyr_y));
            ps.cur.stance_duration_ms = (uint16_t)(s->ts_ms - ps.cur.heel_strike_ts_ms);
            ps.cur.foot_angle_to_cdeg = 0;  /* foot_angle stub */
            transition(PHASE_TOE_OFF, s->ts_ms);
        }
        break;
    }
    case PHASE_TOE_OFF:
        transition(PHASE_SWING, s->ts_ms);
        break;
    default: break;
    }
    ps.acc_z_lp_prev = acc_z_lp;
}
