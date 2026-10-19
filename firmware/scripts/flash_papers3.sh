#!/usr/bin/env bash
# Flash an InkSight M5Stack PaperS3 firmware image over the native USB-C port.
#
#   ./scripts/flash_papers3.sh [path/to/image.bin] [serial-port]
#
# Defaults to the merged image produced by collect_papers3_artifacts.sh and to
# the first /dev/cu.usbmodem* port (macOS). Works with both esptool v4 (`write_flash`,
# underscore options) and esptool v5 (`write-flash`, dash options).
#
# The merged image already contains bootloader + partition table + boot_app0 +
# application and is written at offset 0x0. See FLASH_M5PAPERS3.md for the
# separate-offset command if you prefer individual images.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${1:-$(ls -1 dist/papers3/inksight-firmware-papers3_s3-*.bin 2>/dev/null | head -1 || true)}"
PORT="${2:-}"
if [ -z "$PORT" ]; then
    PORT="$(ls /dev/cu.usbmodem* 2>/dev/null | head -1 || true)"
    if [ -z "$PORT" ]; then
        PORT="$(ls /dev/ttyACM* 2>/dev/null | head -1 || true)"
    fi
fi

if [ -z "$IMAGE" ] || [ ! -f "$IMAGE" ]; then
    echo "error: firmware image not found. Build it first:" >&2
    echo "       ./scripts/collect_papers3_artifacts.sh" >&2
    exit 1
fi
if [ -z "$PORT" ]; then
    echo "error: no USB serial port found. Plug the PaperS3 into USB-C and retry," >&2
    echo "       or pass the port explicitly: $0 \"$IMAGE\" /dev/cu.usbmodemXXXX" >&2
    echo "       (macOS: ls /dev/cu.usbmodem*  |  Linux: ls /dev/ttyACM*)" >&2
    exit 1
fi

ESPTOOL_BIN="${ESPTOOL:-esptool}"
if ! command -v "$ESPTOOL_BIN" >/dev/null 2>&1; then
    if command -v esptool.py >/dev/null 2>&1; then
        ESPTOOL_BIN=esptool.py
    else
        echo "error: esptool not found. Install it with: pip install esptool" >&2
        exit 1
    fi
fi

VERSION_LINE="$("$ESPTOOL_BIN" version 2>&1 | head -1 || true)"
MAJOR="$(printf '%s' "$VERSION_LINE" | sed -n 's/.*v\([0-9][0-9]*\)\..*/\1/p')"
[ -n "$MAJOR" ] || MAJOR=4

echo "==> esptool : $VERSION_LINE"
echo "==> port    : $PORT"
echo "==> image   : $IMAGE ($(wc -c <"$IMAGE" | tr -d ' ') bytes)"

if [ "$MAJOR" -ge 5 ]; then
    # esptool v5: hyphenated commands/options
    exec "$ESPTOOL_BIN" --chip esp32s3 --port "$PORT" --baud 921600 \
        write-flash -z \
        --flash-mode dio --flash-freq 80m --flash-size 16MB \
        0x0 "$IMAGE"
else
    # esptool v4: underscore commands/options
    exec "$ESPTOOL_BIN" --chip esp32s3 --port "$PORT" --baud 921600 \
        write_flash -z \
        --flash_mode dio --flash_freq 80m --flash_size 16MB \
        0x0 "$IMAGE"
fi
