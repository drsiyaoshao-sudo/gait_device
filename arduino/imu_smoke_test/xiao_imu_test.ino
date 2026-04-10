#include "LSM6DS3.h"
#include "Wire.h"

LSM6DS3 myIMU(I2C_MODE, 0x6A);

void setup() {
    Serial.begin(9600);
    while (!Serial);
    if (myIMU.begin() != 0) {
        Serial.println("Device error");
    } else {
        Serial.println("Device OK!");
    }
}

void loop() {
    Serial.print("ax:"); Serial.print(myIMU.readFloatAccelX(), 3);
    Serial.print(" ay:"); Serial.print(myIMU.readFloatAccelY(), 3);
    Serial.print(" az:"); Serial.print(myIMU.readFloatAccelZ(), 3);
    Serial.print(" gx:"); Serial.print(myIMU.readFloatGyroX(), 2);
    Serial.print(" gy:"); Serial.print(myIMU.readFloatGyroY(), 2);
    Serial.print(" gz:"); Serial.println(myIMU.readFloatGyroZ(), 2);
    delay(100);
}
