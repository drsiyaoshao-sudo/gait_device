#include <kernel.h>
#include <usb/usb_device.h>
#include <drivers/uart.h>
#include <drivers/sensor.h>
#include <drivers/i2c.h>
#include <drivers/gpio.h>
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

    /* P1.08 driven HIGH by gpio-hog in overlay (fires before drivers init) */
    cdc_send(cdc_uart, "P1.08 via hog\n", 14);

    /* Direct WHO_AM_I probe — SDA=P0.07 SCL=P0.27 via TWIM */
    const struct device *i2c = device_get_binding("I2C_0");
    char sbuf[64];
    if (!i2c) {
        cdc_send(cdc_uart, "I2C_0 not found\n", 16);
    } else {
        cdc_send(cdc_uart, "I2C_0 ok\n", 9);
        uint8_t reg = 0x0F, who = 0;
        int r = i2c_write_read(i2c, 0x6A, &reg, 1, &who, 1);
        int l = snprintf(sbuf, sizeof(sbuf), "WHO_AM_I@0x6A: ret=%d val=0x%02x\n", r, who);
        cdc_send(cdc_uart, sbuf, l);
    }

    cdc_send(cdc_uart, "getting device\n", 15);
    imu = DEVICE_DT_GET_ANY(st_lsm6dsl);
    if (!imu) {
        cdc_send(cdc_uart, "ERR: no DT node\n", 16);
        return -1;
    }
    cdc_send(cdc_uart, "DT node ok\n", 11);
    if (!device_is_ready(imu)) {
        cdc_send(cdc_uart, "ERR: not ready\n", 15);
        return -1;
    }
    cdc_send(cdc_uart, "IMU ready\n", 10);

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
