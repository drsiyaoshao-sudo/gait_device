#pragma once
#include <stdint.h>

typedef struct {
    float    acc_x, acc_y, acc_z;   /* m/s² */
    float    gyr_x, gyr_y, gyr_z;   /* dps  */
    uint32_t ts_ms;
} imu_sample_t;
