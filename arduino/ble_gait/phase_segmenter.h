#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "imu_types.h"
#include "step_detector.h"

typedef struct {
    uint32_t step_index;
    uint32_t heel_strike_ts_ms;
    uint16_t step_duration_ms;
    uint16_t stance_duration_ms;
    uint16_t swing_duration_ms;
    int16_t  foot_angle_ic_cdeg;
    int16_t  foot_angle_to_cdeg;
    int16_t  peak_ang_vel_dps;
    uint8_t  cadence_spm;
    uint8_t  flags;
    uint8_t  reserved[8];
} step_record_t;

typedef void (*step_record_cb_t)(const step_record_t *rec);

void phase_segmenter_init(step_record_cb_t cb);
void phase_segmenter_on_heel_strike(const heel_strike_t *hs);
void phase_segmenter_update(const imu_sample_t *s);
void phase_segmenter_reset(void);
