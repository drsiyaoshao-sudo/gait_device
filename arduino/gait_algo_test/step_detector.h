#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "imu_types.h"

typedef struct {
    uint32_t ts_ms;
    uint32_t step_index;
    float    peak_acc_mag;
    float    peak_gyr_y;
} heel_strike_t;

typedef void (*step_cb_t)(const heel_strike_t *hs);

void  step_detector_init(step_cb_t cb);
void  step_detector_update(const imu_sample_t *s);
void  step_detector_reset(void);
float step_detector_cadence_spm(void);
