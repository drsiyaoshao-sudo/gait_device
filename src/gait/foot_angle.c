#include "foot_angle.h"
#include <stdbool.h>
#include <math.h>
#include <stdbool.h>

#define ODR_HZ          208.0f
#define DT              (1.0f / ODR_HZ)
#define GYRO_ALPHA      0.98f
#define ACCEL_ALPHA     (1.0f - GYRO_ALPHA)
#define RAD_TO_DEG      57.2957795f

static float angle_deg;
static bool  initialised;

void foot_angle_init(void)
{
    angle_deg   = 0.0f;
    initialised = false;
}

void foot_angle_reset(void)
{
    foot_angle_init();
}

void foot_angle_update(const imu_sample_t *s)
{
    /* Gravity-based angle from X and Z (heel-to-toe vs dorsal) */
    float angle_from_gravity = atan2f(s->acc_x, s->acc_z) * RAD_TO_DEG;

    if (!initialised) {
        angle_deg   = angle_from_gravity;
        initialised = true;
        return;
    }

    /* Integrate gyro (gyr_y = rotation around Y = pitch = foot flexion axis) */
    float gyro_integrated = angle_deg + s->gyr_y * DT;

    /* Fuse */
    angle_deg = GYRO_ALPHA * gyro_integrated + ACCEL_ALPHA * angle_from_gravity;
}

float foot_angle_get(void)
{
    return angle_deg;
}
