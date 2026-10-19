#!/usr/bin/env bash
# InkSight 本地部署一键管理脚本（后端 FastAPI :8080 + WebApp :3000）
#
# 用法：
#   backend/scripts/local-servers.sh start      # 启动两个服务（已在跑则跳过）
#   backend/scripts/local-servers.sh stop       # 停止两个服务
#   backend/scripts/local-servers.sh restart    # 重启两个服务（改了后端代码/.env 后用）
#   backend/scripts/local-servers.sh rebuild    # 重新 build WebApp 再重启（改了 webapp/ 代码或 .env 后用）
#   backend/scripts/local-servers.sh status     # 查看端口/健康检查/局域网地址
#   backend/scripts/local-servers.sh logs       # 同时 tail 两个日志（Ctrl-C 退出）
#
# PID 文件：
#   backend/logs/backend.pid
#   webapp/logs/webapp.pid
# 日志：
#   backend/logs/backend.log
#   webapp/logs/webapp.log

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"
WEBAPP_DIR="$REPO_ROOT/webapp"

BACKEND_PORT=8080
WEBAPP_PORT=3000

BACKEND_LOG="$BACKEND_DIR/logs/backend.log"
WEBAPP_LOG="$WEBAPP_DIR/logs/webapp.log"
BACKEND_PID_FILE="$BACKEND_DIR/logs/backend.pid"
WEBAPP_PID_FILE="$WEBAPP_DIR/logs/webapp.pid"
NPM_CACHE="${NPM_CACHE:-$REPO_ROOT/../.npm-cache}"

BACKEND_HEALTH="http://127.0.0.1:${BACKEND_PORT}/api/health"

log()  { printf '%s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }

lan_ip() {
  local ip
  for iface in en0 en1 en2; do
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [ -n "$ip" ]; then printf '%s' "$ip"; return 0; fi
  done
  printf '127.0.0.1'
}

port_pid() {  # $1=port → 监听该端口的 PID（可能为空）
  lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1 || true
}

http_code() {  # $1=url
  curl -s -o /dev/null -m 2 -w '%{http_code}' "$1" 2>/dev/null || true
}

wait_for() {  # $1=url $2=expect_code $3=秒数
  local url="$1" expect="$2" secs="${3:-60}" i code
  for ((i = 0; i < secs * 2; i++)); do
    code="$(http_code "$url")"
    [ "$code" = "$expect" ] && return 0
    sleep 0.5
  done
  return 1
}

start_backend() {
  local pid
  pid="$(port_pid "$BACKEND_PORT")"
  if [ -n "$pid" ]; then
    log "后端已在运行（pid=$pid, :${BACKEND_PORT}），跳过启动。"
    return 0
  fi
  if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
    warn "找不到 $BACKEND_DIR/.venv/bin/python，请先创建虚拟环境并安装 requirements。"
    return 1
  fi
  mkdir -p "$BACKEND_DIR/logs"
  log "启动后端 :$BACKEND_PORT ..."
  (
    cd "$BACKEND_DIR" || exit 1
    nohup .venv/bin/python -m uvicorn api.index:app --host 0.0.0.0 --port "$BACKEND_PORT" \
      >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )
  if wait_for "$BACKEND_HEALTH" 200 60; then
    log "✅ 后端就绪：http://127.0.0.1:${BACKEND_PORT}  (log: $BACKEND_LOG)"
    return 0
  fi
  warn "后端 60s 内未就绪，请查看日志：$BACKEND_LOG"
  return 1
}

start_webapp() {
  local pid
  pid="$(port_pid "$WEBAPP_PORT")"
  if [ -n "$pid" ]; then
    log "WebApp 已在运行（pid=$pid, :${WEBAPP_PORT}），跳过启动。"
    return 0
  fi
  if [ ! -d "$WEBAPP_DIR/.next" ]; then
    warn "webapp/.next 不存在，请先构建：$0 rebuild（或 cd webapp && npm run build）"
    return 1
  fi
  mkdir -p "$WEBAPP_DIR/logs"
  log "启动 WebApp :$WEBAPP_PORT ..."
  (
    cd "$WEBAPP_DIR" || exit 1
    nohup ./node_modules/.bin/next start -p "$WEBAPP_PORT" >> "$WEBAPP_LOG" 2>&1 &
    echo $! > "$WEBAPP_PID_FILE"
  )
  if wait_for "http://127.0.0.1:${WEBAPP_PORT}/" 307 60 \
     || wait_for "http://127.0.0.1:${WEBAPP_PORT}/" 200 5; then
    log "✅ WebApp 就绪：http://127.0.0.1:${WEBAPP_PORT}  (log: $WEBAPP_LOG)"
    return 0
  fi
  warn "WebApp 60s 内未就绪，请查看日志：$WEBAPP_LOG"
  return 1
}

stop_port() {  # $1=port $2=name $3=pid_file
  local port="$1" name="$2" pid_file="$3" pid
  pid="$(port_pid "$port")"
  if [ -z "$pid" ]; then
    log "${name} 未在运行（:${port}）。"
    rm -f "$pid_file"
    return 0
  fi
  log "停止 ${name}（pid=${pid}, :${port}）..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    [ -z "$(port_pid "$port")" ] && break
    sleep 0.5
  done
  if [ -n "$(port_pid "$port")" ]; then
    warn "$name 未在 10s 内退出，发送 SIGKILL。"
    kill -9 "$(port_pid "$port")" 2>/dev/null || true
    sleep 0.5
  fi
  rm -f "$pid_file"
  log "✅ $name 已停止。"
}

cmd_start() {
  local ok=0
  start_backend || ok=1
  start_webapp || ok=1
  show_status
  return $ok
}

cmd_stop() {
  stop_port "$WEBAPP_PORT" "WebApp" "$WEBAPP_PID_FILE"
  stop_port "$BACKEND_PORT" "后端" "$BACKEND_PID_FILE"
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

cmd_rebuild() {
  if [ ! -d "$WEBAPP_DIR/node_modules" ]; then
    warn "webapp/node_modules 不存在，请先 cd webapp && npm install --cache $NPM_CACHE"
    return 1
  fi
  log "构建 WebApp（npm run build，约 1~3 分钟）..."
  if (
    cd "$WEBAPP_DIR" || exit 1
    npm_config_cache="$NPM_CACHE" npm run build
  ); then
    log "✅ WebApp 构建完成。"
  else
    warn "WebApp 构建失败，服务保持原状。"
    return 1
  fi
  cmd_restart
}

show_status() {
  local ip backend_pid webapp_pid
  ip="$(lan_ip)"
  backend_pid="$(port_pid "$BACKEND_PORT")"
  webapp_pid="$(port_pid "$WEBAPP_PORT")"
  log "────────────────────────────────────────────────────────"
  if [ -n "$backend_pid" ]; then
    log "后端    : 运行中 pid=$backend_pid  http://127.0.0.1:${BACKEND_PORT}  http://${ip}:${BACKEND_PORT}"
    log "          /api/health -> $(http_code "$BACKEND_HEALTH")   log: $BACKEND_LOG"
  else
    log "后端    : 未运行（:${BACKEND_PORT}）"
  fi
  if [ -n "$webapp_pid" ]; then
    log "WebApp  : 运行中 pid=$webapp_pid  http://127.0.0.1:${WEBAPP_PORT}  http://${ip}:${WEBAPP_PORT}"
    log "          / -> $(http_code "http://127.0.0.1:${WEBAPP_PORT}/")（307 跳到 /zh 属正常）  log: $WEBAPP_LOG"
  else
    log "WebApp  : 未运行（:${WEBAPP_PORT}）"
  fi
  log "设备后端地址（PaperS3 配网页填写）: http://${ip}:${BACKEND_PORT}"
  log "WebApp 地址: http://${ip}:${WEBAPP_PORT}"
  log "────────────────────────────────────────────────────────"
}

cmd_logs() {
  mkdir -p "$BACKEND_DIR/logs" "$WEBAPP_DIR/logs"
  touch "$BACKEND_LOG" "$WEBAPP_LOG"
  tail -n 40 -f "$BACKEND_LOG" "$WEBAPP_LOG"
}

case "${1:-status}" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  rebuild) cmd_rebuild ;;
  status)  show_status ;;
  logs)    cmd_logs ;;
  *)
    warn "未知命令：$1"
    log "用法：$0 {start|stop|restart|rebuild|status|logs}"
    exit 2
    ;;
esac
