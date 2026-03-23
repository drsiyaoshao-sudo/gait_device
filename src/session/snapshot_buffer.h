#pragma once
#include "../gait/rolling_window.h"
#include <stdint.h>

/* RAM ring buffer for rolling snapshots.
 * Capacity: ~5500 entries × 20 bytes = 110KB (fits in nRF52840 RAM).
 * When optional W25Q16 flash is present, writes go to flash instead. */

#define SNAPSHOT_BUF_SIZE   5500

int  snapshot_buffer_init(void);
void snapshot_buffer_push(const rolling_snapshot_t *snap);

/* Number of snapshots available to export. */
uint32_t snapshot_buffer_count(void);

/* Read snapshot at logical index 0..count-1 (oldest first). */
int snapshot_buffer_read(uint32_t idx, rolling_snapshot_t *out);

/* Clear all stored snapshots (call after successful BLE export). */
void snapshot_buffer_clear(void);
