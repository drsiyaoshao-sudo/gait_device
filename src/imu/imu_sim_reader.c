/*
 * Simulation-mode IMU reader — compiled only when CONFIG_GAIT_RENODE_SIM=y.
 *
 * Polls a Renode Python.PythonPeripheral at sysbus address 0x400B0000.
 * Register layout (byte offsets):
 *   0x00-0x03  STATUS uint32 LE  (1 = sample ready, 0 = no more samples)
 *   0x04-0x1B  float32[6] LE    (ax ay az gx gy gz in m/s² and dps)
 *   0x1C       ACK byte          (write any value to advance to next sample)
 *
 * Caller contract: identical to imu_reader.c (imu_reader_init / imu_reader_get).
 * Uses k_usleep(4807) per sample to simulate 208 Hz sampling rate so that
 * k_uptime_get_32() timestamps in step records match real-time expectations.
 */

#include "imu_reader.h"
#include <kernel.h>
#include <string.h>
#include <sys/printk.h>
#include <logging/log.h>

LOG_MODULE_REGISTER(imu_sim_reader, LOG_LEVEL_INF);

/*
 * Zephyr minimal libc does not export __errno() that newlib-style libm.a
 * references from sqrtf/atanf error paths.  Provide a weak stub that points
 * at the current thread's errno so the linker is satisfied without requiring
 * CONFIG_NEWLIB_LIBC.
 */
#include <errno.h>
__attribute__((weak)) int *__errno(void) { return &errno; }

/* ------------------------------------------------------------------ */
/* Stub peripheral address                                              */
/* ------------------------------------------------------------------ */
#define SIM_BASE        0x400B0000UL
#define SIM_OFF_STATUS  0x00
#define SIM_OFF_DATA    0x04   /* 24 bytes: ax ay az gx gy gz float32 LE */
#define SIM_OFF_ACK     0x1C

static volatile uint8_t * const _sim = (volatile uint8_t *)SIM_BASE;

/* Set to true once the stub STATUS register returns 0 (all samples consumed). */
volatile bool g_imu_sim_exhausted = false;

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
int imu_reader_init(void)
{
    printk("IMU: simulation mode (stub @ 0x%08lX)\n", (unsigned long)SIM_BASE);
    LOG_INF("IMU sim reader ready — polling sysbus 0x%08lX", (unsigned long)SIM_BASE);
    return 0;
}

int imu_reader_get(imu_sample_t *out)
{
    uint32_t status;

    /* Busy-wait for sample with 5ms yields when empty.
     * The k_sleep(K_MSEC(5)) when empty ensures session_thread (priority 0)
     * can run to process button events even after all samples are consumed. */
    for (;;) {
        memcpy(&status, (void *)(_sim + SIM_OFF_STATUS), sizeof(status));
        if (status) {
            break;
        }
        g_imu_sim_exhausted = true;
        k_sleep(K_MSEC(5));
    }

    /* Simulate 208 Hz sampling interval so timestamps are correct.
     * 1/208 s ≈ 4807 µs per sample. */
    k_usleep(4807);

    /* Read 6 float32 values (ax ay az gx gy gz). */
    float vals[6];
    memcpy(vals, (void *)(_sim + SIM_OFF_DATA), sizeof(vals));

    out->acc_x = vals[0];
    out->acc_y = vals[1];
    out->acc_z = vals[2];
    out->gyr_x = vals[3];
    out->gyr_y = vals[4];
    out->gyr_z = vals[5];
    out->ts_ms = k_uptime_get_32();

    /* Debug: print raw az bits for first 5 samples to check stub data */
    {
        static int _dbg_cnt = 0;
        if (_dbg_cnt < 5) {
            uint32_t az_bits, ax_bits;
            memcpy(&az_bits, &vals[2], 4);
            memcpy(&ax_bits, &vals[0], 4);
            printk("RAW ts=%u ax_bits=0x%x az_bits=0x%x\n",
                   out->ts_ms, (unsigned)ax_bits, (unsigned)az_bits);
            _dbg_cnt++;
        }
    }

    /* Acknowledge: advance stub to next sample. */
    _sim[SIM_OFF_ACK] = 1;

    return 0;
}
