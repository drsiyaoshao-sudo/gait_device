#pragma once
#include <stdint.h>

typedef enum {
    SESSION_IDLE       = 0,
    SESSION_RECORDING  = 1,
    SESSION_COMPLETE   = 2,
    SESSION_TRANSFER   = 3,
} session_state_t;

int  session_mgr_init(void);
session_state_t session_mgr_state(void);

/* Called from BLE control point to trigger export. */
void session_mgr_start_transfer(void);
void session_mgr_clear(void);
