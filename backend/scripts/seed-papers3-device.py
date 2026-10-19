#!/usr/bin/env python3
"""为 M5Stack PaperS3（960x540，1-bit 黑白）预置 InkSight 设备配置。

它做四件事：
  1. 通过 /api/device/<MAC>/token 为设备申请/复用 device token（与固件同一流程，无需登录）；
  2. 通过 POST /api/config 写入这台设备的配置（模式、刷新策略、城市、960x540 等）；
  3. 可选：在本地创建一个账号并把设备绑定到该账号（--no-bind 可关闭）。
     绑定后设备第一次请求 /api/render 就直接出内容；不绑定则设备显示配对码，
     需要用户在 WebApp 注册/登录后到「设备配置页」输入配对码完成绑定；
  4. 打印设备应填写的后端地址（Mac 的局域网 IP:8080）和 WebApp 地址。

用法（在本仓库根目录）：
  backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF
  backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF --no-bind
  backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF \
      --server-url http://192.168.3.6:8080 --city 上海 --modes WEATHER,CALENDAR,DAILY

也可以直接在 backend 目录下运行：
  cd backend && .venv/bin/python scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF

（仓库根目录的 scripts/seed-papers3-device.py 是一个兼容入口，会转发到本文件。）

设备 MAC 的获取方式：
  - 刷机后串口日志里会打印 MAC；
  - 或者设备进入配网热点（InkSight-XXXXX）后，在配网页 /info 里查看；
  - 也可以先随便填一个合法格式的 MAC 跑一遍（例如 --mac AA:BB:CC:DD:EE:FF），
    之后用真实 MAC 再跑一次即可（脚本幂等）。

注意：设备与 Mac 必须在同一个 Wi-Fi；macOS 若弹出防火墙提示请允许 Python 接受连接。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import socket
import string
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
# 默认只启用「不需要 LLM API Key」的模式（静态 / 外部数据 / 计算类），
# 这样在还没配置 DEEPSEEK_API_KEY 的本地部署里设备也能正常出图。
# 配置好 Key 之后，可以在 WebApp 配置页追加 POETRY / ZEN / QUOTE 等 LLM 模式。
DEFAULT_MODES = ["WEATHER", "CALENDAR", "DAILY", "MEMO"]
DEFAULT_MEMO_TITLE = "今日待办"
DEFAULT_MEMO_TEXT = "1. 给 PaperS3 上电\n2. 打开 WebApp 配置页\n3. 开始使用 InkSight"
SCREEN_SIZE = "960x540"
TIMEZONE = "Asia/Shanghai"


# ────────────────────────── 小工具 ──────────────────────────


def _detect_lan_ip() -> str:
    """返回本机局域网 IPv4（优先 en0，然后 en1，最后用 UDP 探测）。"""
    for iface in ("en0", "en1", "en2"):
        try:
            out = subprocess.check_output(
                ["ipconfig", "getifaddr", iface],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            out = ""
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", out) and not out.startswith("127."):
            return out
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        finally:
            sock.close()
    except OSError:
        return "127.0.0.1"


def _http_json(
    method: str,
    url: str,
    payload: Optional[Any] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    data = None
    hdrs: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:  # 4xx/5xx
        raw = exc.read()
        status = exc.code
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"无法连接后端 {url}：{exc.reason}\n"
            f"请先在另一个终端启动后端：\n"
            f"  cd {REPO_ROOT}/backend && .venv/bin/python -m uvicorn api.index:app --host 0.0.0.0 --port 8080"
        ) from exc
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text) if text else {}
    except json.JSONDecodeError:
        return status, text


async def _bind_device_to_local_user(
    mac: str, username: str, password: str, nickname: str
) -> dict[str, Any]:
    """直接写后端 SQLite：创建（或复用）本地账号，并把设备绑定成该账号的 owner。

    这是本地自托管场景的“一步到位”快捷方式；走 WebApp 的配对码流程同样可以完成绑定。
    """
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(BACKEND_DIR)  # 让 backend/.env 与 inksight.db 的定位与后端进程一致
    from core.config_store import (  # noqa: PLC0415  (延迟导入，避免脚本永远依赖 venv)
        bind_device,
        create_user,
        get_user_by_username,
        init_db,
        init_user_api_quota,
    )
    from core.db import close_all  # noqa: PLC0415

    await init_db()
    try:
        user = await get_user_by_username(username)
        created = False
        if user is None:
            user_id = await create_user(username, password)
            if user_id is None:
                raise RuntimeError(f"创建本地账号失败：用户名 {username!r} 已存在")
            created = True
        else:
            user_id = int(user["id"])
        # 与 /api/auth/register 保持一致：初始化 50 次免费额度（幂等，已存在则跳过）。
        # 否则 DAILY / CALENDAR 这类含 LLM 步骤的模式会被计费逻辑拦成「额度已用完」。
        await init_user_api_quota(user_id, free_quota=50)
        result = await bind_device(user_id, mac, nickname=nickname)
        return {
            "created": created,
            "username": username,
            "password": password if created else None,
            "user_id": user_id,
            "status": result.get("status"),
            "role": result.get("role"),
        }
    finally:
        await close_all()


def _random_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ────────────────────────── 主流程 ──────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="为 M5Stack PaperS3（960x540）预置 InkSight 设备配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mac", required=True, help="设备 MAC，格式 AA:BB:CC:DD:EE:FF")
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8080",
        help="本机后端地址（脚本自己调用），默认 http://127.0.0.1:8080",
    )
    parser.add_argument(
        "--server-url",
        default=None,
        help="写进设备/文档的后端地址，默认 http://<本机局域网IP>:8080",
    )
    parser.add_argument(
        "--web-url",
        default=None,
        help="WebApp 地址，默认 http://<本机局域网IP>:3000",
    )
    parser.add_argument("--nickname", default="PaperS3", help="设备昵称，默认 PaperS3")
    parser.add_argument("--city", default="杭州", help="天气城市，默认 杭州")
    parser.add_argument(
        "--modes",
        default=",".join(DEFAULT_MODES),
        help=f"启用模式（逗号分隔），默认 {','.join(DEFAULT_MODES)}",
    )
    parser.add_argument(
        "--strategy",
        default="random",
        choices=["random", "cycle", "time_slot", "smart"],
        help="刷新策略，默认 random",
    )
    parser.add_argument("--refresh-interval", type=int, default=60, help="刷新间隔（分钟），默认 60")
    parser.add_argument(
        "--memo-title", default=DEFAULT_MEMO_TITLE, help="MEMO 模式标题（可留空）"
    )
    parser.add_argument(
        "--memo-text", default=DEFAULT_MEMO_TEXT, help="MEMO 模式正文，用 \\n 表示换行"
    )
    parser.add_argument(
        "--always-active",
        action="store_true",
        help="配置 always_active=true（设备保持常亮轮询，较耗电，默认关闭）",
    )
    parser.add_argument(
        "--no-bind",
        action="store_true",
        help="不创建本地账号/不绑定设备；改为输出配对码，走 WebApp 配对流程",
    )
    parser.add_argument(
        "--username", default="local", help="本地账号用户名（--no-bind 时忽略），默认 local"
    )
    parser.add_argument(
        "--password",
        default=None,
        help="本地账号密码（--no-bind 时忽略）；不填则自动生成并打印",
    )
    args = parser.parse_args(argv)

    mac = args.mac.strip().upper()
    if not MAC_RE.match(mac):
        print(f"✗ MAC 格式不合法：{args.mac!r}，应为 AA:BB:CC:DD:EE:FF", file=sys.stderr)
        return 2

    modes = [m.strip().upper() for m in args.modes.split(",") if m.strip()]
    if not modes:
        print("✗ --modes 不能为空", file=sys.stderr)
        return 2

    lan_ip = _detect_lan_ip()
    api_base = args.api_base.rstrip("/")
    server_url = (args.server_url or f"http://{lan_ip}:8080").rstrip("/")
    web_url = (args.web_url or f"http://{lan_ip}:3000").rstrip("/")
    password = args.password or _random_password()

    print("=" * 72)
    print("InkSight · PaperS3 设备预置")
    print("=" * 72)
    print(f"设备 MAC      : {mac}")
    print(f"本机局域网 IP : {lan_ip}")
    print(f"后端(脚本用)  : {api_base}")
    print(f"设备后端地址  : {server_url}")
    print(f"WebApp 地址   : {web_url}")
    print()

    # 0) 健康检查
    status, health = _http_json("GET", f"{api_base}/api/health")
    if status != 200:
        print(f"✗ 后端不可用（GET /api/health -> {status}）：{health}", file=sys.stderr)
        print("  请先启动后端，例如：", file=sys.stderr)
        print(
            f"  cd {REPO_ROOT}/backend && .venv/bin/python -m uvicorn api.index:app --host 0.0.0.0 --port 8080",
            file=sys.stderr,
        )
        return 1
    print(f"[1/4] 后端健康检查通过 ({api_base})")

    # 1) 设备 token（与固件相同的免登录流程）
    status, token_payload = _http_json("POST", f"{api_base}/api/device/{mac}/token")
    if status != 200 or not isinstance(token_payload, dict) or not token_payload.get("token"):
        print(f"✗ 获取 device token 失败：HTTP {status} {token_payload}", file=sys.stderr)
        return 1
    device_token = str(token_payload["token"])
    print(f"[2/4] 已获取 device token（{'新建' if token_payload.get('new') else '复用现有'}）")

    # 2) 写入配置
    memo_text = args.memo_text.replace("\\n", "\n")
    mode_overrides: dict[str, Any] = {}
    if "MEMO" in modes:
        mode_overrides["MEMO"] = {
            "memo_title_1": args.memo_title,
            "memo_text_1": memo_text,
        }
    config_body = {
        "mac": mac,
        "nickname": args.nickname,
        "modes": modes,
        "refreshStrategy": args.strategy,
        "refreshInterval": max(10, min(1440, args.refresh_interval)),
        "modeLanguage": "zh",
        "city": args.city,
        "timezone": TIMEZONE,
        "screenSize": SCREEN_SIZE,
        "memoText": memo_text,
        "modeOverrides": mode_overrides,
        "always_active": bool(args.always_active),
    }
    status, save_payload = _http_json(
        "POST",
        f"{api_base}/api/config",
        payload=config_body,
        headers={"X-Device-Token": device_token},
    )
    if status != 200:
        print(f"✗ 保存配置失败：HTTP {status} {save_payload}", file=sys.stderr)
        return 1
    print(
        f"[3/4] 配置已写入（config_id={save_payload.get('config_id')}，"
        f"{SCREEN_SIZE}，{len(modes)} 个模式：{','.join(modes)}）"
    )

    # 3) 校验配置是否真的生效
    status, cfg = _http_json(
        "GET", f"{api_base}/api/config/{mac}", headers={"X-Device-Token": device_token}
    )
    if status != 200:
        print(f"✗ 读取配置失败：HTTP {status} {cfg}", file=sys.stderr)
        return 1
    saved_modes = cfg.get("modes") or []
    print(f"[4/4] 配置校验通过：refresh_strategy={cfg.get('refresh_strategy')}，modes={','.join(saved_modes)}")

    # 4) 绑定 or 输出配对码
    bind_info: Optional[dict[str, Any]] = None
    pair_code: Optional[str] = None
    if args.no_bind:
        status, claim = _http_json(
            "POST",
            f"{api_base}/api/device/{mac}/claim-token",
            headers={"X-Device-Token": device_token},
        )
        if status == 200 and isinstance(claim, dict):
            pair_code = claim.get("pair_code") or None
        if not pair_code:
            print(f"⚠ 生成配对码失败（HTTP {status}），设备首次渲染时会自动生成并显示配对码", file=sys.stderr)
    else:
        try:
            bind_info = asyncio.run(
                _bind_device_to_local_user(mac, args.username, password, args.nickname)
            )
        except Exception as exc:  # noqa: BLE001 - 绑定失败不阻塞配置写入
            print(f"⚠ 本地账号绑定失败：{exc}", file=sys.stderr)
            print("  仍可通过 WebApp 配对流程绑定设备（见下方说明）", file=sys.stderr)

    # ── 汇总 ──
    print()
    print("=" * 72)
    print("完成 ✅  接下来只差把设备连上网：")
    print("=" * 72)
    print(f"1) 设备配网：设备首次启动会开热点 `InkSight-XXXXX`（后 5 位是 MAC 尾号）。")
    print(f"   手机/电脑连上该热点 → 打开 http://192.168.4.1 → 填 WiFi 与后端地址：")
    print(f"     后端地址 = {server_url}")
    print(f"   （如果设备已经配过网，可在配网页修改后端地址；地址不要带结尾 `/`）")
    print(f"2) 设备会自己 POST /api/device/{mac}/token 拿 token，然后开始拉图。")
    if bind_info:
        print(f"3) 设备已绑定到本地账号：{bind_info['username']}（status={bind_info['status']}, role={bind_info['role']}）")
        if bind_info.get("password"):
            print(f"   初始密码：{bind_info['password']}   ← 请立即保存，登录 WebApp 后可自行修改")
        print(f"   现在设备应能直接显示内容；WebApp： {web_url}/config?mac={mac}")
    else:
        print("3) 设备未绑定账号：第一次渲染会显示「配对码」，请在 WebApp 完成绑定：")
        if pair_code:
            print(f"   配对码（刚生成）：{pair_code}（10 分钟内有效；也可直接看设备屏幕）")
        print(f"   打开 {web_url}/config → 注册/登录 → 输入配对码/或访问 {web_url}/claim?code=<配对码>")
        print("   绑定成功后设备会自动切换到正常内容画面（可能需要等一个刷新周期，或长按设备按键刷新）。")
    print()
    print("提示：想换成真实设备 MAC 时，用同样的命令再跑一次即可（脚本幂等）。")
    print("     查看/修改配置：WebApp 的 /config 页；API 文档：docs/deploy-local.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
