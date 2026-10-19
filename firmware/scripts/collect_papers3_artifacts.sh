#!/usr/bin/env bash
# Build the InkSight M5Stack PaperS3 firmware and collect flashable artifacts.
#
#   ./scripts/collect_papers3_artifacts.sh [version]
#
# Outputs (firmware/dist/papers3/):
#   inksight-firmware-papers3_s3-<version>.bin   merged image, flash at 0x0
#                                                (browser WebSerial flasher / manual URL)
#   firmware.bin bootloader.bin partitions.bin boot_app0.bin
#                                                for the manual-offset esptool command
#   manifest.json                                esp-web-tools manifest for the merged image
#
# Requires PlatformIO (`pio`) on PATH, or set PIO=/path/to/pio.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV=epd_47_m5papers3_s3
VERSION="${1:-${INKSIGHT_FW_VERSION:-dev}}"
PIO_BIN="${PIO:-pio}"

if ! command -v "$PIO_BIN" >/dev/null 2>&1; then
    echo "error: '$PIO_BIN' not found. Install PlatformIO or set PIO=/path/to/pio" >&2
    exit 1
fi

echo "==> Building $ENV (version: $VERSION)"
"$PIO_BIN" run -e "$ENV"

echo "==> Verifying artifacts"
python3 scripts/check_papers3_artifacts.py --collect --version "$VERSION"

echo
echo "==> Flash with PlatformIO:"
echo "    $PIO_BIN run -e $ENV -t upload"
echo "==> Or with esptool (merged image, offset 0):"
echo "    ./scripts/flash_papers3.sh dist/papers3/inksight-firmware-papers3_s3-$VERSION.bin"
