#ifndef INKSIGHT_CONFIG_H
#define INKSIGHT_CONFIG_H

#include <Arduino.h>

#if defined(BOARD_PROFILE_ESP32_C3)
#define PIN_EPD_MOSI   6
#define PIN_EPD_SCK    4
#define PIN_EPD_CS     7
#define PIN_EPD_DC     1
#define PIN_EPD_RST    2
#define PIN_EPD_BUSY   10
#define PIN_BAT_ADC    0
#define PIN_CFG_BTN    9
#define PIN_LED        3
#define PIN_AI_CHAT_SW -1
#elif defined(BOARD_PROFILE_ESP32_C3_WROOM02)
#define PIN_EPD_MOSI   6
#define PIN_EPD_SCK    4
#define PIN_EPD_CS     7
#define PIN_EPD_DC     1
#define PIN_EPD_RST    2
#define PIN_EPD_BUSY   10
#define PIN_BAT_ADC    0
#define PIN_CFG_BTN    9
#define PIN_LED        5
#define PIN_AI_CHAT_SW -1
#elif defined(BOARD_PROFILE_ESP32_WROOM32E)
#define PIN_EPD_MOSI   14
#define PIN_EPD_SCK    13
#define PIN_EPD_CS     15
#define PIN_EPD_DC     27
#define PIN_EPD_RST    26
#define PIN_EPD_BUSY   25
#define PIN_BAT_ADC    35
#define PIN_CFG_BTN    0
#define PIN_LED        2
#define PIN_AI_CHAT_SW 23
#define BOARD_HAS_AUDIO
#elif defined(BOARD_PROFILE_SMT_WROOM32E)
#define PIN_EPD_MOSI   14
#define PIN_EPD_SCK    13
#define PIN_EPD_CS     15
#define PIN_EPD_DC     27
#define PIN_EPD_RST    26
#define PIN_EPD_BUSY   25
#define PIN_BAT_ADC    35
#define PIN_CFG_BTN    0
#define PIN_LED        2
#define PIN_AI_CHAT_SW 4
#define BOARD_HAS_AUDIO
#elif defined(BOARD_PROFILE_SMT_C3)
#define PIN_EPD_MOSI   6
#define PIN_EPD_SCK    4
#define PIN_EPD_CS     7
#define PIN_EPD_DC     1
#define PIN_EPD_RST    2
#define PIN_EPD_BUSY   10
#define PIN_BAT_ADC    0
#ifndef PIN_CFG_BTN
#define PIN_CFG_BTN    9
#endif
#define PIN_LED        5
#define PIN_AI_CHAT_SW -1
#elif defined(BOARD_PROFILE_YD_ESP32_S3_N16R8)
#define PIN_EPD_MOSI   11
#define PIN_EPD_SCK    12
#define PIN_EPD_CS     10
#define PIN_EPD_DC     9
#define PIN_EPD_RST    8
#define PIN_EPD_BUSY   7
#define PIN_BAT_ADC    4
#define PIN_CFG_BTN    0
#define PIN_LED        -1
#define PIN_RGB_LED    48
#define PIN_AI_CHAT_SW -1
#elif defined(BOARD_PROFILE_M5PAPERS3)
// M5Stack PaperS3 (SKU C139): ESP32-S3R8 (16MB flash / 8MB OPI PSRAM), 4.7"
// 960x540 16-gray ET047TC1 e-paper panel driven DIRECTLY by the ESP32-S3 over
// an 8-bit parallel bus (not SPI, not IT8951). Panel, touch and RTC are owned by
// M5GFX's board_M5PaperS3 profile (Bus_EPD + Panel_EPD) which M5Unified
// initialises for us, so the generic SPI e-paper pins are intentionally unused.
// -1 keeps any remaining generic pin handling harmless.
#define PIN_EPD_MOSI   -1
#define PIN_EPD_SCK    -1
#define PIN_EPD_CS     -1
#define PIN_EPD_DC     -1
#define PIN_EPD_RST    -1
#define PIN_EPD_BUSY   -1
#define PIN_BAT_ADC    3    // ADC1 channel 2, external 1:2 divider (M5Unified ratio 2.0)
#define PIN_CFG_BTN    -1   // side button belongs to the PMS150G power IC: NOT a GPIO
#define PIN_LED        0    // status LED
#define PIN_AI_CHAT_SW -1
#define EPD_ROTATION   1    // panel offset_rotation=3 -> rotation 1 renders 960x540 landscape
#define BOARD_HAS_EPD_PARALLEL
#elif defined(BOARD_PROFILE_M5PAPERDIY)
// M5Stack PaperDIY (K159 / K159-B): ESP32-S3R8 (16MB flash / 8MB OPI PSRAM),
// same 4.7" 960x540 16-gray ET047TC1 panel and same 8-bit parallel bus as the
// PaperS3. Differences:
//   * EPD_PWR is switched by the M5PM1 PMIC (GPIO2/PYG2), not a direct ESP32 pin
//     (M5GFX's board_M5PaperDIY autodetect sets it high before panel init);
//   * power/battery/charge state live in the M5PM1 (no PMS150G, no BM8563 RTC,
//     no GT911 touch);
//   * there ARE two user buttons wired to the ESP32: ButtonA=GPIO4, ButtonB=GPIO3,
//     both active LOW (M5Unified configures them as inputs; we add pull-ups).
// Display pins are owned by M5GFX, so the generic SPI e-paper pins stay unset.
#define PIN_EPD_MOSI   -1
#define PIN_EPD_SCK    -1
#define PIN_EPD_CS     -1
#define PIN_EPD_DC     -1
#define PIN_EPD_RST    -1
#define PIN_EPD_BUSY   -1
#define PIN_BAT_ADC    -1   // no direct ADC divider: battery is read through M5PM1 (board hook)
#define PIN_CFG_BTN    4    // ButtonA (active LOW): config/portal button (long press = portal)
#define PIN_LED        -1   // only an M5PM1-driven power/charge LED, not a GPIO
#define PIN_AI_CHAT_SW 3    // ButtonB (active LOW): optional; no audio codec on this board
#define EPD_ROTATION   1    // panel offset_rotation=3 -> rotation 1 renders 960x540 landscape
#define BOARD_HAS_EPD_PARALLEL
#else
#error "Unsupported board profile"
#endif

// Rotation passed to M5.Display.setRotation() for the 47" parallel-EPD profiles.
// The panel config in M5GFX uses offset_rotation=3, so:
//   rotation 0 -> 540x960 portrait, rotation 1 -> 960x540 landscape (what InkSight renders),
//   rotation 3 -> 960x540 landscape rotated 180 degrees (use if the image is upside down).
#ifndef EPD_ROTATION
#define EPD_ROTATION 0
#endif

// Board-agnostic "is the config button pressed" helper.
// M5 PaperS3 has no ESP32-readable user button (its side button is handled by
// the PMS150G power IC), so PIN_CFG_BTN is -1 there and every button read must
// go through this helper. Without it, digitalRead(-1) would look like a
// permanently pressed pin and could wedge the device in the captive portal /
// abort the fetch loop forever. PaperDIY uses this with ButtonA (GPIO4).
static inline bool configButtonDown() {
#if PIN_CFG_BTN >= 0
    return digitalRead(PIN_CFG_BTN) == LOW;
#else
    return false;
#endif
}

#ifndef PIN_RGB_LED
#define PIN_RGB_LED -1
#endif

// ── Display constants ────────────────────────────────────────
// Default for 4.2" E-Paper (400x300, 1-bit).
// Override via build flags: -D EPD_WIDTH=800 -D EPD_HEIGHT=480
// Supported configurations:
//   4.2"  (400x300) - default
//   2.9"  (296x128)
//   5.83" (648x480)
//   7.5"  (800x480)
#ifndef EPD_WIDTH
#define EPD_WIDTH  400
#endif
#ifndef EPD_HEIGHT
#define EPD_HEIGHT 300
#endif

static const int W = EPD_WIDTH;
static const int H = EPD_HEIGHT;
static const int ROW_BYTES   = W / 8;
static const int ROW_STRIDE  = (ROW_BYTES + 3) & ~3;  // BMP row stride (4-byte aligned)
static const int IMG_BUF_LEN = ROW_BYTES * H;
/** Preprocessor image buffer size for #if (IMG_BUF_LEN is not a cpp constant). */
#define INKSIGHT_IMG_BUF_BYTES_MACRO ((EPD_WIDTH / 8) * (EPD_HEIGHT))

#ifndef EPD_BPP
#define EPD_BPP 1
#endif
static const int COLOR_BUF_LEN = (W * H) / 4;  // 2bpp: 4 pixels per byte

// Shared framebuffers (defined in main.cpp)
extern uint8_t imgBuf[];
#if EPD_BPP >= 2
extern uint8_t *colorBuf;
extern bool useColorBuf;
bool ensureColorBuf();
#endif

// ── Refresh strategy ─────────────────────────────────────────
static const int FULL_REFRESH_INTERVAL = 10;  // Full refresh every N updates to clear ghosting

// ── Config defaults ─────────────────────────────────────────
static const char *DEFAULT_SERVER  = "";  // Must be set via captive portal
static const int   WIFI_TIMEOUT    = 15000;   // ms
static const int   MAX_WIFI_NETWORKS = 5;     // Max saved WiFi credentials (tried in order on boot)
static const int   HTTP_TIMEOUT    = 30000;   // ms
static const int   CFG_BTN_HOLD_MS = 2000;    // Long press duration to trigger config mode
static const int   AI_CHAT_BTN_HOLD_MS = 3000; // Long press duration to enter AI chat mode
static const int   VOCAB_ENTER_HOLD_MS = 2000; // Long press duration to enter vocab review
static const int   VOCAB_BTN_HOLD_MS = 1500;  // Long press duration to submit vocab rating
static const int   VOCAB_EXIT_HOLD_MS = 5000; // Long press duration to exit vocab review
static const int   SHORT_PRESS_MIN_MS = 50;   // Minimum short press duration (debounce)
static const int   LIVE_POLL_MS = 5000;       // Poll interval for pending remote actions
static const int   LIVE_WIFI_RETRY_MS = 5000; // Retry interval when WiFi is disconnected
static const unsigned long TEMP_ONLINE_WINDOW_MS = 10UL * 60UL * 1000UL;
static const unsigned long PORTAL_AUTO_TIMEOUT_MS = 3UL * 60UL * 1000UL;
static const unsigned long PORTAL_MANUAL_TIMEOUT_MS = 10UL * 60UL * 1000UL;
static const unsigned long HEARTBEAT_INTERVAL_MS = 10UL * 60UL * 1000UL;
static const int   MAX_RETRY_COUNT = 5;       // Max retries before deep sleep
// WiFi -> captive portal fallback: when ALL saved networks fail to connect,
// do this many quick in-place retry sweeps (no reboot) before opening the AP.
// Keeps the portal fast to appear (user is likely waiting to reconfigure)
// while still riding out a brief blip such as a router rebooting.
static const int           WIFI_PORTAL_RETRY_SWEEPS   = 1;
static const unsigned long WIFI_PORTAL_RETRY_DELAY_MS = 3000;
// Progressive retry delays in seconds: 5s, 15s, 30s, 60s, 120s
static const int   RETRY_DELAYS[] = {5, 15, 30, 60, 120};

// ── Time zone ───────────────────────────────────────────────
#define NTP_UTC_OFFSET  (8 * 3600)  // UTC+8 (China Standard Time), adjust for your region

// ── Debug mode ──────────────────────────────────────────────
#define DEBUG_MODE 0  // Set to 1 for fast refresh (1 min), 0 for user config
#if DEBUG_MODE
static const int DEBUG_REFRESH_MIN = 1;  // 1 minute for debugging
#endif

// ── Time display region (partial refresh area) ──────────────
// Proportional to screen size (scales across 2.9"/4.2"/7.5")
#define TIME_RGN_X0   (0)
#define TIME_RGN_X1   ((W * 14 / 100) & ~7)
#define TIME_RGN_Y0   (H * 2 / 100)
#define TIME_RGN_Y1   (H * 8 / 100)

#define TIME_TEXT_X   (W * 1 / 100)
#define TIME_TEXT_Y   (H * 4 / 100)

#ifndef AUTO_BOOT_AI_CHAT
#define AUTO_BOOT_AI_CHAT 0
#endif
#ifndef VOCAB_REVIEW_BUILD
#define VOCAB_REVIEW_BUILD 0
#endif

#endif // INKSIGHT_CONFIG_H
