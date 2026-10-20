# InkSight on M5Stack PaperDIY (K159 / K159-B)

PlatformIO environment: **`epd_47_m5paperdiy_s3`**

| | |
|---|---|
| Board | M5Stack PaperDIY (K159 / K159-B) |
| SoC | ESP32-S3R8 — 16 MB flash, 8 MB **OPI** PSRAM (octal), native USB-Serial/JTAG |
| Panel | 4.7" 960×540, 16-gray **ET047TC1**, driven **directly by the ESP32-S3** over an 8-bit parallel bus (same bus pins as PaperS3; no SPI controller, no IT8951) |
| Display power | `EPD_PWR` is switched by the **M5PM1** PMIC (GPIO2/PYG2), not a direct ESP32 pin. M5GFX's `board_M5PaperDIY` autodetect sets it high during panel bring-up. |
| PMIC | **M5PM1** over I2C (addr 0x6E, SDA 42 / SCL 41): battery + charge state + power rails + shutdown. No PMS150G, no BM8563 RTC chip, no GT911 touch. |
| Buttons | **ButtonA = GPIO4**, **ButtonB = GPIO3**, both active LOW (the side power button is handled by the M5PM1, not by the ESP32) |
| Battery | 140 mAh, read through the M5PM1 (`M5.Power.getBatteryVoltage()` → `M5.Power.M5pm1.getBatteryVoltage()`) |
| Firmware | `firmware/`, env `epd_47_m5paperdiy_s3`, 960×540 1-bit (`bpp=1`) InkSight render buffer |

The firmware reuses the 4.7" parallel-EPD driver written for the PaperS3 — same M5GFX
`Bus_EPD` + `Panel_EPD` 16-gray waveform path, same `pushGrayscaleImage` 1-bit
protocol, same 16 MB partition layout. Only the board profile differs
(`BOARD_PROFILE_M5PAPERDIY`): PMIC/battery/buttons/sleep handling.

### PaperDIY vs PaperS3 (what the firmware changes)

| | PaperDIY (K159) | PaperS3 (C139) |
|---|---|---|
| Display panel / bus | ET047TC1, 8-bit parallel (identical) | ET047TC1, 8-bit parallel |
| EPD power switch | M5PM1 GPIO2 | ESP32 GPIO46 (PMS150G) |
| Power IC | M5PM1 (I2C 0x6E) | PMS150G |
| RTC | none (M5PM1 keeps time not used) | BM8563 (I2C) |
| Touch | none | GT911 (I2C, INT 48) |
| User buttons | **ButtonA GPIO4, ButtonB GPIO3** | none readable by ESP32 |
| Battery | 140 mAh via M5PM1 ADC | 1800 mAh via GPIO3 divider |
| Deep sleep | ESP32-S3 timer deep sleep, M5PM1 keeps rails; ButtonA wake | BM8563 alarm + timer + PMS150G power pulse |
| `BOARD_PROFILE_*` | `BOARD_PROFILE_M5PAPERDIY` | `BOARD_PROFILE_M5PAPERS3` |

---

## 1. Build

```bash
cd firmware
pio run -e epd_47_m5paperdiy_s3
```

Or build + collect flashable artifacts in one step:

```bash
cd firmware
./scripts/collect_epd47_artifacts.sh paperdiy 0.1.0-paperdiy
```

Platform: `espressif32@8.0.0` (arduino-esp32 3.3.12 / IDF 5.x), pinned for this env
only; `qio_opi` + `psram_type=opi` is required because M5GFX refuses to bring up this
panel without OPI PSRAM (`CONFIG_SPIRAM_MODE_OCT`). Libraries are pinned to
M5GFX 0.2.33 + M5Unified 0.2.26, the versions that contain `board_M5PaperDIY`.
The `[common]` platform stays unpinned so all other boards are unchanged.

Output (`.pio/build/epd_47_m5paperdiy_s3/`):

| File | Contents |
|---|---|
| `firmware_merged.bin` | bootloader + partition table + boot_app0 + app, **flash at 0x0** (what the browser flasher uses) |
| `firmware.bin` | application image, flash at **0x10000** |
| `bootloader.bin` | bootloader, flash at **0x0** |
| `partitions.bin` | partition table, flash at **0x8000** |
| `boot_app0.bin` | OTA selector (from the arduino framework), flash at **0xe000** |

Current build: **RAM 45.6 %** (149,484 / 327,680 B), **Flash 35.1 %**
(1,842,599 / 5,242,880 B app slot), app image 1,899,824 bytes, merged image
**1,965,360 bytes**.

`scripts/collect_epd47_artifacts.sh paperdiy` copies these to `firmware/dist/paperdiy/`
and generates a WebSerial `manifest.json`:

```
dist/paperdiy/
  inksight-firmware-paperdiy_s3-<version>.bin   ← merged image (offset 0)
  firmware.bin  bootloader.bin  partitions.bin  boot_app0.bin
  manifest.json                                 ← {"chipFamily":"ESP32-S3","parts":[{"offset":0,...}]}
```

Verify the artifacts (no hardware needed):

```bash
python3 scripts/check_epd47_artifacts.py --board paperdiy
# merged magic/header (16MB, DIO, 80MHz), partition table @0x8000, app @0x10000, sizes, sha256
```

---

## 2. Flash over USB-C

The PaperDIY's USB-C port is wired to the ESP32-S3 native USB-Serial/JTAG peripheral;
on macOS it appears as `/dev/cu.usbmodem*` (Linux `/dev/ttyACM*`). The unit used during
development enumerated as `/dev/cu.usbmodem101` with MAC `b8:1f:3f:b8:54:2c`.
Firmware serial logs go to the same USB CDC port at **115200 baud**
(`ARDUINO_USB_CDC_ON_BOOT=1`).

**Download mode:** long-press the bottom power button for ~2 s until the red LED
blinks, then release; with USB-C connected the ROM bootloader exposes the USB
Serial/JTAG port. (A normal reset/power cycle also enumerates the port when the
installed firmware does not hold it.)

### Option A — PlatformIO (recommended)

```bash
cd firmware
pio run -e epd_47_m5paperdiy_s3 -t upload
pio device monitor -e epd_47_m5paperdiy_s3      # /dev/cu.usbmodem*
```

### Option B — merged image + esptool (what the browser flasher writes)

```bash
# esptool v5 (PlatformIO 8.x bundles v5; a standalone v5.6.0 also works)
esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0 dist/paperdiy/inksight-firmware-paperdiy_s3-0.1.0-paperdiy.bin
```

Convenience wrapper (auto-detects port and esptool v4/v5 syntax):

```bash
./scripts/flash_epd47.sh dist/paperdiy/inksight-firmware-paperdiy_s3-0.1.0-paperdiy.bin
```

> esptool v4 (`pip install "esptool<5"`) uses underscores:
> `write_flash -z --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0 <image>`.

### Option C — separate images (manual offsets)

```
esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0     dist/paperdiy/bootloader.bin \
  0x8000  dist/paperdiy/partitions.bin \
  0xe000  dist/paperdiy/boot_app0.bin \
  0x10000 dist/paperdiy/firmware.bin
```

### Option D — browser WebSerial flasher (`webapp` → `/flash`)

The flasher writes a single binary at offset `0x0`, so use the **merged** image.
Either paste a URL to the merged `.bin` into the flasher's *manual firmware URL*
field, or publish it as a GitHub release asset named
`inksight-firmware-paperdiy_s3-<version>.bin` — `backend/api/shared.py::chip_family_from_asset_name()`
maps the `_s3` in that name to `ESP32-S3` and emits `{"parts":[{"offset":0}]}`
automatically. For a local test serve the folder and use the manual URL, e.g.
`python3 -m http.server 8000` in `firmware/dist/paperdiy/`.

### Recovery

The Lead keeps a full 16 MB factory backup at
`firmware/backups/paperdiy-factory-full.bin` (git-ignored).

```bash
# Restore the complete factory image (bootloader + partition table + factory app)
esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0 firmware/backups/paperdiy-factory-full.bin

# Or just wipe everything and re-flash InkSight
esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX erase-flash
./scripts/flash_epd47.sh dist/paperdiy/inksight-firmware-paperdiy_s3-0.1.0-paperdiy.bin
```

Note: InkSight's 16 MB layout differs from the factory PaperDIY layout
(factory: nvs 0x9000/0x6000, phy_init 0xf000/0x1000, factory app 0x10000/0xff0000;
InkSight: dual OTA layout with app0/app1 5 MB each + spiffs, see §3). Flashing the
InkSight merged image replaces the factory bootloader/partition table at 0x0/0x8000,
which is why the full backup exists for recovery.

---

## 3. Flash layout (16 MB)

`firmware/partitions/inksight_16mb_ota.csv` (same for PaperDIY and PaperS3):

| Name | Type | Offset | Size |
|---|---|---|---|
| bootloader | — | `0x0` | ~20 KB |
| partition table | — | `0x8000` | 4 KB |
| nvs | data/nvs | `0x9000` | `0x4000` (16 KB) |
| boot_app0 | — | `0xe000` | 8 KB (inside the `otadata` region) |
| otadata | data/ota | `0xd000` | `0x2000` (8 KB) |
| app0 (OTA slot 0) | app/ota_0 | `0x10000` | `0x500000` (5 MB) |
| app1 (OTA slot 1) | app/ota_1 | `0x510000` | `0x500000` (5 MB) |
| spiffs | data/spiffs | `0xa10000` | `0x5f0000` (~5.9 MB) |

> OTA is **disabled** for this board (`src/ota.cpp`): official InkSight releases are
> 400×300 4.2" SPI-panel builds that cannot drive the ET047TC1 panel. Upgrades are
> USB re-flashes only.

---

## 4. First boot / provisioning

1. Flash the firmware (above) and power the board on with the bottom power button.
2. **No stored WiFi config → the captive portal starts automatically.** The setup
   screen is drawn on the e-paper panel (a full 16-gray refresh takes a few seconds).
3. On a phone/laptop join the Wi-Fi AP `InkSight-XXXXX` (last 5 MAC chars) and open
   **http://192.168.4.1**.
4. In the portal enter:
   * your Wi-Fi SSID + password,
   * the InkSight server URL, e.g. `http://192.168.3.6:8080` — substitute the Mac's
     **current LAN IP** (`ipconfig getifaddr en0` on macOS) and keep the `:8080` port,
   * city / preferences as requested.
5. The device reboots/connects, fetches `GET /api/render?w=960&h=540&bpp=1&colors=2...`,
   shows the 1-bit image full-screen, then sleeps.

### Buttons (PaperDIY has real user buttons)

| Button | Pin | Behaviour |
|---|---|---|
| **ButtonA** | GPIO4 | Config/portal button. **Hold ≥ 2 s while awake → captive portal.** **Hold at power-on → force portal.** Short press while awake: no action. As a deep-sleep wake source: pressing it wakes the device (10-minute temporary-online window). |
| **ButtonB** | GPIO3 | Long-press ≥ 3 s → shows "AI CHAT / unsupported on this board" (there is no audio codec on this board; the AI-chat feature is compiled out). Otherwise unused. |

The normal no-button recovery path from the PaperS3 port also stays active: after
**3 consecutive fetch/server failures** across sleep cycles the device reopens the
captive portal automatically (NVS counter `srv_fail_n`), so a changed Mac LAN IP is
recoverable even without pressing anything. Pressing ButtonA (long) is the faster way.

---

## 5. Sleep / wake on PaperDIY

* `enterDeepSleep()` → `boardEnterDeepSleep()` for this board just logs and returns,
  so the **generic** ESP32-S3 deep-sleep path runs: `esp_sleep_enable_timer_wakeup()`
  + ext1 wakeup on ButtonA (GPIO4) + `esp_deep_sleep_start()`.
* The **M5PM1 keeps the 3V3 rail up** during deep sleep (it only cuts power on an
  explicit shutdown), so the timer/button wake works and the panel keeps its image.
* Wake from the button is treated like a normal wake: the device refreshes content
  and opens a 10-minute temporary-online window (same behaviour as other InkSight
  boards with a config button).
* Deeper sleep alternative (not used, M5Unified 0.2.26 has no `M5PM1_Class::timerSet`):
  a newer M5PM1 API can do `timerSet(seconds, M5PM1_TIM_ACTION_POWERON)` +
  `shutdown()` for a full rail cut with PMIC power-on timer.

---

## 6. Expected boot log (USB CDC, 115200)

```
=== InkSight ===
[EPD] PaperDIY init: board=<n> display=960x540 rotation=1 psram=<bytes>
EPD ready
Retry count: 0/5
[WIFI] ...
Fetching image...
GET http://<server>/api/render?...
BMP OK  64800 bytes
Displaying image...
smartDisplay: full refresh (cycle 0)
Display done
Boot complete, entering deep sleep for <N> min
[SLEEP] PaperDIY: ESP32-S3 timer deep sleep for <N> min (M5PM1 keeps rails; ButtonA GPIO4 wake armed by main.cpp)
```

Things to watch on first hardware boot:

* **Rotation**: the firmware sets `EPD_ROTATION = 1` and expects `display=960x540`.
  If the log prints `540x960`, change `EPD_ROTATION` to `0` in `src/config.h`
  (per-profile macro) and rebuild; if the image is landscape but upside down, use `3`.
* **Panel bring-up**: M5GFX autodetect must log `[Autodetect] board_M5PaperDIY`
  (ESP-IDF log level `I`, may be suppressed by Arduino log verbosity). If the
  display stays blank, check that the M5PM1 is found on I2C 42/41 and that OPI PSRAM
  is active (`psram` value in the `[EPD]` line must be ~8 MB, not 0).
* **Polarity**: 1-bit mapping is `0 = black ink` (`TFT_WHITE` foreground). If the
  first image is inverted, swap the two colour arguments in `epd47Push1bpp()`.
* **Battery**: `[BAT] PaperDIY vbat=x.xxV` should be ~3.7–4.2 V. 0 V means the
  M5PM1 BAT_ADC read failed (check `M5.Power.getBatteryVoltage()` / PMIC I2C).
* **Deep sleep**: after `[SLEEP] ...` the board should stay off the USB bus and wake
  at the configured interval (default 60 min) or on ButtonA.

---

## 7. Known limitations / unverified on hardware

Everything in this port is compile/link/byte-level verified; the Lead performs the
hardware flashing/verification. Still to confirm on hardware:

* Panel orientation (`EPD_ROTATION=1` → 960×540) and 1-bit polarity on the PaperDIY.
* M5PM1-based `EPD_PWR` bring-up timing (M5GFX autodetect sets M5PM1 GPIO2 high; the
  panel may need a short delay before the first refresh on some units).
* Battery voltage accuracy through the M5PM1 BAT_ADC (140 mAh pack) and charge state.
* Deep-sleep current and wake reliability with the M5PM1 rails kept up.
* Button wake: pressing ButtonA during deep sleep should wake the device (ext1 wake
  on GPIO4); the wake cause is reported as `[WAKE] Wakeup from button/GPIO`.
* No touch panel and no audio codec on this board (features compiled out).
* 960×540 `/api/render` round-trip depends on the backend accepting `w=960&h=540&bpp=1`.

---

## 8. Files relevant to this port

| File | Change |
|---|---|
| `platformio.ini` | `[env:epd_47_m5paperdiy_s3]` (same platform/libs/16 MB layout as PaperS3) |
| `src/config.h` | `BOARD_PROFILE_M5PAPERDIY` profile (ButtonA/GPIO4, ButtonB/GPIO3, PIN_BAT_ADC=-1, `EPD_ROTATION=1` for both 47" profiles) |
| `src/epd_driver.cpp` | 47" branch generalized to PaperS3 **or** PaperDIY: board-conditional RTC init, `EPD_ROTATION`, ButtonA/B `INPUT_PULLUP`, PaperDIY deep-sleep hook, M5PM1 battery |
| `src/board_hooks.cpp` | generic no-op hooks only for boards other than PaperS3/PaperDIY |
| `src/network.cpp` | battery hook first; `PIN_BAT_ADC < 0` profiles return 0 V instead of sampling an invalid pin |
| `src/main.cpp` | 47" portal-recovery guards cover PaperDIY too; button long-press portal path works via ButtonA |
| `src/ota.cpp` | OTA disabled for PaperS3 **and** PaperDIY |
| `scripts/collect_epd47_artifacts.sh`, `scripts/flash_epd47.sh`, `scripts/check_epd47_artifacts.py` | build/collect/flash/verify helper scripts (board = `paperdiy` or `papers3`) |
