#pragma once
#include "imu_reader.h"
#include <stdbool.h>

typedef struct {
    float acc_bias[3];   /* m/s²  — subtract from raw acc */
    float gyr_bias[3];   /* dps   — subtract from raw gyro */
    bool  valid;
} imu_calibration_t;

/* Collect 400 stationary samples, compute bias, persist to NVS. */
int calibration_run(imu_calibration_t *cal);

/* Load from NVS; returns 0 on success, -ENOENT if not yet calibrated. */
int calibration_load(imu_calibration_t *cal);

/* Apply stored calibration to a raw sample (in-place). */
void calibration_apply(const imu_calibration_t *cal, imu_sample_t *s);
