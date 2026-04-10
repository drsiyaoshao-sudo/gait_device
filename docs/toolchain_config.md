# GaitSense Toolchain Configuration

**Maintained by:** `/toolchain` janitor command  
**Last updated:** 2026-04-10  
**Lock status:** LOCKED — Stage 0 HIL validated 2026-04-10  
**Stage 0 evidence:** USB counter ✓ · USB IMU ✓ · USB algo ✓ · BLE algo ✓ (confirmed by engineer 2026-04-10)

> This file is the single source of truth for all build, flash, and test operations.
> All agents read this file before taking any toolchain-dependent action.
> Only the `/toolchain` janitor command writes to it.
> Changes since last lock: `/toolchain diff`

---

## Hardware

| Field | Value | Notes |
|-------|-------|-------|
| Board | Seeed XIAO nRF52840 Sense (102010448) | Must be **Sense** variant — on-board IMU only on Sense |
| MCU | Nordic nRF52840, ARM Cortex-M4F @ 64 MHz | 1 MB flash, 256 KB SRAM |
| IMU | LSM6DS3TR-C | On-board, I2C address 0x6A, WHO_AM_I = 0x6A |
| BLE | nRF52840 integrated | S140 SoftDevice v7.3.0 required for Arduino BLE |
| Bootloader | Seeed UF2 bootloader | Links at 0x1000; app links at 0x27000 (SoftDevice offset) |
| USB | USB-C (data-capable cable required) | Appears as USB CDC ACM serial device |
| Power | 3.7 V LiPo via JST-PH 2.0 mm or USB-C | 150 mAh minimum for ankle wearable |
| External test hw | Nordic PPK2 (power profiler) | For current measurement in Stage 4 |

---

## Pin Map

| Signal | Arduino Pin | nRF52840 Port | Direction | Notes |
|--------|-------------|---------------|-----------|-------|
| IMU_POWER | 15 | P1.08 | OUTPUT | Power enable for LSM6DS3TR-C; asserted HIGH at boot by Seeed core via `PIN_LSM6DS3TR_C_POWER` |
| IMU_SDA | 4 (Wire1) | P0.07 | BIDIR | I2C data — use Wire1, not Wire |
| IMU_SCL | 5 (Wire1) | P0.27 | BIDIR | I2C clock — **do not use P0.27 as button or GPIO** |
| LED_RED | — | P0.13 | OUTPUT | Built-in RGB LED red channel, active-low |
| LED_GREEN | — | P1.11 | OUTPUT | Built-in RGB LED green channel, active-low |
| LED_BLUE | — | P1.12 | OUTPUT | Built-in RGB LED blue channel, active-low |
| BUTTON_FUTURE | D0 | P0.02 | INPUT | Reserved for session control button — only safe free pad |
| SWDCLK | — | P0.27 | — | Shared with IMU_SCL; do not use for GPIO when IMU active |
| USB_CDC | — | — | — | Appears as `/dev/tty.usbmodem*` on macOS after boot |

**Pin conflict warning:** P0.27 = IMU_SCL. Any overlay or sketch that assigns P0.27 as a button or GPIO will break I2C. This caused the Zephyr IMU bring-up failure (see Blocked Toolchains).

---

## Active Firmware Toolchain

| Layer | Tool | Version / Details |
|-------|------|-------------------|
| Build system | Arduino CLI | `arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840Sense` |
| Board core | Seeed nrf52 Arduino core | `Seeeduino:nrf52` — includes Bluefruit52Lib, SoftDevice S140 v7.3.0 |
| FQBN | `Seeeduino:nrf52:xiaonRF52840Sense` | Full board FQBN for all compile/upload calls |
| Flash method | Sparse UF2 | Double-tap RST → `/Volumes/XIAO-SENSE/` mounts → copy UF2 |
| UF2 converter | `scripts/make_sparse_uf2.py` | Combines `sd_bl.bin` at 0x1000 + app hex at 0x27000 |
| SoftDevice binary | `/tmp/seeed_bl/sd_bl.bin` | S140 v7.3.0 + Seeed bootloader; extract once from nrfutil zip |
| Serial monitor (USB) | `screen /dev/tty.usbmodem* 115200` | Or `pio device monitor -e xiaoble_sense_hello` |
| BLE receiver | `python3.11 scripts/ble_console.py` | `bleak` library; always python3.11 (not system 3.9) |
| BLE protocol | Nordic UART Service (NUS) | TX UUID: `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` (board→host) |
| Device BLE name | `GaitS` | "GaitSense" truncates to "GaitS" in advertising packet |
| Algorithm source | `src/gait/*.c` | C, framework-agnostic; ported to `.cpp` per Arduino sketch |
| Simulation | Renode + PlatformIO (`xiaoble_sense_sim`) | Separate from hardware firmware toolchain |
| Unit tests | PlatformIO native (`native`) | `pio test -e native` |

---

## Blocked Toolchains

| Layer | Blocked Tool | Blocked Since | Reason | Strikes | Lift Condition |
|-------|-------------|---------------|--------|---------|----------------|
| Firmware build + flash | Zephyr + PlatformIO (`xiaoble_sense_hello`) | 2026-04-10 | LSM6DS3TR-C WHO_AM_I returns EIO (errno -5) after 3 independent fix attempts. Root cause: P0.27 shared between I2C SCL and session button in DTS overlay. Regulator-fixed boot timing also suspected. | 3/3 | New Bill + Judicial Hearing required. Must show hardware evidence of successful WHO_AM_I read before block can be lifted. |
| Serial monitor | `pio device monitor` (for hardware) | 2026-04-10 | DTR assert timing caused board reset on macOS with pio monitor. `screen` and direct `pyserial` are reliable. | 1 | Can re-evaluate if pio monitor works with `--raw` flag on new OS/pio version. |

---

## Library Manifest

| Library | Version | Source | Purpose | Known Issues / Patches |
|---------|---------|--------|---------|------------------------|
| Seeed Arduino LSM6DS3 | 2.0.3 | Arduino library manager: `Seeed Arduino LSM6DS3` | IMU driver for LSM6DS3TR-C (I2C_MODE, 0x6A) | `setBitOrder()` not available on `ARDUINO_ARCH_MBED`; patched in `LSM6DS3.cpp` to skip on mbed. Not needed on Seeed nrf52 core. |
| Bluefruit52Lib | bundled with Seeed nrf52 core | Seeed nrf52 core (built-in) | BLE stack: BLEUart, Nordic UART Service, SoftDevice wrapper | None |
| Wire (Wire1) | bundled with Seeed nrf52 core | Seeed nrf52 core (built-in) | I2C — use Wire1 for IMU on XIAO Sense, not Wire | Wire (not Wire1) will target the wrong I2C bus |
| bleak | 0.21.1+ | `python3.11 -m pip install bleak` | BLE central on macOS for `ble_console.py` | Must use python3.11; system Python 3.9 not supported |
| pyserial | 3.5+ | `python3 -m pip install pyserial` | USB CDC serial for simulation scripts | — |
| numpy | 1.24+ | `pip install numpy` | Simulation signal generation | — |
| scipy | 1.10+ | `pip install scipy` | Filter design (Butterworth LP/HP chains) | — |
| matplotlib | 3.7+ | `pip install matplotlib` | Signal plots (Amendment 11) | — |

---

## Repository Registry

| Repo | Local Path | Branch | Purpose | Cross-repo assets | Access |
|------|-----------|--------|---------|-------------------|--------|
| gait_device | `/Users/siyaoshao/gait_device` | `constitution-style-management` (→ main) | Primary: firmware, simulation, algorithm, governance | All — this is the source of truth | read/write |
| auto-pinn-generation | `/Users/siyaoshao/auto-pinn-generation` | main | PINN physics-informed neural network for gait boundary discovery; Stage 3 grid search | `.claude/commands/` — agent skill templates (hear, plot-evidence, model-train, session, plot-profile, plot-training) | read-only from gait_device sessions |

**Cross-repo agent skill policy:** When an agent skill is imported from `auto-pinn-generation`,
it must be adapted and committed to `gait_device/.claude/commands/` before use. Do not call
scripts or agents in `auto-pinn-generation` directly from a gait_device session.

---

## Validation Record

Run `/toolchain validate` to re-run all checks.

| Check | Status | Detail |
|-------|--------|--------|
| Blocked toolchain in active slot | PASS | Zephyr blocked; active = Arduino CLI |
| Required fields populated | PASS | Board, MCU, IMU, FQBN, flash method all present |
| Library versions pinned | PASS | All libraries have explicit version or "bundled" |
| Amendment 17 alignment | PASS | Active toolchain table matches amendments.md record |
| Repo paths exist | PASS | Both local paths exist on disk |
| Pin conflicts | PASS | P0.27 documented as SCL-only; button assigned to P0.02 |
| Blocked toolchain has reason | PASS | Zephyr block cites WHO_AM_I EIO + 3 strikes |

**Overall: CLEAN**

---

## Change Log

| Date | Change | Made by |
|------|--------|---------|
| 2026-04-10 | Initial config created; Stage 0 HIL validated | engineer + Claude Sonnet 4.6 |
| 2026-04-10 | Zephyr blocked after 3-strike failure on WHO_AM_I | engineer |
| 2026-04-10 | Arduino CLI + sparse UF2 established as active toolchain | engineer |
| 2026-04-10 | BLE NUS path validated: counter ✓ IMU ✓ algo ✓ | engineer |
