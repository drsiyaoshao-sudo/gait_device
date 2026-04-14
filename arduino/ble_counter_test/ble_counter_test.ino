/*
 * ble_counter_test.ino — BLE counter smoke test (Amendment 16 step 4)
 *
 * Uses Nordic UART Service (NUS) — nRF Connect shows it as "Nordic UART Service"
 * with a dedicated UART tab. No hunting for custom UUIDs.
 *
 * To receive: nRF Connect → scan → "GaitSense" → Connect → Nordic UART Service tab
 * → enable notify → watch "counter=N" lines arrive every second.
 */

#include <bluefruit.h>

BLEUart bleuart;
uint32_t counter = 0;

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

    Serial.println("GaitSense advertising — open nRF Connect, Nordic UART Service");
}

void loop() {
    delay(1000);
    counter++;

    char buf[32];
    int len = snprintf(buf, sizeof(buf), "counter=%lu\n", counter);
    Serial.print(buf);

    if (Bluefruit.connected()) {
        bleuart.write(buf, len);
    }
}
