#include "ble_gait_svc.h"
#include "../session/session_mgr.h"
#include "../session/snapshot_buffer.h"
#include "../gait/rolling_window.h"
#include <kernel.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <bluetooth/conn.h>
#include <bluetooth/uuid.h>
#include <bluetooth/gatt.h>
#include <logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(ble_gatt_svc, LOG_LEVEL_INF);

/* ------------------------------------------------------------------ */
/* UUIDs                                                                */
/* ------------------------------------------------------------------ */
/* Service: GAIT-0000 */
#define BT_UUID_GAIT_SVC    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE( \
    0x6E410000, 0xB5A3, 0xF393, 0xE0A9, 0xE50E24DCCA9E))

/* Session Status: GAIT-0001  (Read, Notify) */
#define BT_UUID_SESS_STATUS BT_UUID_DECLARE_128(BT_UUID_128_ENCODE( \
    0x6E410001, 0xB5A3, 0xF393, 0xE0A9, 0xE50E24DCCA9E))

/* Step Data Transfer: GAIT-0002  (Notify) — 5 × step_record_t per PDU */
#define BT_UUID_STEP_DATA   BT_UUID_DECLARE_128(BT_UUID_128_ENCODE( \
    0x6E410002, 0xB5A3, 0xF393, 0xE0A9, 0xE50E24DCCA9E))

/* Control Point: GAIT-0003  (Write) */
#define BT_UUID_CTRL_POINT  BT_UUID_DECLARE_128(BT_UUID_128_ENCODE( \
    0x6E410003, 0xB5A3, 0xF393, 0xE0A9, 0xE50E24DCCA9E))

/* ------------------------------------------------------------------ */
/* GATT attribute values                                                */
/* ------------------------------------------------------------------ */
static uint8_t session_status = SESSION_IDLE;
static struct bt_conn *active_conn;

/* CCC (Client Characteristic Configuration) storage */
static struct bt_gatt_ccc_cfg status_ccc_cfg[1];
static struct bt_gatt_ccc_cfg step_data_ccc_cfg[1];

/* ------------------------------------------------------------------ */
/* Control Point write handler                                          */
/* ------------------------------------------------------------------ */
#define CTRL_START   0x0001
#define CTRL_STOP    0x0002
#define CTRL_EXPORT  0x0003
#define CTRL_CLEAR   0x0004

static ssize_t ctrl_write(struct bt_conn *conn,
                           const struct bt_gatt_attr *attr,
                           const void *buf, uint16_t len,
                           uint16_t offset, uint8_t flags)
{
    if (len < 2) return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);

    uint16_t cmd;
    memcpy(&cmd, buf, 2);

    switch (cmd) {
    case CTRL_START:
        session_mgr_start_transfer();
        break;
    case CTRL_EXPORT:
        session_mgr_start_transfer();
        break;
    case CTRL_CLEAR:
        session_mgr_clear();
        break;
    default:
        return BT_GATT_ERR(BT_ATT_ERR_NOT_SUPPORTED);
    }
    return len;
}

/* ------------------------------------------------------------------ */
/* Session status read                                                   */
/* ------------------------------------------------------------------ */
static ssize_t status_read(struct bt_conn *conn,
                            const struct bt_gatt_attr *attr,
                            void *buf, uint16_t len, uint16_t offset)
{
    session_status = (uint8_t)session_mgr_state();
    return bt_gatt_attr_read(conn, attr, buf, len, offset,
                             &session_status, sizeof(session_status));
}

/* ------------------------------------------------------------------ */
/* GATT service definition                                              */
/* ------------------------------------------------------------------ */
BT_GATT_SERVICE_DEFINE(gait_svc,
    BT_GATT_PRIMARY_SERVICE(BT_UUID_GAIT_SVC),

    /* Session Status */
    BT_GATT_CHARACTERISTIC(BT_UUID_SESS_STATUS,
                            BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                            BT_GATT_PERM_READ,
                            status_read, NULL, &session_status),
    BT_GATT_CCC(status_ccc_cfg, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

    /* Step Data Transfer */
    BT_GATT_CHARACTERISTIC(BT_UUID_STEP_DATA,
                            BT_GATT_CHRC_NOTIFY,
                            BT_GATT_PERM_NONE,
                            NULL, NULL, NULL),
    BT_GATT_CCC(step_data_ccc_cfg, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

    /* Control Point */
    BT_GATT_CHARACTERISTIC(BT_UUID_CTRL_POINT,
                            BT_GATT_CHRC_WRITE,
                            BT_GATT_PERM_WRITE,
                            NULL, ctrl_write, NULL),
);

/* ------------------------------------------------------------------ */
/* Export thread: stream snapshots on SESSION_TRANSFER                  */
/* ------------------------------------------------------------------ */
/* Notification PDU: 4-byte header + up to 5 × rolling_snapshot_t (20B each) */
#define SNAPS_PER_NOTIF     10     /* 4 + 10×20 = 204 bytes — fits MTU 247 */

static void export_thread_fn(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);

    while (1) {
        if (session_mgr_state() != SESSION_TRANSFER || !active_conn) {
            k_msleep(100);
            continue;
        }

        uint32_t total = snapshot_buffer_count();
        uint16_t seq   = 0;

        for (uint32_t i = 0; i < total; i += SNAPS_PER_NOTIF) {
            uint8_t pkt[4 + SNAPS_PER_NOTIF * sizeof(rolling_snapshot_t)];
            uint16_t n = (uint16_t)MIN(SNAPS_PER_NOTIF, total - i);

            /* Header */
            memcpy(pkt, &seq, 2);
            memcpy(pkt + 2, &n, 2);
            seq++;

            for (uint16_t j = 0; j < n; j++) {
                rolling_snapshot_t snap;
                snapshot_buffer_read(i + j, &snap);
                memcpy(pkt + 4 + j * sizeof(snap), &snap, sizeof(snap));
            }

            /* Find the notify characteristic attribute */
            const struct bt_gatt_attr *attr = &gait_svc.attrs[4]; /* step data chrc value */
            bt_gatt_notify(active_conn, attr, pkt, 4 + n * sizeof(rolling_snapshot_t));
            k_msleep(10);   /* ~7.5ms connection interval — give stack time */
        }

        LOG_INF("Export complete — %u snapshots sent", total);
        session_mgr_clear();
    }
}

K_THREAD_DEFINE(export_tid, 2048, export_thread_fn, NULL, NULL, NULL, 1, 0, 0);

/* ------------------------------------------------------------------ */
/* Connection callbacks                                                  */
/* ------------------------------------------------------------------ */
static void connected(struct bt_conn *conn, uint8_t err)
{
    if (err) {
        LOG_ERR("BLE connect failed (err %u)", err);
        return;
    }
    active_conn = bt_conn_ref(conn);
    LOG_INF("BLE connected");

    /* Request tighter connection interval for snapshot export */
    bt_conn_le_param_update(conn,
        BT_LE_CONN_PARAM(BT_GAP_INIT_CONN_INT_MIN, 40, 0, 400));
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
    LOG_INF("BLE disconnected (reason %u)", reason);
    if (active_conn) {
        bt_conn_unref(active_conn);
        active_conn = NULL;
    }
    /* Re-advertise for 60s if session is complete */
    if (session_mgr_state() == SESSION_COMPLETE ||
        session_mgr_state() == SESSION_TRANSFER) {
        ble_gait_svc_advertise();
    }
}

BT_CONN_CB_DEFINE(conn_cbs) = {
    .connected    = connected,
    .disconnected = disconnected,
};

/* ------------------------------------------------------------------ */
/* Advertising                                                           */
/* ------------------------------------------------------------------ */
static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_NAME_COMPLETE, 'G','a','i','t','S','e','n','s','e'),
};

void ble_gait_svc_advertise(void)
{
    bt_le_adv_stop();
    int err = bt_le_adv_start(BT_LE_ADV_CONN, ad, ARRAY_SIZE(ad), NULL, 0);
    if (err) {
        LOG_ERR("Advertising failed (err %d)", err);
    } else {
        LOG_INF("Advertising started");
    }
}

/* ------------------------------------------------------------------ */
/* Init                                                                  */
/* ------------------------------------------------------------------ */
int ble_gait_svc_init(void)
{
    int err = bt_enable(NULL);
    if (err) {
        LOG_ERR("BT enable failed (err %d)", err);
        return err;
    }
    ble_gait_svc_advertise();
    return 0;
}

void ble_gait_svc_notify_status(uint8_t status)
{
    session_status = status;
    const struct bt_gatt_attr *attr = &gait_svc.attrs[1];
    bt_gatt_notify(active_conn, attr, &status, sizeof(status));
}
