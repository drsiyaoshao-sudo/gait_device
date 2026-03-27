#pragma once
#include <stdio.h>
#define LOG_MODULE_REGISTER(name, level)
#define LOG_INF(fmt, ...)  printf("[INF] " fmt "\n", ##__VA_ARGS__)
#define LOG_WRN(fmt, ...)  printf("[WRN] " fmt "\n", ##__VA_ARGS__)
#define LOG_ERR(fmt, ...)  printf("[ERR] " fmt "\n", ##__VA_ARGS__)
#define LOG_DBG(fmt, ...)
/* Zephyr printk → libc printf for native unit tests */
#define printk printf
