/*
 * ble_gait.ino — Gait algorithm over BLE (Amendment 16 step 4: algorithm over BLE)
 *
 * Streams step count, cadence, and SI stance over Nordic UART Service.
 * nRF Connect → "GaitSense" → Nordic UART Service → enable notify.
 *
 * Output format (on every completed step, ≤20 bytes for MTU=23):
 *   S<step> <stance_ms> <swing_ms> <cadence_spm>
 *   e.g. "S42 401 482 75\n"
 *
 * Output format (every 10 steps snapshot, ≤20 bytes):
 *   N<step> <si_stance_int>.<si_stance_frac> <cadence>
 *   e.g. "N40 62.5 80\n"
 */

#include <bluefruit.h>
#include "LSM6DS3.h"
#include "Wire.h"
#include "imu_types.h"
#include "step_detector.h"
#include "phase_segmenter.h"
#include "rolling_window.h"

BLEUart bleuart;
LSM6DS3 myIMU(I2C_MODE, 0x6A);

static uint32_t step_total = 0;

static void ble_print(const char *buf, int len) {
    Serial.print(buf);
    /* Write regardless — bleuart silently drops if not subscribed */
    bleuart.write((const uint8_t*)buf, len);
}

static void on_snapshot(const rolling_snapshot_t *snap) {
    /* "N10000 100.0 180\n" = 17 bytes worst case — fits MTU=23 */
    char buf[20];
    int len = snprintf(buf, sizeof(buf), "N%u %u.%u %u\n",
        snap->anchor_step_index,
        snap->si_stance_x10 / 10, snap->si_stance_x10 % 10,
        snap->mean_cadence_x10 / 10);
    ble_print(buf, len);
}

static void on_step_record(const step_record_t *rec) {
    step_total++;
    float cadence = step_detector_cadence_spm();
    step_record_t r = *rec;
    r.cadence_spm = (cadence > 255.0f) ? 255 : (uint8_t)cadence;
    rolling_window_add_step(&r);

    /* "S10000 800 600 180\n" = 19 bytes worst case — fits MTU=23 */
    char buf[20];
    int len = snprintf(buf, sizeof(buf), "S%u %u %u %d\n",
        r.step_index,
        r.stance_duration_ms, r.swing_duration_ms,
        (int)cadence);
    ble_print(buf, len);
}

static void on_heel_strike(const heel_strike_t *hs) {
    phase_segmenter_on_heel_strike(hs);
}

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
        Serial.println("IMU FAILED"); while (1);
    }
    Serial.println("IMU OK");

    step_detector_init(on_heel_strike);
    phase_segmenter_init(on_step_record);
    rolling_window_init(on_snapshot);

    Bluefruit.begin();
    Bluefruit.setName("GaitS");  /* "GaitSense" truncates in adv packet — keep short */
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

    Serial.println("GaitSense advertising — swing or walk");
}

static int poll_n = 0;

void loop() {
    delay(5);   /* ~200 Hz */

    imu_sample_t s;
    s.ts_ms = millis();
    s.acc_x = myIMU.readFloatAccelX() * 9.81f;
    s.acc_y = myIMU.readFloatAccelY() * 9.81f;
    s.acc_z = myIMU.readFloatAccelZ() * 9.81f;
    s.gyr_x = myIMU.readFloatGyroX();
    s.gyr_y = myIMU.readFloatGyroY();
    s.gyr_z = myIMU.readFloatGyroZ();

    step_detector_update(&s);
    phase_segmenter_update(&s);
}
