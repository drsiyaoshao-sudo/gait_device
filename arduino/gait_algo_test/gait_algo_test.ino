#include "LSM6DS3.h"
#include "Wire.h"
#include "imu_types.h"
#include "step_detector.h"
#include "phase_segmenter.h"
#include "rolling_window.h"

LSM6DS3 myIMU(I2C_MODE, 0x6A);

static uint32_t step_total = 0;

/* ── rolling_window callback: print every 10 steps ── */
static void on_snapshot(const rolling_snapshot_t *snap) {
    Serial.print("SNAPSHOT step="); Serial.print(snap->anchor_step_index);
    Serial.print(" si_stance=");
    Serial.print(snap->si_stance_x10 / 10); Serial.print(".");
    Serial.print(snap->si_stance_x10 % 10); Serial.print("%");
    Serial.print(" si_swing=");
    Serial.print(snap->si_swing_x10 / 10);  Serial.print(".");
    Serial.print(snap->si_swing_x10 % 10);  Serial.print("%");
    Serial.print(" cadence=");
    Serial.print(snap->mean_cadence_x10 / 10); Serial.println(" spm");
}

/* ── phase_segmenter callback: step record complete ── */
static void on_step_record(const step_record_t *rec) {
    step_total++;
    /* cadence_spm field in step_record_t is uint8_t, never set by phase_segmenter.
     * Read directly from step_detector which tracks it. */
    float cadence = step_detector_cadence_spm();

    /* Mutate a local copy to set cadence before adding to rolling window */
    step_record_t r = *rec;
    r.cadence_spm = (cadence > 255.0f) ? 255 : (uint8_t)cadence;

    rolling_window_add_step(&r);

    /* Print SI after every step — don't wait for 10-step snapshot */
    uint16_t si = rolling_window_si_stance_x10();

    Serial.print("STEP #"); Serial.print(r.step_index);
    Serial.print(" stance="); Serial.print(r.stance_duration_ms);
    Serial.print("ms swing="); Serial.print(r.swing_duration_ms);
    Serial.print("ms cadence="); Serial.print((int)cadence);
    Serial.print("spm si_stance=");
    Serial.print(si / 10); Serial.print("."); Serial.print(si % 10);
    Serial.println("%");
}

/* ── step_detector callback: heel strike → feed phase_segmenter ── */
static void on_heel_strike(const heel_strike_t *hs) {
    phase_segmenter_on_heel_strike(hs);
}

void setup() {
    Serial.begin(115200);
    while (!Serial);

    if (myIMU.begin() != 0) {
        Serial.println("IMU init FAILED");
        while (1);
    }
    Serial.println("IMU OK — gait algorithm running");

    step_detector_init(on_heel_strike);
    phase_segmenter_init(on_step_record);
    rolling_window_init(on_snapshot);
}

void loop() {
    /* ~208 Hz poll — matches algorithm ODR assumption */
    delay(5);

    imu_sample_t s;
    s.ts_ms = millis();
    /* LSM6DS3 returns accel in g — convert to m/s² */
    s.acc_x = myIMU.readFloatAccelX() * 9.81f;
    s.acc_y = myIMU.readFloatAccelY() * 9.81f;
    s.acc_z = myIMU.readFloatAccelZ() * 9.81f;
    /* Gyro already in dps */
    s.gyr_x = myIMU.readFloatGyroX();
    s.gyr_y = myIMU.readFloatGyroY();
    s.gyr_z = myIMU.readFloatGyroZ();

    step_detector_update(&s);
    phase_segmenter_update(&s);
}
