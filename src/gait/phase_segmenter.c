#include "phase_segmenter.h"
#include <stdbool.h>
#include "foot_angle.h"
#include <stdbool.h>
#include "step_detector.h"
#include <math.h>
#include <string.h>
#include <logging/log.h>

LOG_MODULE_REGISTER(phase_seg, LOG_LEVEL_DBG);

/* ------------------------------------------------------------------ */
/* Thresholds                                                           */
/* ------------------------------------------------------------------ */
#define ACC_MID_STANCE_FRAC     0.85f   /* acc_z > 0.85 * 9.81 */
#define ACC_MAG_HP_MID_THRESH   2.94f   /* ~0.3g in m/s² */
#define GYR_MID_TO_TERM_DPS     (-10.0f)
#define ACC_Z_DERIV_WIN_MS      20
#define PUSH_OFF_GYR_DEFAULT    80.0f   /* dps — foot departing ground */
#define ACC_Z_TOE_OFF           2.94f   /* ~0.3g */
#define MOUNTING_SUSPECT_DEG    15.0f   /* mid-stance acc_z deviation threshold */

/* ------------------------------------------------------------------ */
/* State                                                                */
/* ------------------------------------------------------------------ */
static struct {
    step_record_cb_t cb;
    gait_phase_t     phase;

    step_record_t    cur;           /* being filled for current step */
    step_record_t    prev;          /* completed previous step */

    uint32_t         phase_entry_ts;
    float            acc_z_lp_prev;
    uint32_t         acc_z_neg_deriv_start_ts;

    /* Adaptive push-off threshold: mean |gyr_y| at last 4 toe-offs */
    float            pushoff_thresh_history[4];
    int              pushoff_idx;
    float            pushoff_thresh;

    bool             first_step;
} ps;

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */
static float pushoff_adaptive_thresh(void)
{
    float sum = 0;
    for (int i = 0; i < 4; i++) sum += ps.pushoff_thresh_history[i];
    return sum / 4.0f;
}

static void record_pushoff(float gyr_abs)
{
    ps.pushoff_thresh_history[ps.pushoff_idx] = gyr_abs;
    ps.pushoff_idx = (ps.pushoff_idx + 1) % 4;
    ps.pushoff_thresh = pushoff_adaptive_thresh();
}

static void transition(gait_phase_t next, uint32_t ts)
{
    ps.phase = next;
    ps.phase_entry_ts = ts;
}

static void emit_step(uint32_t swing_end_ts)
{
    ps.cur.swing_duration_ms  = (uint16_t)(swing_end_ts - ps.phase_entry_ts);
    ps.cur.step_duration_ms   = ps.cur.stance_duration_ms + ps.cur.swing_duration_ms;
    ps.cur.flags |= 0x01;   /* valid */

    LOG_DBG("STEP #%u stance=%u swing=%u fa_ic=%d fa_to=%d peak_gyr=%d",
            ps.cur.step_index,
            ps.cur.stance_duration_ms,
            ps.cur.swing_duration_ms,
            ps.cur.foot_angle_ic_cdeg,
            ps.cur.foot_angle_to_cdeg,
            ps.cur.peak_ang_vel_dps);

    if (ps.cb) ps.cb(&ps.cur);
    ps.prev = ps.cur;
    memset(&ps.cur, 0, sizeof(ps.cur));
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
void phase_segmenter_init(step_record_cb_t cb)
{
    memset(&ps, 0, sizeof(ps));
    ps.cb            = cb;
    ps.phase         = PHASE_IDLE;
    ps.first_step    = true;
    ps.pushoff_thresh = PUSH_OFF_GYR_DEFAULT;
    for (int i = 0; i < 4; i++) ps.pushoff_thresh_history[i] = PUSH_OFF_GYR_DEFAULT;
}

void phase_segmenter_reset(void)
{
    phase_segmenter_init(ps.cb);
}

gait_phase_t phase_segmenter_current_phase(void)
{
    return ps.phase;
}

void phase_segmenter_on_heel_strike(const heel_strike_t *hs)
{
    if (ps.phase == PHASE_SWING || ps.phase == PHASE_IDLE) {
        if (ps.phase == PHASE_SWING) {
            emit_step(hs->ts_ms);
        }

        /* Start new step record */
        ps.cur.step_index        = hs->step_index;
        ps.cur.heel_strike_ts_ms = hs->ts_ms;
        ps.cur.peak_ang_vel_dps  = (int16_t)hs->peak_gyr_y;

        float fa_ic = foot_angle_get();
        ps.cur.foot_angle_ic_cdeg = (int16_t)(fa_ic * 100.0f);

        transition(PHASE_LOADING, hs->ts_ms);
    }
}

void phase_segmenter_update(const imu_sample_t *s)
{
    float acc_z   = s->acc_z;
    float acc_mag = sqrtf(s->acc_x*s->acc_x + s->acc_y*s->acc_y + acc_z*acc_z);
    float gyr_y   = s->gyr_y;

    /* Low-pass acc_z for mid-stance check */
    float acc_z_lp = 0.9f * ps.acc_z_lp_prev + 0.1f * acc_z;

    /* Track peak |gyr_y| during current step for push-off detection */
    if (fabsf(gyr_y) > fabsf((float)ps.cur.peak_ang_vel_dps)) {
        ps.cur.peak_ang_vel_dps = (int16_t)gyr_y;
    }

    switch (ps.phase) {

    case PHASE_LOADING:
        /* Wait for stable ground contact */
        if (acc_z_lp > (0.85f * 9.81f) && acc_mag < ACC_MAG_HP_MID_THRESH) {
            transition(PHASE_MID_STANCE, s->ts_ms);
        }
        break;

    case PHASE_MID_STANCE: {
        /* Check for mounting error: acc_z should be close to 9.81 at mid-stance */
        float acc_z_angle = atan2f(acc_z_lp, 9.81f) * 57.2958f;
        if (fabsf(acc_z_angle) > MOUNTING_SUSPECT_DEG) {
            ps.cur.flags |= 0x02;   /* mounting_suspect */
        }

        /* acc_z derivative going negative for 20ms → terminal stance */
        if (acc_z_lp < ps.acc_z_lp_prev && gyr_y < GYR_MID_TO_TERM_DPS) {
            if (ps.acc_z_neg_deriv_start_ts == 0) {
                ps.acc_z_neg_deriv_start_ts = s->ts_ms;
            } else if ((s->ts_ms - ps.acc_z_neg_deriv_start_ts) >= 20) {
                ps.acc_z_neg_deriv_start_ts = 0;
                transition(PHASE_TERMINAL, s->ts_ms);
            }
        } else {
            ps.acc_z_neg_deriv_start_ts = 0;
        }
        break;
    }

    case PHASE_TERMINAL: {
        /* Toe-off: strong plantar push OR foot leaves ground */
        bool push_off_gyr = fabsf(gyr_y) > ps.pushoff_thresh;
        bool foot_leaving = acc_z_lp < ACC_Z_TOE_OFF;

        if (push_off_gyr || foot_leaving) {
            record_pushoff(fabsf(gyr_y));
            ps.cur.stance_duration_ms = (uint16_t)(s->ts_ms - ps.cur.heel_strike_ts_ms);

            float fa_to = foot_angle_get();
            ps.cur.foot_angle_to_cdeg = (int16_t)(fa_to * 100.0f);

            transition(PHASE_TOE_OFF, s->ts_ms);
        }
        break;
    }

    case PHASE_TOE_OFF:
        /* Automatic — swing begins immediately */
        transition(PHASE_SWING, s->ts_ms);
        break;

    case PHASE_SWING:
        /* Wait for next heel strike (handled in on_heel_strike) */
        break;

    case PHASE_IDLE:
        break;
    }

    ps.acc_z_lp_prev = acc_z_lp;
}
