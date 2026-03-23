/*
 * Unit tests — foot_angle complementary filter
 * Build: pio test -e native
 */
#include <stdio.h>
#include <math.h>
#include <assert.h>
#include <string.h>

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

#include "../../src/gait/foot_angle.h"
#include "../../src/imu/imu_reader.h"

static imu_sample_t make_sample(float ax, float ay, float az,
                                  float gx, float gy, float gz)
{
    imu_sample_t s = {0};
    s.acc_x = ax; s.acc_y = ay; s.acc_z = az;
    s.gyr_x = gx; s.gyr_y = gy; s.gyr_z = gz;
    return s;
}

static void test_drift_1s_zero_input(void)
{
    foot_angle_init();

    /* Initialise with flat foot (acc_x=0, acc_z=9.81 → angle=0°) */
    imu_sample_t s = make_sample(0.0f, 0.0f, 9.81f, 0.0f, 0.0f, 0.0f);
    foot_angle_update(&s);

    /* 1 second of zero gyro + mild noise on accel (±0.1 m/s²) */
    for (int i = 0; i < 208; i++) {
        float noise = (i % 2 == 0) ? 0.05f : -0.05f;
        s = make_sample(noise, 0.0f, 9.81f + noise, 0.0f, 0.0f, 0.0f);
        foot_angle_update(&s);
    }

    float drift = fabsf(foot_angle_get());
    printf("[test_drift_1s_zero_input] drift=%.4f° (must be < 1°)\n", drift);
    assert(drift < 1.0f);
    printf("PASS\n");
}

static void test_gravity_init(void)
{
    foot_angle_init();

    /* 10° dorsiflexed: acc_x = 9.81*sin(10°), acc_z = 9.81*cos(10°) */
    float angle_true = 10.0f;
    float ax = 9.81f * sinf(angle_true * 3.14159f / 180.0f);
    float az = 9.81f * cosf(angle_true * 3.14159f / 180.0f);

    imu_sample_t s = make_sample(ax, 0.0f, az, 0.0f, 0.0f, 0.0f);
    foot_angle_update(&s);

    float angle = foot_angle_get();
    printf("[test_gravity_init] measured=%.2f° (expected ~%.2f°)\n", angle, angle_true);
    assert(fabsf(angle - angle_true) < 1.0f);
    printf("PASS\n");
}

static void test_gyro_integration(void)
{
    foot_angle_init();

    /* Start flat */
    imu_sample_t s = make_sample(0.0f, 0.0f, 9.81f, 0.0f, 0.0f, 0.0f);
    foot_angle_update(&s);

    /* Rotate 100 dps for 0.1s = 10° with zero accel correction */
    /* Use pure gyro scenario: acc_x=0, acc_z=9.81 stays constant (small angle) */
    for (int i = 0; i < 21; i++) {
        s = make_sample(0.0f, 0.0f, 9.81f, 0.0f, 100.0f, 0.0f);
        foot_angle_update(&s);
    }

    float angle = foot_angle_get();
    printf("[test_gyro_integration] angle=%.2f° (expected ~10°, filter applies)\n", angle);
    /* Filter blends in gravity — expect ballpark 8-12° */
    assert(angle > 5.0f && angle < 15.0f);
    printf("PASS\n");
}

int main(void)
{
    printf("=== foot_angle unit tests ===\n");
    test_gravity_init();
    test_drift_1s_zero_input();
    test_gyro_integration();
    printf("All tests PASSED\n");
    return 0;
}
