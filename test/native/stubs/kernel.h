#pragma once
#include <stdint.h>
#include <stdbool.h>
#define K_FOREVER  (-1)
#define K_NO_WAIT  (0)
typedef struct { int val; } k_timeout_t;
static inline uint32_t k_uptime_get_32(void) { return 0; }
