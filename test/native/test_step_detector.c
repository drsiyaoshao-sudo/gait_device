/*
 * Unit tests — step_detector
 * Build: pio test -e native
 * Deps: step_detector.c, foot_angle.c compiled with -DUNIT_TEST
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <assert.h>

/* Stub Zephyr types used by step_detector.c */
#ifndef UNIT_TEST
#error "Compile with -DUNIT_TEST"
#endif

/* Minimal stubs */
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef signed short int16_t;
typedef unsigned char uint8_t;
typedef int bool;
#define true 1
#define false 0

#include "../../src/gait/step_detector.h"

/* ------------------------------------------------------------------ */
/* Synthetic walk generator                                             */
/* 100 steps at 100 spm, 208 Hz                                        */
/* ------------------------------------------------------------------ */
#define ODR 208
#define STEPS 100
#define CADENCE_SPM 100.0f

static int detected_steps;

static void on_step(const heel_strike_t *hs)
{
    (void)hs;
    detected_steps++;
}

static imu_sample_t make_sample(uint32_t ts_ms, float acc_z, float gyr_y)
{
    imu_sample_t s = {0};
    s.acc_z = acc_z;
    s.gyr_y = gyr_y;
    s.ts_ms = ts_ms;
    return s;
}

static void test_synthetic_walk(void)
{
    step_detector_init(on_step);
    detected_steps = 0;

    float step_period_s = 60.0f / CADENCE_SPM;           /* 0.6s per step */
    float step_period_ms = step_period_s * 1000.0f;
    int   samples_per_step = (int)(step_period_s * ODR); /* 124 samples */

    uint32_t ts = 0;                              /* milliseconds */
    /* Each sample = 1000/208 ≈ 4.808 ms; use integer accumulation */
    #define TS_NUM 1000
    #define TS_DEN ODR
    int ts_frac = 0;

    for (int step = 0; step < STEPS; step++) {
        for (int i = 0; i < samples_per_step; i++) {
            float t = (float)i / ODR;
            float phase = t / step_period_s;

            /* Heel strike impulse at start of step: acc_z spike */
            float acc_z;
            if (phase < 0.05f) {
                /* Impact: Gaussian peak ~35 m/s² (3.5g + gravity) */
                float sigma = 0.02f;
                float mu    = step_period_s * 0.02f;
                acc_z = 9.81f + 25.0f * expf(-(t - mu)*(t - mu) / (2*sigma*sigma));
            } else if (phase < 0.6f) {
                /* Stance: ~1g loading */
                acc_z = 9.81f + 2.0f * sinf(3.14159f * phase / 0.6f);
            } else {
                /* Swing: near-zero load */
                acc_z = 2.0f + 1.0f * sinf(3.14159f * phase);
            }

            /*
             * gyr_y: negative just before heel strike (foot decelerating),
             * crosses zero and goes briefly positive as foot loads (~5ms),
             * then positive burst at toe-off push-off.
             * The confirmation window is ±40ms around the acc peak —
             * the zero crossing must occur within that window.
             */
            /*
             * gyr_y signal aligned so that the LP-filtered acc peak
             * (at ~phase 0.03) coincides with negative gyr_y, and gyr_y
             * crosses zero (negative→positive) at phase 0.05, giving a
             * ~10ms zero-crossing window after the acc peak — well within
             * the 40ms confirmation gate.
             */
            float gyr_y;
            if (phase < 0.05f) {
                /* Linearly decaying negative: -120 at phase=0 → 0 at phase=0.05 */
                gyr_y = -120.0f * (0.05f - phase) / 0.05f;
            } else if (phase < 0.10f) {
                /* Brief positive rebound after heel contact (zero crossing here) */
                gyr_y = 15.0f;
            } else if (phase > 0.55f && phase < 0.70f) {
                /* Push-off: plantarflexion burst */
                gyr_y = +200.0f * sinf(3.14159f * (phase - 0.55f) / 0.15f);
            } else {
                gyr_y = 0.0f;
            }

            imu_sample_t s = make_sample(ts, acc_z, gyr_y);
            step_detector_update(&s);
            /* Advance timestamp by exactly 1/ODR seconds in ms */
            ts_frac += TS_NUM;
            ts      += ts_frac / TS_DEN;
            ts_frac  = ts_frac % TS_DEN;
        }
    }

    printf("[test_synthetic_walk] detected=%d / expected=%d\n", detected_steps, STEPS);
    assert(detected_steps >= STEPS - 2 && detected_steps <= STEPS + 2);
    printf("PASS\n");
}

static void test_no_steps_silence(void)
{
    step_detector_init(on_step);
    detected_steps = 0;

    /* Feed 5 seconds of flat 1g gravity, no motion */
    for (int i = 0; i < 5 * ODR; i++) {
        imu_sample_t s = make_sample(i, 9.81f, 0.0f);
        step_detector_update(&s);
    }

    printf("[test_no_steps_silence] detected=%d / expected=0\n", detected_steps);
    assert(detected_steps == 0);
    printf("PASS\n");
}

static void test_min_interval_enforced(void)
{
    /* Two rapid spikes 100ms apart — only first should register */
    step_detector_init(on_step);
    detected_steps = 0;

    /* Spike 1 at t=0 */
    for (int i = 0; i < 10; i++) {
        imu_sample_t s = make_sample(i * 5, 9.81f + 30.0f * expf(-(float)i*i/4.0f),
                                     (i < 3) ? -100.0f : 10.0f);
        step_detector_update(&s);
    }

    /* Spike 2 at t=100ms — within MIN_STEP_INTERVAL (250ms) */
    for (int i = 0; i < 10; i++) {
        imu_sample_t s = make_sample(100 + i * 5, 9.81f + 30.0f * expf(-(float)i*i/4.0f),
                                     (i < 3) ? -100.0f : 10.0f);
        step_detector_update(&s);
    }

    printf("[test_min_interval_enforced] detected=%d / expected<=1\n", detected_steps);
    assert(detected_steps <= 1);
    printf("PASS\n");
}

int main(void)
{
    printf("=== step_detector unit tests ===\n");
    test_synthetic_walk();
    test_no_steps_silence();
    test_min_interval_enforced();
    printf("All tests PASSED\n");
    return 0;
}
