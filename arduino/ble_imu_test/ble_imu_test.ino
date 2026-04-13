/*
 * ble_imu_test.ino — BLE IMU smoke test (Amendment 16 step 4)
 *
 * Streams live accel + gyro over Nordic UART Service at ~10 Hz.
 * nRF Connect → "GaitSense" → Nordic UART Service → enable notify.
 */

#include <bluefruit.h>
#include "LSM6DS3.h"
#include "Wire.h"

BLEUart bleuart;
LSM6DS3 myIMU(I2C_MODE, 0x6A);

void connect_callback(uint16_t conn_handle) {
    BLEConnection *conn = Bluefruit.Connection(conn_handle);
    char name[32] = {0};
    conn->getPeerName(name, sizeof(name));
    Serial.print("BLE connected: "); Serial.println(name);
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason) {
    (void)conn_handle; (void)reason;
    Serial.println("BLE disconnected");
}

void setup() {
    Serial.begin(115200);

    if (myIMU.begin() != 0) {
        Serial.println("IMU init FAILED");
        while (1);
    }
    Serial.println("IMU OK");

    Bluefruit.begin();
    Bluefruit.setName("GaitSense");
    Bluefruit.setTxPower(4);
    Bluefruit.Periph.setConnectCallback(connect_callback);
    Bluefruit.Periph.setDisconnectCallback(disconnect_callback);

    bleuart.begin();

    Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
    Bluefruit.Advertising.addTxPower();
    Bluefruit.Advertising.addService(bleuart);
    Bluefruit.Advertising.addName();
    Bluefruit.Advertising.restartOnDisconnect(true);
    Bluefruit.Advertising.setInterval(32, 244);
    Bluefruit.Advertising.setFastTimeout(30);
    Bluefruit.Advertising.start(0);

    Serial.println("Advertising — nRF Connect → GaitSense → Nordic UART");
}

static int n = 0;

void loop() {
    delay(5);   /* ~200 Hz poll */
    if (++n % 20 != 0) return;  /* send ~10 Hz */

    /* Each write must be ≤20 bytes (MTU=23, ATT overhead=3).
     * "A-9.81,-9.81,-9.81\n" = 20 bytes worst case.
     * "G-999.9,-999.9,-999.9\n" = 22 — split to G%.0f,%.0f,%.0f\n = 14 max. */
    char buf[22];
    int len;

    len = snprintf(buf, sizeof(buf), "A%.2f,%.2f,%.2f\n",
        myIMU.readFloatAccelX(), myIMU.readFloatAccelY(), myIMU.readFloatAccelZ());
    Serial.print(buf);
    bleuart.write(buf, len);

    len = snprintf(buf, sizeof(buf), "G%.1f,%.1f,%.1f\n",
        myIMU.readFloatGyroX(), myIMU.readFloatGyroY(), myIMU.readFloatGyroZ());
    Serial.print(buf);
    bleuart.write(buf, len);
}
