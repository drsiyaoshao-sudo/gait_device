#pragma once
#include "rolling_window.h"

/* Initialise all gait sub-modules and wire them together. */
int gait_engine_init(snapshot_cb_t on_snapshot);

/* Feed one calibrated IMU sample through the full pipeline. */
void gait_engine_update(const imu_sample_t *s);

/* Start/stop a session. */
void gait_engine_session_start(void);
void gait_engine_session_stop(void);

/* Retrieve total step count for current session. */
uint32_t gait_engine_step_count(void);
