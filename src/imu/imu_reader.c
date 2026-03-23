#include "imu_reader.h"
#include <kernel.h>
#include <device.h>
#include <drivers/sensor.h>
#include <logging/log.h>

LOG_MODULE_REGISTER(imu_reader, LOG_LEVEL_INF);

/*
 * Zephyr 2.7.1 LSM6DSO driver supports SENSOR_TRIG_DATA_READY only.
 * We collect individual samples from the DATA_READY trigger and enqueue them.
 * The gait_engine processes them one-by-one (same as FIFO drain, just finer).
 * BATCH_SIZE is kept for logging — no functional difference from a FIFO batch.
 */
#define BATCH_SIZE          32      /* log interval: ~154ms at 208 Hz */
#define QUEUE_DEPTH         64      /* imu_sample_t entries in msgq   */

static const struct device *imu_dev;
static int batch_count;

/* Inter-thread queue: trigger callback → gait_thread */
K_MSGQ_DEFINE(imu_sample_queue, sizeof(imu_sample_t), QUEUE_DEPTH, 4);

/* ------------------------------------------------------------------ */
/* DATA_READY trigger callback                                          */
/* ------------------------------------------------------------------ */
static void drdy_trigger_cb(const struct device *dev,
                             const struct sensor_trigger *trig)
{
    struct sensor_value acc[3], gyr[3];
    imu_sample_t s;

    if (sensor_sample_fetch(dev) != 0) {
        return;
    }
    sensor_channel_get(dev, SENSOR_CHAN_ACCEL_XYZ, acc);
    sensor_channel_get(dev, SENSOR_CHAN_GYRO_XYZ,  gyr);

    s.acc_x = sensor_value_to_double(&acc[0]);
    s.acc_y = sensor_value_to_double(&acc[1]);
    s.acc_z = sensor_value_to_double(&acc[2]);
    s.gyr_x = sensor_value_to_double(&gyr[0]);
    s.gyr_y = sensor_value_to_double(&gyr[1]);
    s.gyr_z = sensor_value_to_double(&gyr[2]);
    s.ts_ms = k_uptime_get_32();

    if (k_msgq_put(&imu_sample_queue, &s, K_NO_WAIT) != 0) {
        LOG_WRN("imu_sample_queue full — dropping sample");
    }

    if (++batch_count >= BATCH_SIZE) {
        batch_count = 0;
        LOG_DBG("batch complete (%d samples ~%dms)", BATCH_SIZE,
                (int)(BATCH_SIZE * 1000U / 208U));
    }
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
int imu_reader_init(void)
{
    /* st_lsm6dso matches compatible = "st,lsm6dso" in the overlay */
    imu_dev = DEVICE_DT_GET_ANY(st_lsm6dso);
    if (!device_is_ready(imu_dev)) {
        LOG_ERR("LSM6DSO not ready");
        return -ENODEV;
    }

    batch_count = 0;

    static struct sensor_trigger trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_ALL,
    };

    if (sensor_trigger_set(imu_dev, &trig, drdy_trigger_cb) != 0) {
        LOG_ERR("Failed to set DATA_READY trigger");
        return -EIO;
    }

    LOG_INF("IMU ready — DATA_READY @ 208 Hz (batch log every %d samples ~%dms)",
            BATCH_SIZE, (int)(BATCH_SIZE * 1000U / 208U));
    return 0;
}

int imu_reader_get(imu_sample_t *out)
{
    return k_msgq_get(&imu_sample_queue, out, K_FOREVER);
}
