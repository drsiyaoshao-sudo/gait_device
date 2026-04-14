#pragma once
#include <stdint.h>
#include "phase_segmenter.h"

#define WINDOW_SIZE       200
#define SNAPSHOT_INTERVAL  10

typedef struct {
    uint32_t anchor_step_index;
    uint32_t anchor_ts_ms;
    uint16_t si_stance_x10;
    uint16_t si_swing_x10;
    uint16_t si_peak_angvel_x10;
    uint16_t mean_cadence_x10;
    uint8_t  step_count;
    uint8_t  flags;
} rolling_snapshot_t;

typedef void (*snapshot_cb_t)(const rolling_snapshot_t *snap);

void     rolling_window_init(snapshot_cb_t cb);
void     rolling_window_add_step(const step_record_t *rec);
void     rolling_window_reset(void);
uint16_t rolling_window_si_stance_x10(void);
