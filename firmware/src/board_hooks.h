#ifndef INKSIGHT_BOARD_HOOKS_H
#define INKSIGHT_BOARD_HOOKS_H

// ── Board-specific power / PMIC hooks ───────────────────────
// Most InkSight boards are plain ESP32/ESP32-C3 modules where:
//   * deep sleep = esp_sleep_enable_timer_wakeup() (+ optional GPIO button wake)
//   * battery voltage = analogRead(PIN_BAT_ADC) with a 1:2 divider
// M5Stack PaperS3 is different: the side button and the actual power cut are
// handled by a PMS150G power IC, and a BM8563 RTC alarm is what re-powers the
// board at wake time. Those behaviours live in board hooks so main.cpp and
// network.cpp stay generic and the other board profiles are untouched
// (board_hooks.cpp provides the no-op defaults).

// Board-specific deep sleep transition.
// Returns immediately on boards that should use the generic esp_sleep flow in
// main.cpp::enterDeepSleep(). On M5 PaperS3 it arms the BM8563 RTC alarm +
// ESP32-S3 timer wake and powers the board down through the PMS150G, so it
// never returns.
void boardEnterDeepSleep(int minutes);

// Board-specific battery voltage. Returns a negative value when the generic
// ADC path in network.cpp::readBatteryVoltage() should be used instead.
float boardReadBatteryVoltage();

#endif // INKSIGHT_BOARD_HOOKS_H
