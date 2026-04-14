#include <kernel.h>
#include <usb/usb_device.h>
#include <drivers/uart.h>
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
    uint32_t dtr = 0;

    if (usb_enable(NULL) != 0) return -1;

    cdc_uart = device_get_binding("CDC_ACM_0");
    if (!cdc_uart) return -1;

    while (!dtr) {
        uart_line_ctrl_get(cdc_uart, UART_LINE_CTRL_DTR, &dtr);
        k_sleep(K_MSEC(100));
    }

    int n = 0;
    char buf[16];
    while (1) {
        int len = snprintf(buf, sizeof(buf), "%d\n", n++);
        cdc_send(cdc_uart, buf, len);
        k_sleep(K_MSEC(500));
    }
}
