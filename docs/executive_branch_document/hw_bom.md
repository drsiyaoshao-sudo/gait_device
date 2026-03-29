# Hardware Bill of Materials — Ankle Gait Analysis Wearable

## Core Assembly (~$45–50)

| # | Item | Part Number | Description | Qty | Supplier | Est. Unit Price |
|---|------|-------------|-------------|-----|----------|-----------------|
| 1 | MCU + IMU Module | Seeed 102010448 | **XIAO nRF52840 Sense** — nRF52840 Cortex-M4F + LSM6DS3TR-C 6-DOF IMU, BLE 5.0, built-in LiPo charging (BQ25101) via USB-C, 21×17.5mm castellated pads | 1 | [Seeed Studio](https://www.seeedstudio.com/Seeed-XIAO-BLE-Sense-nRF52840-p-5253.html) / Mouser | $15–18 |
| 2 | LiPo Battery | 402030 3.7V 150mAh | Lithium polymer cell, JST-PH 2.0mm connector, 40×20×3mm | 1 | Amazon / Adafruit | $6–8 |
| 3 | Perfboard | Generic 2.54mm pitch | Single-sided FR4; cut to ~30×40mm to mount XIAO + button + LED | 1 pc | Amazon / Adafruit | $1 |
| 4 | Tactile Button | Omron B3F-4055 or equiv. | 6×6mm through-hole, session start/stop | 1 | Mouser / Digikey | $0.50 |
| 5 | LED, Green | 3mm TH (L-7113GD) or 0805 SMD | Status indicator — placed dorsal side, visible without removing device | 1 | Mouser | $0.10 |
| 6 | Resistor 330Ω | 1/4W 5% TH | LED current limiter (3.3V → ~9mA LED current) | 1 | — | $0.05 |
| 7 | Resistor 4.7kΩ | 1/4W 5% TH | Button pull-up to 3.3V | 1 | — | $0.05 |
| 8 | Wire | 30 AWG solid core | Point-to-point perfboard wiring (button ↔ XIAO GPIO, LED ↔ resistor) | ~30cm | — | $1 |
| 9 | Elastic ankle strap | 25mm neoprene or webbing | Rigid saddle insert that locates device over lateral malleolus; Velcro closure | 1 | Amazon | $3–5 |
| 10 | Velcro | 25mm hook-and-loop, self-adhesive | Strap closure; also secures enclosure to strap | 10cm | Amazon | $1 |
| 11 | Conformal coat | MG Chemicals 422B (silicone) | Sweat/moisture protection for all perfboard solder joints and component pads | 1 spray can | Amazon / Mouser | $12 |
| 12 | Strain relief adhesive | Loctite Flex 401 or hot glue stick | Bead along all 4 XIAO castellated pad edges; wire drip loops | 1 tube | Amazon | $5 |
| 13 | Enclosure | 3D-printed TPU Shore A ≥ 90 | Custom shell ~35×25×10mm; holds perfboard + LiPo; integrated strap loops; dorsal LED window | 1 | Self-fabricated (Bambu/Prusa) | ~$2 filament |

**Core total:** ~$45–50

---

## Optional / Recommended Additions

| Item | Part Number | Description | Supplier | Est. Price |
|------|-------------|-------------|----------|------------|
| SPI Flash breakout | Adafruit 4763 (W25Q16JV, 2MB) | Extended session storage: 2MB / 20 bytes/snapshot = 100K snapshots (~unlimited day use). Auto-detected at boot. Wire to XIAO SPI pins. | Adafruit | $4 |
| SWD Debugger | SEGGER J-Link EDU Mini | Hardware breakpoints, SEGGER RTT (low-latency debug log), SystemView thread profiler. Attach to XIAO SWD pads. Essential for firmware debugging. | SEGGER / Mouser | $20 |
| Current probe | Nordic PCA64115 (PPK2) | USB inline current measurement, 1μA resolution. Validates sleep/active power budget without oscilloscope. | Nordic Semi / Mouser | $80 |

---

## IMU Specifications (LSM6DS3TR-C on XIAO Sense)

| Parameter | Value | Relevance to gait |
|-----------|-------|------------------|
| Accelerometer range | ±16g | Heel strike peak: 5–6g; ±16g gives headroom |
| Accelerometer noise density | 90 μg/√Hz | Low enough for step impact detection |
| Gyroscope range | ±2000 dps | Ankle plantarflexion peak: ~200–300 dps; ±2000 dps is overkill but fine |
| Gyroscope noise density | 4 mdps/√Hz | Determines foot angle drift over one step (~0.17° per step — acceptable for V1) |
| ODR (used) | 208 Hz | Closest to 200 Hz in LSM6DS3 ODR table; 5ms temporal resolution |
| FIFO depth | 4KB = 4096 bytes ≈ 341 complete 6-DOF samples | Allows 32-sample watermark → MCU sleeps 154ms between FIFO drains; 341 >> 32 gives ample headroom |
| Interface | I2C (on-board to XIAO) | No external wiring needed; pre-connected on XIAO Sense PCB |
| Supply voltage | 1.8V (internal regulator on XIAO) | No external LDO needed |

---

## Mounting & Coordinate Frame

```
                    ↑ Z (dorsal / up)
                    |
        Lateral     |         Medial
        ankle       |         ankle
   ←——— Y ——————————|——————————————→
   (lateral)        |
                    |    → X (anterior / heel-to-toe)
```

**Mounting rule:** XIAO Sense placed on lateral ankle, USB-C port facing posterior (toward heel).
This ensures:
- X-axis = anterior direction (gait propulsion)
- Y-axis = medial direction (toward opposite ankle)
- Z-axis = dorsal/upward (perpendicular to ground when standing)

**Antenna orientation:** XIAO chip antenna must face **laterally** (away from body) to minimize body absorption at 2.4 GHz.

---

## Mechanical Notes

- **Enclosure material:** TPU Shore A ≥ 90 (rigid enough to transmit heel strike impact to IMU without mechanical low-pass filtering). Avoid soft silicone — it attenuates the signal.
- **IMU-to-ankle standoff:** Minimize air gap between enclosure underside and ankle skin. Every mm of gap is a mechanical low-pass filter on heel strike transients.
- **Solder joint reinforcement:** Apply Loctite Flex 401 bead along all XIAO castellated pad solder joints before first use. Heel strike at running pace = repeated 5–6g shock.
- **Ingress protection:** Conformal coat all exposed solder joints. Seal JST-PH connector with silicone RTV after mating. Target: IPX4 equivalent (splash-resistant).
- **Button debounce:** Running vibration (2–8g) can false-trigger a button. 200ms software debounce minimum in firmware; require 2s hold for long-press (session stop).
