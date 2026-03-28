#pragma once
#include <stdint.h>
#include "phase_segmenter.h"

/* Rolling snapshot written every SNAPSHOT_INTERVAL steps.
 * Captures aggregate symmetry metrics over the last WINDOW_SIZE steps. */

#define WINDOW_SIZE         200     /* steps in rolling computation window */
#define SNAPSHOT_INTERVAL   10      /* write snapshot every N steps        */

typedef struct __attribute__((packed)) {
    uint32_t anchor_step_index;   /* step index of last step in window */
    uint32_t anchor_ts_ms;
    uint16_t si_stance_x10;       /* symmetry index stance duration × 10  */
    uint16_t si_swing_x10;
    uint16_t si_peak_angvel_x10;
    uint16_t mean_cadence_x10;    /* mean cadence × 10 (spm)              */
    uint8_t  step_count;          /* steps in window (< WINDOW_SIZE at start) */
    uint8_t  flags;               /* bit0: walking, bit1: running          */
} rolling_snapshot_t;             /* 18 bytes: 4+4+2+2+2+2+1+1 */

typedef void (*snapshot_cb_t)(const rolling_snapshot_t *snap);

void rolling_window_init(snapshot_cb_t cb);
void rolling_window_add_step(const step_record_t *rec);
void rolling_window_reset(void);

/* Compute and return current SI for stance duration (0–200, in × 10 units). */
uint16_t rolling_window_si_stance_x10(void);
