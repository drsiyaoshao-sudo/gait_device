#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "../imu/imu_reader.h"

typedef struct {
    uint32_t ts_ms;          /* heel strike timestamp */
    uint32_t step_index;     /* monotonic step counter (0-based) */
    float    peak_acc_mag;   /* acc_mag at heel strike (m/s²) */
    float    peak_gyr_y;     /* gyr_y at heel strike (dps)    */
} heel_strike_t;

typedef void (*step_cb_t)(const heel_strike_t *hs);

/* Initialise step detector; cb is called on every confirmed heel strike. */
void step_detector_init(step_cb_t cb);

/* Feed one calibrated IMU sample; internally filters and runs FSM. */
void step_detector_update(const imu_sample_t *s);

/* Reset state (new session). */
void step_detector_reset(void);

/* Current estimated cadence in steps/min (0 if fewer than 4 steps recorded). */
float step_detector_cadence_spm(void);
