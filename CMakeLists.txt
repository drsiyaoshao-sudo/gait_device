cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(gait_device)

target_link_libraries(app PRIVATE m)

target_sources(app PRIVATE
  src/main.c
  src/imu/calibration.c
  src/gait/gait_engine.c
  src/gait/step_detector.c
  src/gait/phase_segmenter.c
  src/gait/foot_angle.c
  src/gait/rolling_window.c
  src/session/session_mgr.c
  src/session/snapshot_buffer.c
)

# IMU reader: real hardware uses I2C driver; sim mode uses memory-mapped stub
if(CONFIG_GAIT_RENODE_SIM)
  target_sources(app PRIVATE src/imu/imu_sim_reader.c)
else()
  target_sources(app PRIVATE src/imu/imu_reader.c)
  target_sources(app PRIVATE src/ble/ble_gait_svc.c)
endif()
