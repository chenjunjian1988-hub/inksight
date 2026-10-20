#include "board_hooks.h"
#include "config.h"

// Default (generic) implementations. M5 PaperS3 / PaperDIY override both hooks
// in epd_driver.cpp's 47" parallel-EPD branch, where M5Unified is available.
#if !defined(BOARD_PROFILE_M5PAPERS3) && !defined(BOARD_PROFILE_M5PAPERDIY)

void boardEnterDeepSleep(int minutes) {
    // No board-specific power sequencing required: main.cpp will arm the generic
    // esp_sleep timer wakeup (and the GPIO button wakeup when available).
    (void)minutes;
}

float boardReadBatteryVoltage() {
    return -1.0f;  // use the generic analogRead(PIN_BAT_ADC) implementation
}

#endif // !BOARD_PROFILE_M5PAPERS3 && !BOARD_PROFILE_M5PAPERDIY
