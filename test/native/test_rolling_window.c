/*
 * Unit tests — rolling_window (SI computation, window bounds)
 * Build: pio test -e native
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <assert.h>

#ifndef UNIT_TEST
#error "Compile with -DUNIT_TEST"
#endif

typedef unsigned int  uint32_t;
typedef unsigned short uint16_t;
typedef signed short   int16_t;
typedef unsigned char  uint8_t;
typedef int bool;
#define true 1
#define false 0

#include "../../src/gait/rolling_window.h"

static int snap_count;
static rolling_snapshot_t last_snap;

static void on_snap(const rolling_snapshot_t *s)
{
    last_snap = *s;
    snap_count++;
}

static step_record_t make_step(uint32_t idx, uint16_t stance_ms, uint16_t swing_ms)
{
    step_record_t r;
    memset(&r, 0, sizeof(r));
    r.step_index         = idx;
    r.heel_strike_ts_ms  = idx * 600;
    r.stance_duration_ms = stance_ms;
    r.swing_duration_ms  = swing_ms;
    r.step_duration_ms   = stance_ms + swing_ms;
    r.cadence_spm        = 100;
    r.peak_ang_vel_dps   = 200;
    r.flags              = 0x01;   /* valid */
    return r;
}

/* SI = 200 * |odd - even| / (odd + even) */
static float expected_si(float odd, float even)
{
    if (odd + even < 1e-6f) return 0.0f;
    return 200.0f * fabsf(odd - even) / (odd + even);
}

/* ------------------------------------------------------------------ */

static void test_si_identical_steps(void)
{
    rolling_window_init(on_snap);
    snap_count = 0;

    /* 210 identical steps: stance=350ms, swing=250ms */
    for (uint32_t i = 0; i < 210; i++) {
        step_record_t r = make_step(i, 350, 250);
        rolling_window_add_step(&r);
    }

    /* Last snapshot: SI should be 0 (identical odd and even) */
    float si = last_snap.si_stance_x10 / 10.0f;
    printf("[test_si_identical_steps] SI_stance=%.2f%% (expected ~0%%)\n", si);
    assert(si < 1.0f);
    printf("PASS\n");
}

static void test_si_alternating(void)
{
    rolling_window_init(on_snap);
    snap_count = 0;

    /* Alternating: even steps 400ms, odd steps 350ms
     * Expected SI = 200 * |350 - 400| / (350 + 400) = 200 * 50/750 ≈ 13.33% */
    for (uint32_t i = 0; i < 210; i++) {
        uint16_t stance = (i & 1) ? 350 : 400;
        step_record_t r = make_step(i, stance, 250);
        rolling_window_add_step(&r);
    }

    float si      = last_snap.si_stance_x10 / 10.0f;
    float si_exp  = expected_si(350.0f, 400.0f);
    printf("[test_si_alternating] SI_stance=%.2f%% (expected ~%.2f%%)\n", si, si_exp);
    assert(fabsf(si - si_exp) < 2.0f);   /* within 2% tolerance */
    printf("PASS\n");
}

static void test_window_fills_correctly(void)
{
    rolling_window_init(on_snap);
    snap_count = 0;

    /* Add exactly WINDOW_SIZE steps */
    for (uint32_t i = 0; i < WINDOW_SIZE; i++) {
        step_record_t r = make_step(i, 350, 250);
        rolling_window_add_step(&r);
    }

    printf("[test_window_fills_correctly] snaps_emitted=%d step_count_in_snap=%d\n",
           snap_count, last_snap.step_count);
    assert(last_snap.step_count == 200);
    printf("PASS\n");
}

static void test_snapshot_interval(void)
{
    rolling_window_init(on_snap);
    snap_count = 0;

    /* Add 100 steps — expect exactly 10 snapshots (100 / SNAPSHOT_INTERVAL) */
    for (uint32_t i = 0; i < 100; i++) {
        step_record_t r = make_step(i, 350, 250);
        rolling_window_add_step(&r);
    }

    printf("[test_snapshot_interval] snaps=%d / expected=%d\n",
           snap_count, 100 / SNAPSHOT_INTERVAL);
    assert(snap_count == 100 / SNAPSHOT_INTERVAL);
    printf("PASS\n");
}

static void test_si_zero_denom_no_crash(void)
{
    rolling_window_init(on_snap);

    /* Single step — only one of odd/even populated, denom path */
    step_record_t r = make_step(0, 350, 250);
    rolling_window_add_step(&r);
    /* No crash, no assertion failure */
    printf("[test_si_zero_denom_no_crash] PASS\n");
}

int main(void)
{
    printf("=== rolling_window unit tests ===\n");
    test_si_identical_steps();
    test_si_alternating();
    test_window_fills_correctly();
    test_snapshot_interval();
    test_si_zero_denom_no_crash();
    printf("All tests PASSED\n");
    return 0;
}
