#include "gait_engine.h"
#include <stdbool.h>
#include "step_detector.h"
#include "phase_segmenter.h"
#include "foot_angle.h"
#include "rolling_window.h"
#include <logging/log.h>
#include <sys/printk.h>

LOG_MODULE_REGISTER(gait_engine, LOG_LEVEL_INF);

static bool      session_active;
static uint32_t  step_count;

/* ------------------------------------------------------------------ */
/* Internal callbacks                                                   */
/* ------------------------------------------------------------------ */
static void on_heel_strike(const heel_strike_t *hs)
{
    if (!session_active) return;
    step_count++;
    phase_segmenter_on_heel_strike(hs);
}

static void on_step_record(const step_record_t *rec)
{
    rolling_window_add_step(rec);
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
int gait_engine_init(snapshot_cb_t on_snapshot)
{
    foot_angle_init();
    step_detector_init(on_heel_strike);
    phase_segmenter_init(on_step_record);
    rolling_window_init(on_snapshot);
    session_active = false;
    step_count = 0;
    return 0;
}

void gait_engine_update(const imu_sample_t *s)
{
    if (!session_active) return;
    foot_angle_update(s);
    step_detector_update(s);
    phase_segmenter_update(s);
}

void gait_engine_session_start(void)
{
    step_detector_reset();
    phase_segmenter_reset();
    foot_angle_reset();
    rolling_window_reset();
    step_count = 0;
    session_active = true;
    LOG_INF("Session started");
}

void gait_engine_session_stop(void)
{
    session_active = false;
    LOG_INF("Session stopped — total steps: %u", step_count);
    printk("SESSION_END steps=%u\n", step_count);
}

uint32_t gait_engine_step_count(void)
{
    return step_count;
}
