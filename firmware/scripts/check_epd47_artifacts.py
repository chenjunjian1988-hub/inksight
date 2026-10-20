#!/usr/bin/env python3
"""Collect and sanity-check the flashable InkSight 4.7" EPD board artifacts.

Supported boards (both use the same 16MB partition layout and 960x540 panel):

    paperdiy   env epd_47_m5paperdiy_s3   -> dist/paperdiy/
    papers3    env epd_47_m5papers3_s3    -> dist/papers3/

Usage (run from the firmware/ directory):

    python3 scripts/check_epd47_artifacts.py --board paperdiy
    python3 scripts/check_epd47_artifacts.py --board paperdiy --collect --version 0.1.0
    python3 scripts/check_epd47_artifacts.py --board papers3 --collect

What is checked (compile-time only; no hardware access):
  * merged image magic (0xE9) and bootloader header flash params (16MB, DIO/QIO, 80MHz)
  * partition table magic 0xAA50 at 0x8000 and the app/ota layout the firmware expects
  * app image magic 0xE9 at 0x10000 and that it fits the 5MB OTA slot
  * sizes + sha256 of every artifact
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys

BOARDS = {
    "paperdiy": {
        "env": "epd_47_m5paperdiy_s3",
        "dist": os.path.join("dist", "paperdiy"),
        "asset_prefix": "inksight-firmware-paperdiy_s3",
        "display_name": "InkSight PaperDIY",
    },
    "papers3": {
        "env": "epd_47_m5papers3_s3",
        "dist": os.path.join("dist", "papers3"),
        "asset_prefix": "inksight-firmware-papers3_s3",
        "display_name": "InkSight PaperS3",
    },
}

# Partitions from partitions/inksight_16mb_ota.csv
APP_OFFSET = 0x10000
APP_SLOT_SIZE = 0x500000
BOOTLOADER_OFFSET = 0x0
PARTITION_TABLE_OFFSET = 0x8000
BOOT_APP0_OFFSET = 0xE000

FLASH_MODE_NAMES = {0: "QIO", 1: "QOUT", 2: "DIO", 3: "DOUT"}
FLASH_SIZE_NAMES = {
    0: "1MB",
    1: "2MB",
    2: "4MB",
    3: "8MB",
    4: "16MB",
    5: "32MB",
    6: "64MB",
    7: "128MB",
}
FLASH_FREQ_NAMES = {0xF: "80MHz", 0x0: "40MHz", 0x1: "26MHz", 0x2: "20MHz"}

EXPECTED_PARTITION_ROWS = [
    ("nvs", 0x9000, 0x4000),
    ("otadata", 0xD000, 0x2000),
    ("app0", 0x10000, 0x500000),
    ("app1", 0x510000, 0x500000),
    ("spiffs", 0xA10000, 0x5F0000),
]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_at(path: str, offset: int, length: int) -> bytes:
    with open(path, "rb") as f:
        f.seek(offset)
        return f.read(length)


def decode_esp_image_header(blob: bytes) -> dict:
    """ESP32 image header: magic, segment count, flash mode, flash size/freq."""
    if len(blob) < 24:
        raise ValueError("short image header")
    return {
        "magic": blob[0],
        "segments": blob[1],
        "flash_mode": blob[2],
        "flash_size": (blob[3] >> 4) & 0x0F,
        "flash_freq": blob[3] & 0x0F,
        "entry": struct.unpack("<I", blob[4:8])[0],
    }


def parse_partition_table(blob: bytes) -> list[dict]:
    rows = []
    for i in range(0, len(blob), 32):
        entry = blob[i : i + 32]
        if len(entry) < 32:
            break
        # Partition table magic 0xAA50 is stored little-endian (bytes AA 50).
        magic = entry[0] | (entry[1] << 8)
        if magic != 0x50AA:
            break
        ptype, subtype = entry[2], entry[3]
        offset, size = struct.unpack("<II", entry[4:12])
        label = entry[12:28].split(b"\x00")[0].decode("ascii", "replace")
        rows.append(
            {"label": label, "type": ptype, "subtype": subtype, "offset": offset, "size": size}
        )
    return rows


def verify(board: str, collect: bool, version: str) -> int:
    profile = BOARDS[board]
    build_dir = os.path.join(".pio", "build", profile["env"])
    dist_dir = profile["dist"]

    if not os.path.isdir(build_dir):
        print(f"ERROR: build directory not found: {build_dir}")
        return 1

    merged = os.path.join(build_dir, "firmware_merged.bin")
    app = os.path.join(build_dir, "firmware.bin")
    bootloader = os.path.join(build_dir, "bootloader.bin")
    partitions = os.path.join(build_dir, "partitions.bin")
    boot_app0 = os.path.join(build_dir, "boot_app0.bin")

    ok = True

    def fail(msg: str) -> None:
        nonlocal ok
        ok = False
        print(f"  FAIL: {msg}")

    def good(msg: str) -> None:
        print(f"  ok  : {msg}")

    print(f"=== {profile['display_name']} firmware artifacts ({profile['env']}) ===")
    for path in (merged, app, bootloader, partitions):
        if not os.path.isfile(path):
            print(f"ERROR: missing {path} (did `pio run -e {profile['env']}` succeed?)")
            return 1

    # ── merged image at offset 0 ────────────────────────────────────────────
    merged_size = os.path.getsize(merged)
    with open(merged, "rb") as f:
        merged_head = f.read(24)
    try:
        hdr = decode_esp_image_header(merged_head)
    except ValueError as exc:
        fail(f"merged image header unreadable: {exc}")
        return 1

    if hdr["magic"] != 0xE9:
        fail(f"merged image magic 0x{hdr['magic']:02x} != 0xE9")
    else:
        good(f"merged image starts with ESP32 image magic 0xE9 ({merged_size} bytes)")

    if hdr["flash_size"] != 4:
        fail(
            f"merged image flash size = {FLASH_SIZE_NAMES.get(hdr['flash_size'], hdr['flash_size'])} "
            "(expected 16MB; check board_upload.flash_size)"
        )
    else:
        good("merged image header declares 16MB flash")

    if hdr["flash_mode"] not in (0, 2):
        fail(f"merged image flash mode = {FLASH_MODE_NAMES.get(hdr['flash_mode'])}")
    else:
        good(f"merged image flash mode = {FLASH_MODE_NAMES.get(hdr['flash_mode'])}")

    if hdr["flash_freq"] != 0xF:
        fail(f"merged image flash freq = {FLASH_FREQ_NAMES.get(hdr['flash_freq'], hdr['flash_freq'])}")
    else:
        good("merged image flash freq = 80MHz")

    # ── partition table ────────────────────────────────────────────────────
    part_blob = read_at(merged, PARTITION_TABLE_OFFSET, 32 * 8)
    rows = parse_partition_table(part_blob)
    if not rows:
        fail("no valid partition table (magic 0xAA50 LE) at 0x8000")
    else:
        got = [(r["label"], r["offset"], r["size"]) for r in rows]
        for expected in EXPECTED_PARTITION_ROWS:
            if expected not in got:
                fail(f"partition table missing/!= {expected}")
        if all(e in got for e in EXPECTED_PARTITION_ROWS):
            good("partition table at 0x8000 matches partitions/inksight_16mb_ota.csv")

    # ── app image ──────────────────────────────────────────────────────────
    app_size = os.path.getsize(app)
    app_blob = read_at(merged, APP_OFFSET, 24)
    try:
        app_hdr = decode_esp_image_header(app_blob)
    except ValueError as exc:
        fail(f"app header unreadable at 0x{APP_OFFSET:x}: {exc}")
        app_hdr = {"magic": -1}
    if app_hdr.get("magic") != 0xE9:
        fail(f"app image magic at 0x{APP_OFFSET:x} is not 0xE9")
    else:
        good(f"app image at 0x{APP_OFFSET:x} is a valid ESP32 image ({app_size} bytes)")

    if app_size > APP_SLOT_SIZE:
        fail(f"app ({app_size} bytes) does not fit the 5MB OTA slot")
    else:
        good(f"app fits OTA slot ({app_size} / {APP_SLOT_SIZE} bytes)")

    expected_min = APP_OFFSET + app_size
    if merged_size < expected_min:
        fail(f"merged image ({merged_size}) smaller than app end (0x{expected_min:x})")
    else:
        good(f"merged image size 0x{merged_size:x} covers app @0x{APP_OFFSET:x}")

    # boot_app0 presence for the manual-offset esptool command.
    if not os.path.isfile(boot_app0):
        framework_boot_app0 = _find_boot_app0()
        if framework_boot_app0:
            print(f"  note: boot_app0.bin not in build dir; using {framework_boot_app0}")
        else:
            print("  note: boot_app0.bin not found; manual offset command can omit 0xe000 entry")
    else:
        good("boot_app0.bin present")

    # ── report + optionally collect ───────────────────────────────────────
    artifacts = [merged, app, bootloader, partitions]
    if os.path.isfile(boot_app0):
        artifacts.append(boot_app0)

    print("\n=== artifact list ===")
    for path in artifacts:
        print(f"  {path}  {os.path.getsize(path):>9} bytes  sha256={sha256(path)[:16]}…")

    if collect:
        os.makedirs(dist_dir, exist_ok=True)
        flat_name = f"{profile['asset_prefix']}-{version}.bin"
        shutil.copyfile(merged, os.path.join(dist_dir, flat_name))
        for path in (app, bootloader, partitions):
            shutil.copyfile(path, os.path.join(dist_dir, os.path.basename(path)))
        boot_app0_src = boot_app0 if os.path.isfile(boot_app0) else _find_boot_app0()
        if boot_app0_src:
            shutil.copyfile(boot_app0_src, os.path.join(dist_dir, "boot_app0.bin"))

        manifest = {
            "name": profile["display_name"],
            "version": version,
            "builds": [
                {
                    "chipFamily": "ESP32-S3",
                    "parts": [{"path": flat_name, "offset": 0}],
                }
            ],
        }
        manifest_path = os.path.join(dist_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")

        print(f"\n=== collected into {dist_dir}/ ===")
        for name in sorted(os.listdir(dist_dir)):
            print(f"  {name}")

    return 0 if ok else 1


def _find_boot_app0() -> str | None:
    core_dir = os.environ.get("PLATFORMIO_CORE_DIR") or os.path.expanduser(
        "~/.platformio"
    )
    path = os.path.join(
        core_dir,
        "packages",
        "framework-arduinoespressif32",
        "tools",
        "partitions",
        "boot_app0.bin",
    )
    return path if os.path.isfile(path) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--board",
        choices=sorted(BOARDS),
        default="paperdiy",
        help="which 47-inch board profile to verify/collect (default: paperdiy)",
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="copy the artifacts (and a web-flasher manifest.json) into dist/<board>/",
    )
    parser.add_argument(
        "--version",
        default=os.environ.get("INKSIGHT_FW_VERSION", "dev"),
        help="version string used in the artifact file name (default: dev)",
    )
    args = parser.parse_args()
    return verify(args.board, args.collect, args.version)


if __name__ == "__main__":
    sys.exit(main())
