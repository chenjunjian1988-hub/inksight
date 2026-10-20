#!/usr/bin/env bash
# Build an InkSight 4.7" EPD firmware target and collect flashable artifacts.
#
#   ./scripts/collect_epd47_artifacts.sh [board] [version]
#     board   = paperdiy (default) | papers3
#     version = version label used in the merged file name (default: dev)
#
# Outputs (firmware/dist/<board>/):
#   inksight-firmware-<board>_s3-<version>.bin   merged image, flash at 0x0
#                                                (browser WebSerial flasher / manual URL)
#   firmware.bin bootloader.bin partitions.bin boot_app0.bin
#                                                for the manual-offset esptool command
#   manifest.json                                esp-web-tools manifest for the merged image
#
# Requires PlatformIO (`pio`) on PATH, or set PIO=/path/to/pio.
set -euo pipefail

cd "$(dirname "$0")/.."

BOARD="${1:-paperdiy}"
VERSION="${2:-${INKSIGHT_FW_VERSION:-dev}}"
PIO_BIN="${PIO:-pio}"

case "$BOARD" in
    paperdiy) ENV=epd_47_m5paperdiy_s3 ;;
    papers3)  ENV=epd_47_m5papers3_s3 ;;
    *)
        echo "error: unknown board '$BOARD' (expected: paperdiy | papers3)" >&2
        exit 1
        ;;
esac

if ! command -v "$PIO_BIN" >/dev/null 2>&1; then
    echo "error: '$PIO_BIN' not found. Install PlatformIO or set PIO=/path/to/pio" >&2
    exit 1
fi

echo "==> Building $ENV (board: $BOARD, version: $VERSION)"
"$PIO_BIN" run -e "$ENV"

echo "==> Verifying artifacts"
python3 scripts/check_epd47_artifacts.py --board "$BOARD" --collect --version "$VERSION"

echo
echo "==> Flash with PlatformIO:"
echo "    $PIO_BIN run -e $ENV -t upload"
echo "==> Or with esptool (merged image, offset 0):"
echo "    ./scripts/flash_epd47.sh dist/$BOARD/inksight-firmware-${BOARD}_s3-$VERSION.bin"
