#include "calibration.h"
#include <stdbool.h>
#include <kernel.h>
#include <drivers/sensor.h>
#include <logging/log.h>
#include <math.h>
#include <string.h>
#ifndef CONFIG_GAIT_RENODE_SIM
#include <fs/nvs.h>
#include <storage/flash_map.h>
#endif

LOG_MODULE_REGISTER(calibration, LOG_LEVEL_INF);

#define CAL_SAMPLES     400
#define NVS_CAL_ID      1       /* NVS key for calibration struct */
#define NVS_SECTOR_SIZE 0x1000  /* 4 KB — standard nRF52840 flash sector */
#define NVS_SECTOR_CNT  2

#ifndef CONFIG_GAIT_RENODE_SIM
static struct nvs_fs nvs;

/*
 * Open the 'storage' flash partition and initialise NVS on it.
 * Zephyr 2.7.1 API: flash_area_open() + nvs_init(dev_name).
 */
static int nvs_open_partition(void)
{
    const struct flash_area *fa;
    int rc = flash_area_open(FLASH_AREA_ID(storage), &fa);
    if (rc < 0) {
        LOG_WRN("No storage partition — NVS disabled (rc=%d)", rc);
        return rc;
    }

    nvs.offset       = fa->fa_off;
    nvs.sector_size  = NVS_SECTOR_SIZE;
    nvs.sector_count = NVS_SECTOR_CNT;

    const char *dev_name = fa->fa_dev_name;
    flash_area_close(fa);

    return nvs_init(&nvs, dev_name);
}
#endif /* CONFIG_GAIT_RENODE_SIM */

int calibration_run(imu_calibration_t *cal)
{
    double acc_sum[3] = {0}, gyr_sum[3] = {0};
    imu_sample_t s;

    LOG_INF("Calibrating — hold device still for ~2 seconds");

    for (int i = 0; i < CAL_SAMPLES; i++) {
        imu_reader_get(&s);
        acc_sum[0] += s.acc_x;
        acc_sum[1] += s.acc_y;
        acc_sum[2] += s.acc_z;
        gyr_sum[0] += s.gyr_x;
        gyr_sum[1] += s.gyr_y;
        gyr_sum[2] += s.gyr_z;
    }

    cal->acc_bias[0] = (float)(acc_sum[0] / CAL_SAMPLES);
    cal->acc_bias[1] = (float)(acc_sum[1] / CAL_SAMPLES);
    /* Z: remove the 1g gravity component so pure acc_z tilt reads 0 */
    cal->acc_bias[2] = (float)(acc_sum[2] / CAL_SAMPLES) - 9.81f;

    cal->gyr_bias[0] = (float)(gyr_sum[0] / CAL_SAMPLES);
    cal->gyr_bias[1] = (float)(gyr_sum[1] / CAL_SAMPLES);
    cal->gyr_bias[2] = (float)(gyr_sum[2] / CAL_SAMPLES);
    cal->valid = true;

    LOG_INF("Cal done: acc_bias=[%.3f %.3f %.3f] gyr_bias=[%.3f %.3f %.3f]",
            (double)cal->acc_bias[0], (double)cal->acc_bias[1], (double)cal->acc_bias[2],
            (double)cal->gyr_bias[0], (double)cal->gyr_bias[1], (double)cal->gyr_bias[2]);

    /* Best-effort NVS persist — non-fatal if partition missing */
#ifndef CONFIG_GAIT_RENODE_SIM
    if (nvs_open_partition() == 0) {
        nvs_write(&nvs, NVS_CAL_ID, cal, sizeof(*cal));
    }
#endif
    return 0;
}

int calibration_load(imu_calibration_t *cal)
{
#ifdef CONFIG_GAIT_RENODE_SIM
    /* In Renode sim mode: skip NVS entirely.  Sim samples from walker_model
     * are already calibrated (zero bias by construction), so return a zero-bias
     * calibration immediately.  This prevents calibration_run() from consuming
     * sim samples that the gait algorithm needs. */
    memset(cal, 0, sizeof(*cal));
    cal->valid = true;
    LOG_INF("Calibration: sim mode — zero biases (NVS skipped)");
    return 0;
#else
    int rc = nvs_open_partition();
    if (rc != 0) {
        return rc;
    }
    ssize_t n = nvs_read(&nvs, NVS_CAL_ID, cal, sizeof(*cal));
    if (n != sizeof(*cal) || !cal->valid) {
        memset(cal, 0, sizeof(*cal));
        return -ENOENT;
    }
    LOG_INF("Calibration loaded from NVS");
    return 0;
#endif
}

void calibration_apply(const imu_calibration_t *cal, imu_sample_t *s)
{
    s->acc_x -= cal->acc_bias[0];
    s->acc_y -= cal->acc_bias[1];
    s->acc_z -= cal->acc_bias[2];
    s->gyr_x -= cal->gyr_bias[0];
    s->gyr_y -= cal->gyr_bias[1];
    s->gyr_z -= cal->gyr_bias[2];
}
