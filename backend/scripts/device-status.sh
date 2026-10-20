#!/usr/bin/env bash
# InkSight 设备/服务状态速查（本地自托管用）
#
#   backend/scripts/device-status.sh            # 默认查 PaperDIY 设备
#   backend/scripts/device-status.sh AA:BB:..  # 指定设备 MAC
#
# 输出：服务健康、局域网地址、设备最近一次渲染、配置里的模式/刷新间隔、最近 5 次渲染记录。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"

MAC="${1:-B8:1F:3F:B8:54:2C}"
MAC_UP="$(printf '%s' "$MAC" | tr '[:lower:]' '[:upper:]')"
PY="$BACKEND_DIR/.venv/bin/python"
BACKEND_URL="http://127.0.0.1:8080"
WEBAPP_URL="http://127.0.0.1:3000"

lan_ip() {
  local ip
  for iface in en0 en1 en2; do
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [ -n "$ip" ]; then printf '%s' "$ip"; return 0; fi
  done
  printf '127.0.0.1'
}

code() { curl -s -o /dev/null -m 3 -w '%{http_code}' "$1" 2>/dev/null || echo "---"; }

IP="$(lan_ip)"
echo "────────────────────────────────────────────────────────"
echo " InkSight 状态  $(date '+%Y-%m-%d %H:%M:%S')"
echo "────────────────────────────────────────────────────────"
echo " 后端    : $(code "$BACKEND_URL/api/health")  $BACKEND_URL  (LAN http://$IP:8080)"
echo " WebApp  : $(code "$WEBAPP_URL/zh")  $WEBAPP_URL  (LAN http://$IP:3000)"
echo " 设备后端地址（配网页填写）: http://$IP:8080"
echo "────────────────────────────────────────────────────────"

"$PY" - "$BACKEND_DIR" "$MAC_UP" <<'PYEOF'
import sqlite3
import sys
from pathlib import Path

backend_dir, mac = Path(sys.argv[1]), sys.argv[2]
db = sqlite3.connect(backend_dir / "inksight.db")

def one(sql, args=()):
    try:
        return db.execute(sql, args).fetchone()
    except Exception as exc:  # noqa: BLE001
        return (f"<{exc}>",)

tables = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
state = one(
    "select last_persona,last_refresh_at,last_state_poll_at,expected_refresh_min,runtime_mode "
    "from device_state where mac=?",
    (mac,),
) if "device_state" in tables else None

cfg = one(
    "select id,nickname,modes,refresh_strategy,refresh_interval,city,llm_provider,llm_model "
    "from configs where mac=? order by id desc limit 1",
    (mac,),
) if "configs" in tables else None

print(f" 设备 MAC : {mac}")
if cfg:
    cid, nickname, modes, strategy, interval, city, provider, model = cfg
    print(f" 配置     : #{cid} {nickname or ''}  city={city}  modes={modes}")
    print(f"            refresh_strategy={strategy}  refresh_interval={interval}min  llm={provider}/{model}")
else:
    print(" 配置     : (无)")

if state:
    persona, last_refresh, last_poll, expected, runtime = state
    print(f" 最近渲染 : {last_refresh or '-'}  persona={persona or '-'}")
    print(f" 设备轮询 : {last_poll or '-'}  runtime={runtime or '-'}  expected_refresh={expected or '-'}min")
else:
    print(" 设备状态 : (无记录)")

print(" 最近 5 次渲染：")
try:
    rows = list(
        db.execute(
            "select created_at,persona,cache_hit,status from render_logs where mac=? "
            "order by rowid desc limit 5",
            (mac,),
        )
    )
    if rows:
        for created_at, persona, cache_hit, status in rows:
            print(f"   {created_at}  {persona or '-':10s}  cache={cache_hit}  status={status}")
    else:
        print("   (无)")
except Exception:  # noqa: BLE001
    print("   (render_logs 不可用)")
PYEOF

echo "────────────────────────────────────────────────────────"
echo " 提示：设备深睡时不会请求后端；按 ButtonA 可唤醒，"
echo "       长按 ButtonA 约 2s 进入配网模式。日志：backend/logs/backend.log"
echo "────────────────────────────────────────────────────────"
