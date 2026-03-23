cmake_minimum_required(VERSION 3.20.0)
include($ENV{ZEPHYR_BASE}/cmake/app/boilerplate.cmake NO_POLICY_SCOPE)
project(gait_device)

# Core sources (always compiled)
target_sources(app PRIVATE
  ../src/main.c
  ../src/imu/calibration.c
  ../src/gait/gait_engine.c
  ../src/gait/step_detector.c
  ../src/gait/phase_segmenter.c
  ../src/gait/foot_angle.c
  ../src/gait/rolling_window.c
  ../src/session/session_mgr.c
  ../src/session/snapshot_buffer.c
)

# IMU reader: real hardware vs Renode simulation
if(CONFIG_GAIT_RENODE_SIM)
  target_sources(app PRIVATE ../src/imu/imu_sim_reader.c)
else()
  target_sources(app PRIVATE ../src/imu/imu_reader.c)
  target_sources(app PRIVATE ../src/ble/ble_gait_svc.c)
endif()

# Link FPU-compatible libm.
# The compiler is built with -mfloat-abi=hard so we must use the hard-float
# libm variant. Derive the toolchain root from CMAKE_C_COMPILER and add an
# explicit -L path so the linker finds the v7e-m+fp/hard libm before nofp.
get_filename_component(_TC_BIN "${CMAKE_C_COMPILER}" DIRECTORY)
get_filename_component(_TC_ROOT "${_TC_BIN}/.." ABSOLUTE)
set(_LIBM_DIR "${_TC_ROOT}/arm-none-eabi/lib/thumb/v7e-m+fp/hard")
if(EXISTS "${_LIBM_DIR}/libm.a")
  # target_link_directories gives role="libraries" in CMake File API so that
  # PlatformIO routes it to lib_paths (not link_flags where filter_args is buggy).
  target_link_directories(app INTERFACE "${_LIBM_DIR}")
endif()
target_link_libraries(app PRIVATE m)
