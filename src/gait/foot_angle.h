#pragma once
#include "../imu/imu_reader.h"

/* Complementary filter: 0.98 gyro + 0.02 gravity.
 * Crossover ~0.64 Hz — tracks slow postural angle, rejects gyro drift. */

void foot_angle_init(void);
void foot_angle_update(const imu_sample_t *s);
float foot_angle_get(void);   /* degrees; + = dorsiflexed */
void foot_angle_reset(void);
