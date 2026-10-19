Import("env")
import os

# Merge bootloader + partition table + boot_app0 + application into a single
# flashable image at 0x000000 (what the browser WebSerial flasher expects).
#
# The esptool package changed between PlatformIO espressif32 6.x and 8.x:
#   6.x -> package "tool-esptoolpy", script  esptool.py, subcommand "merge_bin"
#   8.x -> package "tool-esptool",   native binary "esptool", subcommand "merge-bin"
# Both are supported here so existing envs keep working after a platform bump.

def _find_esptool(env):
    platform = env.PioPlatform()
    candidates = (
        ("tool-esptool", "esptool"),        # espressif32 >= 8.0.0 (esptool v5, native binary)
        ("tool-esptoolpy", "esptool.py"),   # espressif32 <= 6.x (esptool v4, python script)
    )
    for package, binary in candidates:
        package_dir = platform.get_package_dir(package)
        if not package_dir:
            continue
        path = os.path.join(package_dir, binary)
        if os.path.isfile(path):
            return path
    return None


def _flash_mode_for_upload(env):
    """Return the same flash mode PlatformIO's own upload command uses.

    The espressif32 builder maps QIO/QOUT to DIO for the Arduino framework
    (arduino-esp32 builds its bootloader in DIO while booting in QIO), so the
    merged image must use the same value or the ROM bootloader may fail to read
    the flash after a browser flash.
    """
    try:
        # Exported by platformio's builder/main.py for use in upload flags.
        return env.subst("${__get_board_flash_mode(__env__)}").strip('"')
    except Exception:
        mode = env.GetProjectOption("board_build.flash_mode", "dio")
        return "dio" if mode in ("qio", "qout") else mode


def merge_bin(source, target, env):
    firmware = str(target[0])
    board = env.BoardConfig()
    mcu = board.get("build.mcu", "esp32")

    flash_mode = _flash_mode_for_upload(env)
    flash_freq = board.get("build.f_flash", "40000000L").replace("L", "")
    flash_freq_m = str(int(int(flash_freq) / 1000000)) + "m"
    flash_size = board.get("upload.flash_size", "4MB")

    esptool = _find_esptool(env)
    output = os.path.join(env.subst("$BUILD_DIR"), "firmware_merged.bin")

    # Offsets: bootloader 0x0, partition table 0x8000, boot_app0 0xe000 (all
    # supplied by FLASH_EXTRA_IMAGES), application at 0x10000.
    extra = env.get("FLASH_EXTRA_IMAGES", [])
    app_offset = env.subst("$ESP32_APP_OFFSET") or "0x10000"

    print("=== FIRMWARE MERGE ===")
    print(f"  esptool    : {esptool or '<not found>'}")
    print(f"  flash      : mode={flash_mode} freq={flash_freq_m} size={flash_size}")
    for offset, path in extra:
        print(f"  extra image: {offset} -> {env.subst(path)}")
    print(f"  app image  : {app_offset} -> {firmware}")
    print("======================")

    if not esptool:
        print("ERROR: esptool package not found; cannot create merged binary")
        return

    use_v5_cli = os.path.basename(esptool) == "esptool"

    if use_v5_cli:
        # esptool v5: "esptool --chip <mcu> merge-bin -o <out> <opts...> <addr> <file> ..."
        cmd = [
            esptool,
            "--chip", mcu,
            "merge-bin",
            "-o", output,
            "--flash-mode", flash_mode,
            "--flash-freq", flash_freq_m,
            "--flash-size", flash_size,
        ]
    else:
        # esptool v4: "python esptool.py --chip <mcu> merge_bin ..."
        cmd = [
            "$PYTHONEXE", esptool,
            "--chip", mcu,
            "merge_bin",
            "--flash_mode", flash_mode,
            "--flash_freq", flash_freq_m,
            "--flash_size", flash_size,
            "-o", output,
        ]

    for offset, path in extra:
        cmd.extend([offset, env.subst(path)])

    cmd.extend([app_offset, firmware])

    env.Execute(env.VerboseAction(" ".join(cmd), "Merging firmware into single binary"))


def report_merge(source, target, env):
    """Post-merge sanity report: every browser-flash release needs these bytes."""
    output = os.path.join(env.subst("$BUILD_DIR"), "firmware_merged.bin")
    if not os.path.isfile(output):
        print("WARNING: merged firmware not found:", output)
        return
    with open(output, "rb") as f:
        head = f.read(4)
        size = os.fstat(f.fileno()).st_size
    magic = head[0] if head else -1
    print(f"[MERGE] {output} ({size} bytes, magic=0x{magic:02x} "
          f"{'OK' if magic == 0xE9 else 'INVALID'})")


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", merge_bin)
env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", report_merge)
