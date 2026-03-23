#pragma once
#include <stdint.h>

/*
 * IMU sample as read from LSM6DS3TR-C FIFO.
 * All values in SI units after driver conversion:
 *   acc:  m/s²   (float)
 *   gyro: dps    (float)
 */
typedef struct {
    float acc_x;
    float acc_y;
    float acc_z;
    float gyr_x;
    float gyr_y;
    float gyr_z;
    uint32_t ts_ms;   /* k_uptime_get_32() at drain time */
} imu_sample_t;

/* Initialise IMU driver, configure FIFO watermark trigger. */
int imu_reader_init(void);

/* Called from gait_thread: blocks until a sample is available. */
int imu_reader_get(imu_sample_t *out);
