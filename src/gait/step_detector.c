#include "step_detector.h"
#include <stdbool.h>
#include <math.h>
#include <stdbool.h>
#include <string.h>
#include <logging/log.h>

#ifdef CONFIG_GAIT_RENODE_SIM
/*
 * VSQRT.F32 is broken in Renode 1.16.1 — the instruction returns a wrong
 * result (~1.61e9 instead of 9.81 for input 96.24).  VMUL.F32 and VDIV.F32
 * are correct.  Replace sqrtf with a Newton-Raphson implementation that
 * uses only MUL+DIV so the bug is avoided in simulation.
 * Hardware builds keep the standard sqrtf (VSQRT.F32 hardware instruction).
 */
static float sim_sqrtf(float x)
{
    if (x <= 0.0f) return 0.0f;
    /* Initial approximation via integer bit manipulation (no FPU instructions) */
    union { float f; unsigned int i; } u;
    u.f = x;
    u.i = 0x1fbb4f2eu + (u.i >> 1);   /* ~3% error — good enough as NR seed */
    float y = u.f;
    /* 4 Newton-Raphson iterations: y = 0.5*(y + x/y) */
    y = 0.5f * (y + x / y);
    y = 0.5f * (y + x / y);
    y = 0.5f * (y + x / y);
    y = 0.5f * (y + x / y);
    return y;
}
#define sqrtf sim_sqrtf
#endif /* CONFIG_GAIT_RENODE_SIM */

LOG_MODULE_REGISTER(step_detector, LOG_LEVEL_DBG);

/* ------------------------------------------------------------------ */
/* Configuration                                                        */
/* ------------------------------------------------------------------ */
#define ODR_HZ              208.0f
#define DT                  (1.0f / ODR_HZ)

/* Adaptive LP filter cutoffs */
#define LP_WALKING_HZ       15.0f   /* cadence < 130 spm */
#define LP_RUNNING_HZ       30.0f   /* cadence >= 130 spm */
#define CADENCE_RUN_THRESH  130.0f

/* HP filter: 0.5 Hz removes gravity */
#define HP_CUTOFF_HZ        0.5f

/* Peak detection */
#define PEAK_HISTORY        8       /* steps for adaptive threshold */
#define MIN_STEP_INTERVAL_MS 250    /* 240 spm max */

/* Gyro zero-crossing confirmation window */
#define GYR_CONFIRM_MS      40

/* Minimum |gyr_y| at the acc peak to attempt gyro confirmation.
 * Real heel strikes produce 30–150 dps of dorsiflexion; noise is <0.1 dps.
 * This gate prevents noise-driven false positives when acc_filt peaks in a
 * region of near-zero angular velocity (e.g. at firmware startup). */
#define GYR_MIN_CONFIRM_DPS 5.0f

/* ------------------------------------------------------------------ */
/* IIR biquad helpers (Direct Form I)                                   */
/* Single-pole IIR approximation for embedded simplicity.               */
/* ------------------------------------------------------------------ */
typedef struct { float x1, y1; } iir1_t;

/* Compute coefficient for single-pole IIR LP: α = 2πfc/fs */
static float lp_alpha(float fc_hz)
{
    float rc = 1.0f / (2.0f * 3.14159265f * fc_hz);
    return DT / (rc + DT);
}

static float lp_alpha_hp(float fc_hz)
{
    float rc = 1.0f / (2.0f * 3.14159265f * fc_hz);
    return rc / (rc + DT);
}

static inline float iir_lp(iir1_t *f, float x, float alpha)
{
    f->y1 = alpha * x + (1.0f - alpha) * f->y1;
    return f->y1;
}

static inline float iir_hp(iir1_t *f, float x, float alpha)
{
    float y = alpha * (f->y1 + x - f->x1);
    f->x1 = x;
    f->y1 = y;
    return y;
}

/* ------------------------------------------------------------------ */
/* State                                                                */
/* ------------------------------------------------------------------ */
typedef enum {
    SD_IDLE,
    SD_RISING,       /* acc_mag_hp climbing toward peak */
    SD_FALLING,      /* past peak, waiting for gyro confirm */
    SD_CONFIRMED,    /* step logged, enforcing min interval */
} sd_state_t;

static struct {
    step_cb_t   cb;
    sd_state_t  state;

    iir1_t      hp_filter;
    iir1_t      lp_filter;

    float       running_max;
    float       running_mean;
    float       step_max_history[PEAK_HISTORY];
    int         hist_idx;

    float       peak_candidate;
    uint32_t    peak_ts_ms;
    float       peak_gyr_y;

    uint32_t    last_step_ts_ms;
    uint32_t    step_count;

    /* Last 4 step intervals for cadence estimate */
    uint32_t    interval_history[4];
    int         interval_idx;

    float       cadence_spm;
} sd;

/* ------------------------------------------------------------------ */
/* Adaptive threshold                                                   */
/* ------------------------------------------------------------------ */
static float adaptive_threshold(void)
{
    /* 0.5 * (running_mean + running_max) over last PEAK_HISTORY steps */
    float sum = 0;
    float max = 0;
    for (int i = 0; i < PEAK_HISTORY; i++) {
        sum += sd.step_max_history[i];
        if (sd.step_max_history[i] > max) max = sd.step_max_history[i];
    }
    float mean = sum / PEAK_HISTORY;
    (void)max;
    return 0.5f * mean;
}

static void record_peak(float peak)
{
    sd.step_max_history[sd.hist_idx] = peak;
    sd.hist_idx = (sd.hist_idx + 1) % PEAK_HISTORY;
}

/* ------------------------------------------------------------------ */
/* Cadence tracking                                                     */
/* ------------------------------------------------------------------ */
static void update_cadence(uint32_t interval_ms)
{
    sd.interval_history[sd.interval_idx] = interval_ms;
    sd.interval_idx = (sd.interval_idx + 1) % 4;

    uint32_t sum = 0;
    for (int i = 0; i < 4; i++) sum += sd.interval_history[i];
    float mean_ms = (float)sum / 4.0f;
    sd.cadence_spm = (mean_ms > 0) ? (60000.0f / mean_ms) : 0.0f;
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
void step_detector_init(step_cb_t cb)
{
    printk("SD_INIT addr=0x%x\n", (unsigned)(uintptr_t)&sd);
    memset(&sd, 0, sizeof(sd));
    sd.cb = cb;
    sd.state = SD_IDLE;
    /* Seed history with a plausible walking peak (~10 m/s²) giving initial
     * threshold = 5.0 m/s².  A lower seed lets a wider range of device-wear
     * conditions (attenuation from loose fit, mounting offset) be detected on
     * the very first step without waiting for the threshold to adapt. */
    for (int i = 0; i < PEAK_HISTORY; i++) sd.step_max_history[i] = 10.0f;
}

void step_detector_reset(void)
{
    step_detector_init(sd.cb);
}

float step_detector_cadence_spm(void)
{
    return sd.cadence_spm;
}

void step_detector_update(const imu_sample_t *s)
{
    /* Debug: first call, print address and filter state */
    {
        static int _sd_dbg = 0;
        if (_sd_dbg < 4) {
            uint32_t hp_y1_bits, lp_y1_bits;
            memcpy(&hp_y1_bits, &sd.hp_filter.y1, 4);
            memcpy(&lp_y1_bits, &sd.lp_filter.y1, 4);
            printk("SD_IN[%d] ts=%u hp_y1=0x%x lp_y1=0x%x state=%d sd_addr=0x%x\n",
                   _sd_dbg, s->ts_ms,
                   (unsigned)hp_y1_bits, (unsigned)lp_y1_bits,
                   (int)sd.state,
                   (unsigned)(uintptr_t)&sd);
            _sd_dbg++;
        }
    }

    /* acc magnitude */
    float acc_mag = sqrtf(s->acc_x * s->acc_x +
                          s->acc_y * s->acc_y +
                          s->acc_z * s->acc_z);

    /* Debug: print all 6 IMU values + acc_mag for first 2 samples */
    {
        static int _sd_imu_dbg = 0;
        if (_sd_imu_dbg < 2) {
            uint32_t ax_bits, ay_bits, az_bits, gy_bits, mag_bits;
            memcpy(&ax_bits,  &s->acc_x,  4);
            memcpy(&ay_bits,  &s->acc_y,  4);
            memcpy(&az_bits,  &s->acc_z,  4);
            memcpy(&gy_bits,  &s->gyr_y,  4);
            memcpy(&mag_bits, &acc_mag,   4);
            printk("IMU[%d] ts=%u ax=0x%x ay=0x%x az=0x%x mag=0x%x\n",
                   _sd_imu_dbg, s->ts_ms,
                   (unsigned)ax_bits, (unsigned)ay_bits, (unsigned)az_bits,
                   (unsigned)mag_bits);
            _sd_imu_dbg++;
        }
    }

    /* HP filter removes gravity (0.5 Hz) */
    float alpha_hp = lp_alpha_hp(HP_CUTOFF_HZ);
    float acc_hp   = iir_hp(&sd.hp_filter, acc_mag, alpha_hp);

    /* LP filter: adaptive cutoff based on cadence */
    float fc_lp  = (sd.cadence_spm >= CADENCE_RUN_THRESH) ? LP_RUNNING_HZ : LP_WALKING_HZ;
    float alpha_lp = lp_alpha(fc_lp);
    float acc_filt = iir_lp(&sd.lp_filter, acc_hp, alpha_lp);

    float thresh = adaptive_threshold();

    switch (sd.state) {

    case SD_IDLE:
    case SD_CONFIRMED:
        /* Gate: enforce minimum step interval */
        if (sd.state == SD_CONFIRMED &&
            (s->ts_ms - sd.last_step_ts_ms) < MIN_STEP_INTERVAL_MS) {
            break;
        }
        if (acc_filt > thresh) {
            sd.state = SD_RISING;
            sd.peak_candidate = acc_filt;
            sd.peak_ts_ms     = s->ts_ms;
            sd.peak_gyr_y     = s->gyr_y;
        }
        break;

    case SD_RISING:
        if (acc_filt > sd.peak_candidate) {
            /* Sanity: acc_filt should never exceed ~200 m/s² for any walking/running scenario */
            if (acc_filt > 200.0f) {
                uint32_t filt_bits, hp_y1_bits, lp_y1_bits;
                memcpy(&filt_bits,   &acc_filt,           4);
                memcpy(&hp_y1_bits,  &sd.hp_filter.y1,    4);
                memcpy(&lp_y1_bits,  &sd.lp_filter.y1,    4);
                printk("SANITY FAIL ts=%u filt=0x%x hp_y1=0x%x lp_y1=0x%x acc_mag=%d\n",
                       s->ts_ms, (unsigned)filt_bits, (unsigned)hp_y1_bits, (unsigned)lp_y1_bits,
                       (int)(sqrtf(s->acc_x*s->acc_x + s->acc_y*s->acc_y + s->acc_z*s->acc_z)*100.0f));
            }
            sd.peak_candidate = acc_filt;
            sd.peak_ts_ms     = s->ts_ms;
            sd.peak_gyr_y     = s->gyr_y;
        } else {
            /* Past the peak — transition to gyro confirmation */
            sd.state = SD_FALLING;
        }
        break;

    case SD_FALLING: {
        /* Wait for gyr_y zero-crossing within GYR_CONFIRM_MS of peak */
        uint32_t elapsed = s->ts_ms - sd.peak_ts_ms;
        bool gyr_cross = (sd.peak_gyr_y * s->gyr_y < 0.0f);  /* sign flip */

        bool gyr_strong = (sd.peak_gyr_y >= GYR_MIN_CONFIRM_DPS ||
                           sd.peak_gyr_y <= -GYR_MIN_CONFIRM_DPS);
        if (gyr_cross && elapsed <= GYR_CONFIRM_MS && gyr_strong) {
            /* Confirmed heel strike */
            record_peak(sd.peak_candidate);

            if (sd.step_count > 0) {
                uint32_t interval = sd.peak_ts_ms - sd.last_step_ts_ms;
                update_cadence(interval);
            }

            heel_strike_t hs = {
                .ts_ms       = sd.peak_ts_ms,
                .step_index  = sd.step_count,
                .peak_acc_mag = sd.peak_candidate,
                .peak_gyr_y  = sd.peak_gyr_y,
            };
            sd.last_step_ts_ms = sd.peak_ts_ms;
            sd.step_count++;
            sd.state = SD_CONFIRMED;

            /* Debug: print raw float32 bits of peak_acc_mag to diagnose overflow */
            {
                uint32_t acc_bits;
                int gyr_x10 = (int)(hs.peak_gyr_y * 10.0f);
                memcpy(&acc_bits, &hs.peak_acc_mag, 4);
                printk("STEP #%u ts=%u acc=%d gyr_y=%d cadence=%u spm acc_bits=0x%x\n",
                        hs.step_index, hs.ts_ms,
                        (int)(hs.peak_acc_mag * 10.0f),
                        gyr_x10,
                        (unsigned)sd.cadence_spm,
                        (unsigned)acc_bits);
            }

            if (sd.cb) sd.cb(&hs);

        } else if (elapsed > GYR_CONFIRM_MS) {
            /* Confirmation timed out — false peak, go back to idle */
            sd.state = SD_IDLE;
        }
        break;
    }
    } /* end switch (sd.state) */

    /* Debug: print filter state at exit for first 2 calls */
    {
        static int _sd_dbg_exit = 0;
        if (_sd_dbg_exit < 2) {
            uint32_t hp_y1_bits, lp_y1_bits;
            memcpy(&hp_y1_bits, &sd.hp_filter.y1, 4);
            memcpy(&lp_y1_bits, &sd.lp_filter.y1, 4);
            printk("SD_OUT[%d] ts=%u hp_y1=0x%x lp_y1=0x%x state=%d\n",
                   _sd_dbg_exit, s->ts_ms,
                   (unsigned)hp_y1_bits, (unsigned)lp_y1_bits,
                   (int)sd.state);
            _sd_dbg_exit++;
        }
    }
}
