#include <kernel.h>
#include <usb/usb_device.h>
#include <drivers/uart.h>
#include <drivers/sensor.h>
#include <stdio.h>

static void cdc_send(const struct device *dev, const char *buf, int len)
{
    for (int i = 0; i < len; i++) {
        uart_poll_out(dev, buf[i]);
    }
}

int main(void)
{
    const struct device *cdc_uart;
    const struct device *imu;
    uint32_t dtr = 0;

    if (usb_enable(NULL) != 0) return -1;

    cdc_uart = device_get_binding("CDC_ACM_0");
    if (!cdc_uart) return -1;

    /* Wait for host to open port (asserts DTR) */
    while (!dtr) {
        uart_line_ctrl_get(cdc_uart, UART_LINE_CTRL_DTR, &dtr);
        k_sleep(K_MSEC(100));
    }

    imu = DEVICE_DT_GET_ANY(st_lsm6dsl);
    if (!imu || !device_is_ready(imu)) {
        const char *err = "IMU init failed\n";
        cdc_send(cdc_uart, err, sizeof("IMU init failed\n") - 1);
        return -1;
    }

    struct sensor_value ax, ay, az, gx, gy, gz;
    int n = 0;
    char buf[96];

    while (1) {
        k_sleep(K_MSEC(5));   /* ~200 Hz poll */
        if (++n % 20 != 0) continue;  /* print ~10 Hz */

        sensor_sample_fetch(imu);

        sensor_channel_get(imu, SENSOR_CHAN_ACCEL_X, &ax);
        sensor_channel_get(imu, SENSOR_CHAN_ACCEL_Y, &ay);
        sensor_channel_get(imu, SENSOR_CHAN_ACCEL_Z, &az);
        sensor_channel_get(imu, SENSOR_CHAN_GYRO_X,  &gx);
        sensor_channel_get(imu, SENSOR_CHAN_GYRO_Y,  &gy);
        sensor_channel_get(imu, SENSOR_CHAN_GYRO_Z,  &gz);

        int len = snprintf(buf, sizeof(buf),
            "ax:%.3f ay:%.3f az:%.3f gx:%.2f gy:%.2f gz:%.2f\n",
            sensor_value_to_double(&ax),
            sensor_value_to_double(&ay),
            sensor_value_to_double(&az),
            sensor_value_to_double(&gx),
            sensor_value_to_double(&gy),
            sensor_value_to_double(&gz));
        cdc_send(cdc_uart, buf, len);
    }
}
