#pragma once
#include <stdint.h>

#ifdef CONFIG_GAIT_RENODE_SIM
/* In Renode sim mode BLE is not exercised — provide no-op inline stubs so
 * main.c can call ble_gait_svc_init() without changes. */
static inline int  ble_gait_svc_init(void)              { return 0; }
static inline void ble_gait_svc_advertise(void)          {}
static inline void ble_gait_svc_notify_status(uint8_t s) { (void)s; }
#else
/* Custom 128-bit UUIDs (base: 6E400001-B5A3-F393-E0A9-E50E24DCCA9E style) */

/* Initialise BLE stack and register custom GATT service. */
int ble_gait_svc_init(void);

/* Begin advertising; device is connectable for up to 60s after session stop. */
void ble_gait_svc_advertise(void);

/* Notify session status change to connected central (if subscribed). */
void ble_gait_svc_notify_status(uint8_t status);
#endif
