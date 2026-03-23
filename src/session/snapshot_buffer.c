#include "snapshot_buffer.h"
#include <kernel.h>
#include <logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(snap_buf, LOG_LEVEL_INF);

static rolling_snapshot_t buf[SNAPSHOT_BUF_SIZE];
static uint32_t head;    /* index of oldest snapshot    */
static uint32_t count;   /* total snapshots in buffer   */

K_MUTEX_DEFINE(snap_mutex);

int snapshot_buffer_init(void)
{
    memset(buf, 0, sizeof(buf));
    head  = 0;
    count = 0;
    return 0;
}

void snapshot_buffer_push(const rolling_snapshot_t *snap)
{
    k_mutex_lock(&snap_mutex, K_FOREVER);

    uint32_t tail = (head + count) % SNAPSHOT_BUF_SIZE;
    buf[tail] = *snap;

    if (count < SNAPSHOT_BUF_SIZE) {
        count++;
    } else {
        /* Overwrite oldest */
        head = (head + 1) % SNAPSHOT_BUF_SIZE;
        LOG_WRN("Snapshot buffer full — oldest evicted");
    }

    k_mutex_unlock(&snap_mutex);
}

uint32_t snapshot_buffer_count(void)
{
    k_mutex_lock(&snap_mutex, K_FOREVER);
    uint32_t n = count;
    k_mutex_unlock(&snap_mutex);
    return n;
}

int snapshot_buffer_read(uint32_t idx, rolling_snapshot_t *out)
{
    k_mutex_lock(&snap_mutex, K_FOREVER);

    if (idx >= count) {
        k_mutex_unlock(&snap_mutex);
        return -ENOENT;
    }
    *out = buf[(head + idx) % SNAPSHOT_BUF_SIZE];

    k_mutex_unlock(&snap_mutex);
    return 0;
}

void snapshot_buffer_clear(void)
{
    k_mutex_lock(&snap_mutex, K_FOREVER);
    head  = 0;
    count = 0;
    k_mutex_unlock(&snap_mutex);
    LOG_INF("Snapshot buffer cleared");
}
