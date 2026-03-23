#include "session_mgr.h"
#include "snapshot_buffer.h"
#include "../gait/gait_engine.h"
#include "../imu/calibration.h"
#include <kernel.h>
#include <drivers/gpio.h>
#include <logging/log.h>

#ifdef CONFIG_GAIT_RENODE_SIM
/* Declared in imu_sim_reader.c — set true when all stub samples consumed. */
extern volatile bool g_imu_sim_exhausted;
#endif

LOG_MODULE_REGISTER(session_mgr, LOG_LEVEL_INF);

/* ------------------------------------------------------------------ */
/* Hardware bindings (from device tree overlay)                         */
/* ------------------------------------------------------------------ */
#define LED_NODE    DT_ALIAS(led0)
#define BTN_NODE    DT_ALIAS(sw0)

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED_NODE, gpios);
static const struct gpio_dt_spec btn = GPIO_DT_SPEC_GET(BTN_NODE, gpios);

/* ------------------------------------------------------------------ */
/* Debounce & long-press                                                */
/* ------------------------------------------------------------------ */
#define DEBOUNCE_MS         200
#define LONG_PRESS_MS       2000

/* ------------------------------------------------------------------ */
/* LED blink patterns (period in ms, duty 50%)                          */
/* ------------------------------------------------------------------ */
#define LED_BLINK_IDLE_MS   1000
#define LED_BLINK_REC_MS    250
#define LED_BLINK_XFER_MS   100

/* ------------------------------------------------------------------ */
/* State                                                                */
/* ------------------------------------------------------------------ */
static session_state_t state;
static struct gpio_callback btn_cb_data;
static volatile uint32_t btn_press_ts;
static volatile bool      btn_pressed;

static K_SEM_DEFINE(btn_sem, 0, 1);

/* ------------------------------------------------------------------ */
/* Snapshot callback → push to buffer                                   */
/* ------------------------------------------------------------------ */
static void on_snapshot(const rolling_snapshot_t *snap)
{
    snapshot_buffer_push(snap);
}

/* ------------------------------------------------------------------ */
/* LED thread                                                           */
/* ------------------------------------------------------------------ */
static void led_thread_fn(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);
#ifndef CONFIG_GAIT_RENODE_SIM
    while (1) {
        int period;
        switch (state) {
        case SESSION_RECORDING: period = LED_BLINK_REC_MS;  break;
        case SESSION_TRANSFER:  period = LED_BLINK_XFER_MS; break;
        default:                period = LED_BLINK_IDLE_MS; break;
        }
        gpio_pin_toggle_dt(&led);
        k_msleep(period);
    }
#else
    /* No LED in sim mode — park the thread. */
    while (1) { k_msleep(10000); }
#endif
}

K_THREAD_DEFINE(led_tid, 512, led_thread_fn, NULL, NULL, NULL, 2, 0, 0);

/* ------------------------------------------------------------------ */
/* Button ISR                                                           */
/* ------------------------------------------------------------------ */
static void btn_isr(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(dev); ARG_UNUSED(cb); ARG_UNUSED(pins);
    if (!btn_pressed) {
        btn_press_ts = k_uptime_get_32();
        btn_pressed  = true;
        k_sem_give(&btn_sem);
    }
}

/* ------------------------------------------------------------------ */
/* Session thread                                                        */
/* ------------------------------------------------------------------ */
static void session_thread_fn(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);

    imu_calibration_t cal;
    if (calibration_load(&cal) != 0) {
        LOG_INF("No stored calibration — running calibration now");
        calibration_run(&cal);
    }

    gait_engine_init(on_snapshot);

#ifdef CONFIG_GAIT_RENODE_SIM
    /* Sim mode: auto-start session immediately, auto-stop when IMU samples exhausted. */
    LOG_INF("Sim mode: auto-starting gait session");
    snapshot_buffer_clear();
    gait_engine_session_start();
    state = SESSION_RECORDING;

    /* Poll for stub exhaustion — imu_sim_reader sets g_imu_sim_exhausted once
     * all samples are consumed and further calls return status=0. */
    while (!g_imu_sim_exhausted) {
        k_msleep(50);
    }
    /* Allow the last few samples already in the gait pipeline to flush. */
    k_msleep(500);

    gait_engine_session_stop();
    state = SESSION_COMPLETE;
    LOG_INF("Sim session complete — %u steps", gait_engine_step_count());

    /* Park the session thread. */
    while (1) {
        k_msleep(10000);
    }

#else /* !CONFIG_GAIT_RENODE_SIM — real hardware button path */

    while (1) {
        k_sem_take(&btn_sem, K_FOREVER);

        /* Wait to classify short vs long press */
        k_msleep(DEBOUNCE_MS);
        uint32_t held_ms = k_uptime_get_32() - btn_press_ts;
        btn_pressed = false;

        /* Wait until button released for long-press measurement */
        while (gpio_pin_get_dt(&btn) == 0) {
            k_msleep(10);
        }
        held_ms = k_uptime_get_32() - btn_press_ts;

        if (held_ms >= LONG_PRESS_MS) {
            /* Long press: stop session */
            if (state == SESSION_RECORDING) {
                gait_engine_session_stop();
                state = SESSION_COMPLETE;
                LOG_INF("Session complete — %u steps", gait_engine_step_count());
            }
        } else {
            /* Short press: start session */
            if (state == SESSION_IDLE || state == SESSION_COMPLETE) {
                snapshot_buffer_clear();
                gait_engine_session_start();
                state = SESSION_RECORDING;
            }
        }
    }
#endif /* CONFIG_GAIT_RENODE_SIM */
}

K_THREAD_DEFINE(sess_tid, 1024, session_thread_fn, NULL, NULL, NULL, 0, 0, 0);

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */
int session_mgr_init(void)
{
    state = SESSION_IDLE;

#ifndef CONFIG_GAIT_RENODE_SIM
    /* gpio_is_ready_dt() is Zephyr 3.x; use device_is_ready() in 2.7 */
    if (!device_is_ready(led.port) || !device_is_ready(btn.port)) {
        LOG_ERR("LED or button GPIO not ready");
        return -ENODEV;
    }

    gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE);
    gpio_pin_configure_dt(&btn, GPIO_INPUT);

    gpio_init_callback(&btn_cb_data, btn_isr, BIT(btn.pin));
    gpio_add_callback(btn.port, &btn_cb_data);
    gpio_pin_interrupt_configure_dt(&btn, GPIO_INT_EDGE_TO_ACTIVE);
#endif /* !CONFIG_GAIT_RENODE_SIM */

    snapshot_buffer_init();
    return 0;
}

session_state_t session_mgr_state(void)
{
    return state;
}

void session_mgr_start_transfer(void)
{
    if (state == SESSION_COMPLETE) {
        state = SESSION_TRANSFER;
    }
}

void session_mgr_clear(void)
{
    snapshot_buffer_clear();
    state = SESSION_IDLE;
}
