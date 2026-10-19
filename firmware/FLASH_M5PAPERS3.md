# InkSight on M5Stack PaperS3 (SKU C139)

PlatformIO environment: **`epd_47_m5papers3_s3`**

| | |
|---|---|
| Board | M5Stack PaperS3 (C139) |
| SoC | ESP32-S3R8 — 16 MB flash, 8 MB **OPI** PSRAM (octal) |
| Panel | 4.7" 960×540, 16-gray **ET047TC1**, driven **directly by the ESP32-S3** over an 8-bit parallel bus (no SPI controller, no IT8951) |
| Touch / RTC | GT911 on I2C (SDA 41 / SCL 42 / INT 48), BM8563 RTC on the same bus |
| Power | PMS150G power IC, 1800 mAh battery, USB-C (native USB Serial/JTAG) |
| Firmware | `firmware/`, env `epd_47_m5papers3_s3`, 960×540 1-bit (`bpp=1`) InkSight render buffer |

Board support is provided by two M5Stack libraries, pinned in `platformio.ini`:

* **M5GFX 0.2.33** – `board_M5PaperS3` profile: `Bus_EPD` (8-bit parallel bus) + `Panel_EPD` (16-gray waveform LUTs). Panel support is compiled only when OPI PSRAM is enabled (`CONFIG_SPIRAM_MODE_OCT`), which is why this env needs the `esp32-s3` **qio_opi / opi** memory type.
* **M5Unified 0.2.26** – PaperS3 board profile: PMS150G power sequencing (`POWER_HOLD` GPIO44), BM8563 RTC alarm sleep/wake, battery ADC divider on GPIO3, GT911 touch.

The PlatformIO **platform is pinned to `espressif32@8.0.0`** (arduino-esp32 3.3.12 / ESP-IDF 5.x) for this env only. The 6.x platform (arduino-esp32 2.0.17) does not ship an OPI-PSRAM S3 framework variant with `CONFIG_SPIRAM_MODE_OCT`, so PaperS3 cannot work on it. Other envs keep `[common]`'s unpinned platform exactly as before.

---

## 1. Build

```bash
cd firmware
pio run -e epd_47_m5papers3_s3
```

Or build + collect flashable artifacts in one step:

```bash
cd firmware
./scripts/collect_papers3_artifacts.sh 0.1.0-papers3   # optional version label
```

Output (`.pio/build/epd_47_m5papers3_s3/`):

| File | Contents |
|---|---|
| `firmware_merged.bin` | bootloader + partition table + boot_app0 + app, **flash at 0x0** (what the browser flasher uses) |
| `firmware.bin` | application image, flash at **0x10000** |
| `bootloader.bin` | bootloader, flash at **0x0** |
| `partitions.bin` | partition table, flash at **0x8000** |
| `boot_app0.bin` | OTA selector (from the arduino framework), flash at **0xe000** |

`scripts/collect_papers3_artifacts.sh` copies these to `firmware/dist/papers3/` and generates a WebSerial `manifest.json`:

```
dist/papers3/
  inksight-firmware-papers3_s3-<version>.bin   ← merged image (offset 0)
  firmware.bin  bootloader.bin  partitions.bin  boot_app0.bin
  manifest.json                                ← {"chipFamily":"ESP32-S3","parts":[{"offset":0,...}]}
```

Verify the artifacts (no hardware needed):

```bash
python3 scripts/check_papers3_artifacts.py
# merged magic/header (16MB, DIO, 80MHz), partition table @0x8000, app @0x10000, sizes, sha256
```

---

## 2. Flash over USB-C

The PaperS3's USB-C port is wired to the ESP32-S3 native USB Serial/JTAG peripheral, so it appears on macOS as `/dev/cu.usbmodem*` (Linux `/dev/ttyACM*`). Serial logs from the firmware go to the same USB CDC port at **115200 baud** (`ARDUINO_USB_CDC_ON_BOOT=1`).

### Option A — PlatformIO (recommended)

```bash
cd firmware
pio run -e epd_47_m5papers3_s3 -t upload
pio device monitor -e epd_47_m5papers3_s3      # /dev/cu.usbmodem*
```

### Option B — merged image + esptool (also what the browser flasher writes)

```bash
# macOS example port; check `ls /dev/cu.usbmodem*`
esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0 dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin
```

Convenience wrapper (auto-detects port and esptool v4/v5 syntax):

```bash
./scripts/flash_papers3.sh dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin
```

> esptool v4 (`pip install esptool<5`) uses underscores: `write_flash -z --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0 <image>`. PlatformIO's bundled esptool is v5 and uses dashes, as shown above.

### Option C — separate images (manual offsets)

```
esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0     dist/papers3/bootloader.bin \
  0x8000  dist/papers3/partitions.bin \
  0xe000  dist/papers3/boot_app0.bin \
  0x10000 dist/papers3/firmware.bin
```

### Option D — browser WebSerial flasher (`webapp` → `/flash`)

The flasher writes a single binary at offset `0x0`, so use the **merged** image. Either

* paste a URL to the merged `.bin` into the flasher's *manual firmware URL* field, or
* publish it as a GitHub release asset named `inksight-firmware-papers3_s3-<version>.bin` — `backend/api/shared.py::chip_family_from_asset_name()` maps the `_s3` in that name to `ESP32-S3` and emits `{"parts":[{"offset":0}]}` automatically.

For a local test you can serve the folder and use the manual URL, e.g.
`python3 -m http.server 8000` in `firmware/dist/papers3/`, then use
`http://<your-mac-LAN-IP>:8000/inksight-firmware-papers3_s3-0.1.0-papers3.bin`.

### If the port does not appear / flashing fails

The side button is managed by the PMS150G power IC (it is **not** an ESP32 GPIO):

1. Connect USB-C, then press the side button once (power on). The USB CDC port should enumerate after a few seconds.
2. If esptool cannot sync, put the board in download mode: hold the side button for ~2 s to power off, then reconnect USB while the button is held/quickly after power-on; the ROM bootloader exposes the USB Serial/JTAG port and `esptool --chip esp32s3 --port ... chip-id` should answer.
3. A full chip erase (also wipes WiFi config → next boot goes to the captive portal):
   `esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX erase-flash`
4. Close any serial monitor before flashing (the port is exclusive). `pio device monitor` or Arduino IDE must be closed.

---

## 3. Flash layout (16 MB)

`firmware/partitions/inksight_16mb_ota.csv`:

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

The current build uses **1,846,255 bytes** of the 5 MB app slot (`RAM 45.6%` = 149,492 / 327,680 B, `Flash 35.2%` = 1,846,255 / 5,242,880 B). The app image is 1,903,632 bytes; the merged image is **1,969,168 bytes**.

> OTA is **disabled** for this board (`src/ota.cpp`): official InkSight releases are 400×300 4.2" SPI-panel builds that cannot drive the ET047TC1 panel. Upgrades are USB re-flashes only.

---

## 4. First boot / provisioning

1. Flash the firmware (above) and power the board on with the side button.
2. **No stored WiFi config → the captive portal starts automatically.** The setup screen is drawn on the e-paper panel (this takes a few seconds — a full 16-gray refresh).
3. On a phone/laptop join the Wi-Fi AP `InkSight-XXXXX` (last 5 MAC chars) and open **http://192.168.4.1** (a phone may show a "sign in to network" prompt).
4. In the portal enter:
   * your Wi-Fi SSID + password,
   * the InkSight server URL, e.g. `http://192.168.3.6:8080` — substitute the Mac's **current LAN IP** (`ipconfig getifaddr en0` on macOS) and keep the `:8080` port; the PaperS3 and the Mac must be on the same LAN,
   * city / preferences as requested.
5. The device reboots/connects, fetches `GET /api/render?w=960&h=540&bpp=1&colors=2...`, shows the 1-bit image full-screen, then sleeps.

Re-provisioning on PaperS3: the board has **no ESP32-readable user button** (side button = PMS150G power IC), so the portal is offered when

* there is no stored config, or
* the server URL is empty, or
* **all** saved WiFi networks fail (the device does one quick retry sweep, then opens the portal for 3 minutes), or
* **the backend is unreachable for 3 consecutive refresh cycles** (`PAPERS3_PORTAL_FAILURE_THRESHOLD` in `src/main.cpp`): the firmware persists a failure counter in NVS, keeps displaying the cached image while the backend is down, and after the 3rd consecutive `handleFailure()` it opens the captive portal (auto-timeout 3 min) so the server URL/LAN IP can be corrected. A successful fetch — or opening the portal — resets the counter. This is the no-button recovery path for "my Mac's LAN IP changed".

**Recovery recipes**

| Situation | What to do |
|---|---|
| Server LAN IP changed (e.g. 192.168.3.6 → new IP) | Wait until the device shows the cached image for ~3 refresh cycles; it then opens the `InkSight-XXXXX` AP automatically. Join it, open http://192.168.4.1, update the server URL and save. (Do **not** need USB.) |
| Wrong WiFi credentials stored / device cannot connect at all | The WiFi-failure path opens the portal after one quick retry sweep; alternatively hold the side button to power-cycle and retry. |
| Want a guaranteed clean state (nuclear option) | Erase the NVS partition (0x9000, 16 KB) over USB — this wipes WiFi/server config only, firmware stays:<br>`esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX erase-region 0x9000 0x4000` (esptool v5)<br>`esptool.py --chip esp32s3 -p /dev/cu.usbmodemXXXX erase_region 0x9000 0x4000` (esptool v4)<br>Or erase everything and re-flash the merged image:<br>`esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX erase-flash` then flash again (see §2). The next boot has no config and opens the portal immediately. |

The device tries up to `MAX_WIFI_NETWORKS` (default 5) saved networks in order on every boot; the portal can add/delete networks.

---

## 5. Sleep / wake on PaperS3

* The normal per-cycle sleep is a **BM8563 RTC alarm + ESP32-S3 timer + PMS150G power cut**, handled by `M5.Power.timerSleep(minutes*60)` from `src/epd_driver.cpp::boardEnterDeepSleep()`. The RTC alarm re-powers the board at wake time, so wake behaves like a cold boot; InkSight's NVS state (cycle index, config, cache) survives.
* Wakeup reason after an RTC-alarm power-up is reported as "power on" by the ESP32 (the rail really was cut), which the firmware treats as a normal boot: WiFi → fetch → display → sleep.
* There is **no GPIO button wake** for PaperS3 (`PIN_CFG_BTN = -1`). All button reads go through `configButtonDown()` in `src/config.h`, which returns `false` when no button GPIO exists.
* The periodic 1-minute clock overlay (`updateTimeDisplay()`) is guarded by `epdSupportsPartialRefresh()`; PaperS3 has no cheap partial refresh, so it is skipped to avoid a full refresh every minute.
* `epd_quality` (full 16-gray waveform) is used for the normal per-cycle refresh and every `FULL_REFRESH_INTERVAL` cycles; `epd_text` is used for fast full refreshes (`epdDisplayFast`).

---

## 6. Known limitations / unverified on hardware

No PaperS3 was available while porting; everything below is **compile/link/byte-level verified only**:

* Panel init, waveform timing, orientation and the `0 = black` 1-bit polarity of `pushGrayscaleImage()` are verified by code review against M5GFX's `Panel_EPD`/`copy_grayscale` implementation and M5Stack's official demo, **not** on a physical panel. If the first image is inverted, swap the `TFT_WHITE`/`TFT_BLACK` arguments in `papers3Push1bpp()`; if it is rotated 180°, change `M5.Display.setRotation(1)`.
* BM8563 alarm wake after the PMS150G power cut (full power-cycle wake) is untested. If the device stays asleep, the fallback generic `esp_sleep_enable_timer_wakeup` path is still compiled in after `M5.Power.timerSleep()`; the first thing to check is whether the RTC alarm re-powers the rail (official demo uses the same pattern).
* Battery voltage uses `M5.Power.getBatteryVoltage()` (GPIO3, ratio 2.0); calibrated accuracy is not measured.
* Touch (GT911) is initialised by M5Unified but not used by InkSight's UI yet; a touch-based portal trigger could be added later.
* Audio/voice/vocab-button features are compiled out for this board (no codec, no readable button).
* Deep-sleep current is not measured.
* The 960×540 render path requires the backend to honour `w=960&h=540&bpp=1` (it returns a 1-bit BMP; the firmware strips the BMP header and flips rows). Verified against the firmware parser, not against a live 960×540 backend response.

---

## 7. Files touched for this port

| File | Change |
|---|---|
| `platformio.ini` | new `[env:epd_47_m5papers3_s3]` (m5papers3 platform pin, qio_opi/opi, 16MB partitions, M5GFX/M5Unified deps, LDF include workaround) |
| `src/config.h` | `BOARD_PROFILE_M5PAPERS3` pin map (battery ADC 3, no config button, LED 0), `configButtonDown()` helper |
| `src/epd_driver.cpp` | new `EPD_PANEL_47_M5PAPERS3` branch: M5Unified init, `pushGrayscaleImage` display, EPD sleep, no partial refresh, `boardEnterDeepSleep()`, `boardReadBatteryVoltage()` |
| `src/board_hooks.h/.cpp` | generic no-op deep-sleep/battery hooks so other boards are unchanged |
| `src/display.cpp` | proportional font scaling for the 960×540 panel (setup/diagnostic/AI/preview/error screens) |
| `src/main.cpp` | `configButtonDown()` guards, board sleep hook call, partial-refresh guard for clock overlay, PaperS3 ADC setup |
| `src/network.cpp` | `configButtonDown()` in abort checks, board battery hook + PaperS3 divider formula |
| `src/storage.cpp/.h` | NVS `srv_fail_n` consecutive-failure counter used by the PaperS3 no-button portal recovery |
| `src/ota.cpp` | OTA hard-disabled for `BOARD_PROFILE_M5PAPERS3` |
| `src/network.h` → `src/inksight_network.h` | renamed to avoid macOS/Windows case-insensitive collision with arduino-esp32 3.x `libraries/Network/src/Network.h` |
| `merge_firmware.py` | supports esptool v4 (`tool-esptoolpy`) and v5 (`tool-esptool`), reports merged size/magic |
| `scripts/collect_papers3_artifacts.sh`, `scripts/flash_papers3.sh`, `scripts/check_papers3_artifacts.py` | build/collect/flash/verify helper scripts |
| `dist/papers3/` | generated flashable artifacts (git-ignored) |
