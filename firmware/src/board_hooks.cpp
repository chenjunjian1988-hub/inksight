#include "board_hooks.h"
#include "config.h"

// Default (generic) implementations. M5 PaperS3 overrides both hooks in
// epd_driver.cpp's BOARD_PROFILE_M5PAPERS3 branch, where M5Unified is available.
#if !defined(BOARD_PROFILE_M5PAPERS3)

void boardEnterDeepSleep(int minutes) {
    // No board-specific power sequencing required: main.cpp will arm the generic
    // esp_sleep timer wakeup (and the GPIO button wakeup when available).
    (void)minutes;
}

float boardReadBatteryVoltage() {
    return -1.0f;  // use the generic analogRead(PIN_BAT_ADC) implementation
}

#endif // !BOARD_PROFILE_M5PAPERS3
