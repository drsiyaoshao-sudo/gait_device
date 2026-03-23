"""
PlatformIO post-script: re-link app/libapp.a into the final firmware.

PlatformIO's Zephyr framework build (platformio-build.py) explicitly removes
app/libapp.a from the link step, expecting to compile app sources natively.
However, this doesn't work when Kconfig-conditional sources (CONFIG_GAIT_RENODE_SIM)
control which IMU reader is included — CMake handles the conditional correctly,
but PlatformIO's native compilation would include ALL src/ files.

This script:
  1. Re-adds app/libapp.a (built by CMake/ninja) with --whole-archive so that
     Zephyr SYS_INIT macros and device structs in app code are preserved.
  2. Adds the FPU-compatible libm search path so that sqrtf/atan2f resolve
     to the hard-float libm.a, not the soft-float nofp variant.
"""

Import("env")
import os

build_dir = env.subst("$BUILD_DIR")
libapp = os.path.join(build_dir, "app", "libapp.a")

# --- FPU libm path ---
# Derive toolchain root from $CC (arm-none-eabi-gcc path)
cc = env.subst("$CC")
tc_bin = os.path.dirname(cc)           # .../toolchain-gccarmnoneeabi/bin
tc_root = os.path.dirname(tc_bin)      # .../toolchain-gccarmnoneeabi
libm_fpu_dir = os.path.join(tc_root, "arm-none-eabi", "lib", "thumb", "v7e-m+fp", "hard")
if os.path.isfile(os.path.join(libm_fpu_dir, "libm.a")):
    env.Prepend(LIBPATH=[libm_fpu_dir])

# --- app/libapp.a ---
# Append after existing _LIBFLAGS so Zephyr's whole-archive section runs first
# (libapp depends on Zephyr kernel symbols, so ordering matters).
if os.path.isfile(libapp):
    env.Append(
        _LIBFLAGS=" -Wl,--whole-archive %s -Wl,--no-whole-archive -lm" % libapp
    )
    # Tell SCons that firmware.elf depends on libapp.a being up to date
    env.Depends("$PROG_PATH", libapp)
