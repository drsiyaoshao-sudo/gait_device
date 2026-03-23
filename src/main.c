#include <kernel.h>
#include <logging/log.h>
#include "imu/imu_reader.h"
#include "imu/calibration.h"
#include "gait/gait_engine.h"
#include "session/session_mgr.h"
#include "ble/ble_gait_svc.h"

LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

/* ------------------------------------------------------------------ */
/* IMU drain thread                                                     */
/* Highest priority — drains imu_sample_queue and feeds gait engine.   */
/* ------------------------------------------------------------------ */
static imu_calibration_t cal;

static void imu_thread_fn(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);

    imu_sample_t s;
    while (1) {
        imu_reader_get(&s);          /* blocks until sample available */
        calibration_apply(&cal, &s);
        gait_engine_update(&s);
    }
}

K_THREAD_DEFINE(imu_tid, 2048, imu_thread_fn, NULL, NULL, NULL, -2, 0, 0);

/* ------------------------------------------------------------------ */
/* Main                                                                  */
/* ------------------------------------------------------------------ */
int main(void)
{
    LOG_INF("GaitSense v0.1 — booting");

    if (imu_reader_init() != 0) {
        LOG_ERR("IMU init failed — halting");
        return -1;
    }

    /* Load calibration; run if none stored */
    if (calibration_load(&cal) != 0) {
        LOG_INF("No calibration — running now (hold still)");
        calibration_run(&cal);
    }

    session_mgr_init();

    if (ble_gait_svc_init() != 0) {
        LOG_ERR("BLE init failed");
        return -1;
    }

    LOG_INF("Boot complete — press button to start session");

    /* Main thread parks; all work done in imu_thread, session_thread, ble_thread */
    while (1) {
        k_sleep(K_SECONDS(10));
    }
    return 0;
}
