# InkSight 本地部署指南（macOS + M5Stack PaperDIY 960x540）

本文记录在本机（macOS）实际跑通的一套本地部署：**FastAPI 后端 + Next.js WebApp + PaperDIY 墨水屏**
（`firmware/` 同时也支持 PaperS3，两者同为 4.7" 960×540，差异见 `firmware/FLASH_M5PAPERDIY.md`）。
所有命令都在仓库根目录 `/Users/chen/Documents/deepseek-harness/default-workspace/inksight` 下执行（下称「仓库根目录」）。

> 目标设备：**M5Stack PaperDIY（K159-B），960x540 横屏，1-bit 黑白**；
> 真机 MAC `B8:1F:3F:B8:54:2C`，已绑定本地账号 `chen`（初始密码见 `docs/paperdiy-quickstart.md`）。
> **端口提醒**：WebApp 是 `:3000`，设备配网页里填的“服务器地址”是后端 `:8080`。
> 后端按固件请求的 `w=960&h=540` 出 **BMP（1bpp）**；WebApp/调试预览出 **PNG**。

---

## 0. 当前状态一览（本次已启动）

| 服务 | 地址 | 状态 | 日志 |
|------|------|------|------|
| 后端 FastAPI | `http://127.0.0.1:8080`（局域网 `http://192.168.3.6:8080`） | ✅ 运行中 | `backend/logs/backend.log` |
| WebApp Next.js | `http://127.0.0.1:3000`（局域网 `http://192.168.3.6:3000`） | ✅ 运行中 | `webapp/logs/webapp.log` |
| 浏览器刷机固件（同源） | `http://192.168.3.6:3000/firmware/inksight-paperdiy-s3.bin` | ✅ 可下载（1,965,360 B） | `webapp/public/firmware/` |

- 本机局域网 IP（本次）：**192.168.3.6** —— 设备要填的后端地址就是 **`http://192.168.3.6:8080`**。
- Mac 的 IP 可能变化（DHCP），换网络后请重新确认（见 §2）。
- 数据文件：`backend/inksight.db`（设备配置/用户/状态）、`backend/cache.db`（渲染缓存）。
- 本次部署**未配置任何真实 LLM Key**；需要 LLM 的模式会走降级文案或提示配置 Key（见 §5）。
- 一键管理脚本：`backend/scripts/local-servers.sh {start|stop|restart|rebuild|status|logs}`（见 §3）。
- PID 文件：`backend/logs/backend.pid`、`webapp/logs/webapp.pid`。

---

## 1. 目录与依赖

```
inksight/
├── backend/                 # FastAPI 后端
│   ├── .venv/               # Python 3.11 虚拟环境（已安装 requirements）
│   ├── .env                 # 已从 .env.example 生成（见 §5）
│   ├── fonts/               # 字体（仓库内已带，无需再下载）
│   ├── logs/backend.log     # 后端日志
│   └── scripts/             # setup_fonts.py / seed-papers3-device.py 等
├── webapp/                  # Next.js 16 WebApp
│   ├── .env                 # INKSIGHT_BACKEND_API_BASE=http://127.0.0.1:8080
│   └── logs/webapp.log      # WebApp 日志
├── scripts/
│   └── seed-papers3-device.py   # 兼容入口（真正实现在 backend/scripts/，见 §4）
└── docs/deploy-local.md     # 本文
```

环境要求：

- Python **3.11**（`backend/.venv` 已就绪）
- Node.js **20+**（本机 24，`webapp/node_modules` 已安装）
- 不需要 Docker

---

## 2. 查本机局域网 IP

```bash
ipconfig getifaddr en0     # Wi-Fi（多数情况）
ipconfig getifaddr en1     # 有线 / 第二块网卡
```

拿到形如 `192.168.3.6` 的地址后，设备侧和手机侧用的地址是：

- 后端：`http://192.168.3.6:8080`
- WebApp：`http://192.168.3.6:3000`

> 建议在路由器里给这台 Mac 做 **DHCP 保留（固定分配）**，否则换 Wi-Fi/重启后 IP 可能变化，
> 设备里的后端地址也要跟着改。地址**不要**带结尾 `/`。

### 2.1 DHCP 静态保留（防止设备后端地址失效）

这台 Mac 当前接 Wi-Fi 的网卡是 **en1**（`192.168.3.6`），网关是 `192.168.3.1`（华为路由器）。
先确认 MAC：

```bash
ipconfig getifaddr en1                       # 192.168.3.6
ifconfig en1 | grep ether                    # 本机当前: b6:1c:e4:0d:53:a5
```

⚠️ `b6:…` 这种 MAC 是 macOS 的**“私有 Wi-Fi 地址”**（随机 MAC）：在该网络里一般固定，
但如果开了“轮换/随机 MAC”，MAC 会变，DHCP 保留就会失效。建议：

- 系统设置 → Wi-Fi → 当前网络「详细信息」→ 把 **“私有 Wi-Fi 地址”设为“固定”**（或关闭轮换）；
- 或者干脆给 Mac 设**手动 IP**（192.168.3.6，子网掩码 255.255.255.0，网关 192.168.3.1）。

路由器里通常叫「DHCP 静态分配 / 地址保留 / IP 与 MAC 绑定 / 固定 IP」，路径示例：

- **华为（本机，`192.168.3.1`）**：登录路由器 → 更多功能 → 网络设置 → **设备管理 / DHCP** →
  找到这台 Mac → 「固定 IP / 绑定」→ 设为 `192.168.3.6`（或在「终端管理」里直接改）。
- **TP-LINK（`192.168.1.1`）**：DHCP 服务器 → **地址保留 / 静态地址分配** → 新增：
  MAC = `b6:1c:e4:0d:53:a5`，IP = `192.168.3.6`。
- **小米 / Redmi（`192.168.31.1`）**：高级设置 → **DHCP 静态 IP 绑定** → 添加 MAC 与 IP。
- 其它品牌：在「局域网 / LAN 设置」里找 **DHCP 地址保留 / IP-MAC 绑定**，填同一组 MAC+IP 即可。

改完后把设备断电重启一次（或长按 ButtonA 进配网改服务器地址），用
`backend/scripts/device-status.sh` 确认后端地址仍是 `http://192.168.3.6:8080`。

---

## 3. 启动 / 停止 / 重启（推荐用一键脚本）

两个服务用 `backend/scripts/local-servers.sh` 统一管理（nohup 后台运行 + PID 文件 + 健康检查）：

```bash
cd /Users/chen/Documents/deepseek-harness/default-workspace/inksight

backend/scripts/local-servers.sh start     # 启动后端 :8080 + WebApp :3000
backend/scripts/local-servers.sh stop      # 停止两个服务
backend/scripts/local-servers.sh restart   # 重启两个服务（改了后端代码/backend/.env 后）
backend/scripts/local-servers.sh rebuild   # 重新 build WebApp 再重启（改了 webapp/ 代码/.env 后）
backend/scripts/local-servers.sh status    # 查看端口/PID/健康检查/局域网地址
backend/scripts/local-servers.sh logs      # 同时 tail 两个日志（Ctrl-C 退出）
```

> **日常重启只需要一条命令**：`backend/scripts/local-servers.sh restart`
> （改了 `webapp/` 代码则用 `rebuild`；它内部就是 `npm run build` + restart。）

- PID 文件：`backend/logs/backend.pid`、`webapp/logs/webapp.pid`
- 日志：`backend/logs/backend.log`、`webapp/logs/webapp.log`
- 端口：后端 **8080**，WebApp **3000**

<details>
<summary>等价的裸命令（不想用脚本时）</summary>

```bash
# 后端：启动 / 停止
cd /Users/chen/Documents/deepseek-harness/default-workspace/inksight/backend
nohup .venv/bin/python -m uvicorn api.index:app --host 0.0.0.0 --port 8080 \
  >> logs/backend.log 2>&1 &
pkill -f "uvicorn api.index:app"

# WebApp：构建 / 启动 / 停止
cd /Users/chen/Documents/deepseek-harness/default-workspace/inksight/webapp
npm_config_cache=/Users/chen/Documents/deepseek-harness/default-workspace/.npm-cache npm run build
nohup ./node_modules/.bin/next start -p 3000 >> logs/webapp.log 2>&1 &
pkill -f "next start -p 3000"
```

注意：

- **改了 `backend/.env` 必须重启后端**（环境变量只在进程启动时读取）。
- **改了 `webapp/` 下代码或 `.env` 必须重新 `npm run build` 再重启**（`next start` 是生产模式，不热更新）。
- 首次启动或新增模式后，需要重启后端才会重新加载 `backend/core/modes/` 下的模式 JSON。
</details>

### 3.1 检查服务是否正常

```bash
cd /Users/chen/Documents/deepseek-harness/default-workspace/inksight
backend/scripts/local-servers.sh status

# 或手动检查：
curl -s -o /dev/null -w "backend health : %{http_code}\n" http://127.0.0.1:8080/api/health
curl -sL -o /dev/null -w "webapp  /config: %{http_code}\n" http://127.0.0.1:3000/config
curl -s -o /tmp/r.bmp  -w "render 960x540 : %{http_code} %{size_download} bytes\n" \
  "http://127.0.0.1:8080/api/render?persona=WEATHER&w=960&h=540"
file /tmp/r.bmp   # 期望：PC bitmap ... 960 x 540 x 1
lsof -nP -iTCP:8080 -sTCP:LISTEN   # 应看到 Python 监听 *:8080
lsof -nP -iTCP:3000 -sTCP:LISTEN   # 应看到 node 监听 *:3000
```

---

## 4. PaperDIY 设备接入（关键步骤）

整体流程：**刷机 → 配网（填后端地址）→ 后端自动发 device token → 出图**。
首次出图会显示「配对码 / 欢迎使用 InkSight」，到 WebApp 绑定后即显示内容。

### 4.1 找到设备的 MAC

任选一种：

1. 串口日志（115200）里会打印 MAC；
2. 设备第一次启动会开热点 `InkSight-XXXXX`（后 5 位是 MAC 尾号），连上后配网页 `http://192.168.4.1` 的 `/info` 里有；
3. 已经连过网、请求过后端的情况：

```bash
sqlite3 backend/inksight.db \
  "select mac, datetime(updated_at) from device_state order by updated_at desc limit 5;"
```

4. 或者看后端日志：`grep '/api/render' backend/logs/backend.log | tail`。

MAC 格式必须是 `AA:BB:CC:DD:EE:FF`（大写、冒号分隔）。

### 4.2 预置设备配置（推荐，脚本幂等）

```bash
cd /Users/chen/Documents/deepseek-harness/default-workspace/inksight

# 用真实 MAC 替换 AA:BB:CC:DD:EE:FF
backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF

# 常见变体：
#   只写配置、不创建本地账号（走 WebApp 配对码绑定流程）
backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF --no-bind
#   改城市/模式/刷新策略
backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF \
   --city 上海 --modes WEATHER,CALENDAR,DAILY,MEMO --strategy cycle --refresh-interval 30
#   手动指定后端地址（例如换 Wi-Fi 后 IP 变了）
backend/.venv/bin/python backend/scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF \
   --server-url http://192.168.3.6:8080

# 也可以 cd 到 backend 再运行：
#   cd backend && .venv/bin/python scripts/seed-papers3-device.py --mac AA:BB:CC:DD:EE:FF
# 仓库根目录的 scripts/seed-papers3-device.py 是兼容入口，会转发到 backend/scripts/ 下的实现
# （根目录 scripts/* 被 .gitignore 忽略，正式实现放在 backend/scripts/ 才会进 git）。
```

脚本会：

1. `POST /api/device/<MAC>/token`（与固件相同，无需登录）拿/复用 device token；
2. `POST /api/config` 写入配置（**960x540**、模式、刷新策略、城市、MEMO 初始内容等）；
3. **默认**（`--no-bind` 之外）直接在本地库创建一个账号并把设备绑定为该账号的 owner，
   并把**自动生成的密码打印出来**（请立刻保存；已有同名账号则不改密码）。
   同时给该账号初始化 50 次免费额度（与网页注册一致）。
   这样设备第一次请求就直接出内容，不用配对。
4. 打印设备要填的后端地址、WebApp 地址、下一步操作。

> 默认模式只含**不需要 LLM Key** 的：`WEATHER, CALENDAR, DAILY, MEMO`。
> 等配置好 `DEEPSEEK_API_KEY` 后，再到 WebApp 配置页勾选 `POETRY / ZEN / QUOTE` 等 LLM 模式。

### 4.3 设备配网（第一次刷机后）

1. 设备开机若没有 Wi-Fi 配置，会进入配网模式，开热点 **`InkSight-XXXXX`**；
2. 手机/电脑连这个热点，浏览器打开 **`http://192.168.4.1`**；
3. 选择家里的 Wi-Fi、输入密码，**后端地址填 `http://192.168.3.6:8080`**（或你当前 Mac 的 IP），保存；
4. 设备重启联网 → 后端自动 `POST /api/device/<MAC>/token` → 开始拉图。

若设备之前配过网、只是后端地址变了：重新进入配网页（设备上的按键操作见 `docs/button-controls.md`）改「服务器地址」即可。

### 4.4 绑定设备（两种方式，任选其一）

**A. 脚本绑定（`seed-papers3-device.py` 默认行为）**

脚本已创建账号并绑定，直接看它打印的用户名/密码，登录 WebApp 即可管理设备。
多台设备时可用 `--username` / `--password` 指定同一个账号。

**B. WebApp 配对码（不跑脚本也能绑定）**

1. 浏览器打开 `http://192.168.3.6:3000`（或本机 `http://127.0.0.1:3000`）；
2. 注册 / 登录（本地注册需要填邮箱，任意合法格式即可，**不需要**真实收信 / SMTP）；
3. 进入「设备配置」页 `/config`，在「配对码」输入框填入设备屏幕上显示的配对码并提交；
   也可以直接访问 `http://192.168.3.6:3000/claim?code=<配对码>`；
4. 绑定成功后跳转到 `/config?mac=<MAC>`，设备下一轮刷新就会出内容
   （设备在线时会立即收到刷新通知；不在线则等一个刷新周期或长按设备按键）。

> 配对码有效期 10 分钟；后端日志里也能看到，或调用
> `POST /api/device/<MAC>/claim-token`（带 device token）重新生成。

### 4.5 用户操作全流程（从零到设备出图）

1. **刷机**：用 Chrome/Edge 打开 `http://192.168.3.6:3000/flash`（见 §4.6），
   或按 §4.6 用 esptool 命令行刷 `firmware/dist/papers3/*.bin`；
2. **配网**：设备开机进热点 `InkSight-XXXXX` → 打开 `http://192.168.4.1` →
   填 Wi-Fi + 后端地址 `http://192.168.3.6:8080`；
3. **注册/登录**：浏览器打开 `http://192.168.3.6:3000` → 注册（用户名 2-30 字符、密码 ≥4 位、
   邮箱填任意合法格式即可，本地不校验收信）→ 登录；
4. **输入配对码**：设备第一次拉图会显示「配对码：XXXXXXXX」→ 在 `/config` 页的配对码输入框填入
   （或访问 `http://192.168.3.6:3000/claim?code=XXXXXXXX`）→ 提交；
5. **选 4.7" / 保存配置**：绑定成功后跳到 `/config?mac=<MAC>` →
   右上角屏幕尺寸选 **4.7"（960x540）** → 勾选模式（WEATHER / CALENDAR / DAILY / MEMO 等）→ 点「保存」；
6. **设备出图**：保存后设备在线会立即收到刷新通知（见 `X-Pending-Refresh`），
   下一轮刷新即显示真实内容（不再显示配对码）。也可在配置页点「立即刷新」或长按设备按键。

> 如果直接运行了 `seed-papers3-device.py`（默认会创建账号并绑定），则第 3~4 步可跳过：
> 用脚本打印的用户名/密码登录，直接到第 5 步。

### 4.6 刷机：浏览器 WebFlasher 与 esptool CLI

**已经放进 WebApp 静态目录的合并固件（同源，浏览器可直接下载）：**

- 文件：`webapp/public/firmware/inksight-paperdiy-s3.bin`
- 大小：**1,965,360 字节**（SHA-256 `5b77c356...716407`）
- 来源：`firmware/dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin`（offset 0，ESP32-S3）
- 浏览器访问：**`http://192.168.3.6:3000/firmware/inksight-paperdiy-s3.bin`**
  （本机：`http://127.0.0.1:3000/firmware/inksight-paperdiy-s3.bin`）

**方式 A：浏览器 WebFlasher（Chrome / Edge）**

1. 打开 `http://192.168.3.6:3000/flash`；
2. 选择「手动固件 URL」，粘贴：
   `http://192.168.3.6:3000/firmware/inksight-paperdiy-s3.bin`
   （页面会先通过后端 `/api/firmware/validate-url` 校验，再点「校验/验证」）；
3. 点「开始刷写」→ 选择串口（USB-C 数据线，ESP32-S3 的 USB 口）→ 写入（offset 0）；
4. 刷写完成后按 §4.5 配网、绑定。

> WebFlasher 的下载走同源代理 `/api/firmware/download?url=...`，
> 本次已放行「本机 / 局域网 .bin URL」（原先只允许 GitHub 域名）。

**方式 B（推荐，稳定）：esptool 命令行**

本机已装好 esptool（虚拟环境 `.tooling/venv`），在仓库根目录执行：

```bash
# 列出串口，确认设备是哪个（macOS 一般是 /dev/cu.usbmodem* 或 /dev/cu.wchusbserial*）
.tooling/venv/bin/python -m serial.tools.list_ports -v

# 刷合并固件（offset 0，芯片 ESP32-S3；按实际串口替换 /dev/cu.usbmodem1101）
.tooling/venv/bin/esptool.py --chip esp32s3 -p /dev/cu.usbmodem1101 -b 460800 \
  write_flash 0x0 firmware/dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin

# 校验（可选）
.tooling/venv/bin/esptool.py --chip esp32s3 -p /dev/cu.usbmodem1101 verify_flash 0x0 \
  firmware/dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin
```

> 刷完如果 30 秒内没反应，按一下设备复位键（或重新插拔 USB）。
> 固件烧录细节见 `firmware/FLASH_M5PAPERS3.md`。

### 4.7 WebApp 里预览 960x540

配置页 / 预览页右上角的屏幕尺寸选择器新增了 **4.7"（960x540）** 选项；
选中后预览按 960x540 请求后端（与设备实际渲染一致）。

> 注意：屏幕尺寸只影响 WebApp 的**预览**。设备真实分辨率由固件在 `/api/render?w=&h=` 里上报，
> 后端配置里不存分辨率，无需为不同屏幕改后端。

---

## 5. 之后补充 DEEPSEEK_API_KEY（启用 LLM 模式）

编辑 `backend/.env`，把这一行改成真实 Key（**文件里已用醒目注释标出位置**）：

```dotenv
# ★★★ TODO（用户填写）...
DEEPSEEK_API_KEY=            # ← 在这里填 sk-xxxx
```

改完**重启后端**：

```bash
pkill -f "uvicorn api.index:app"
cd /Users/chen/Documents/deepseek-harness/default-workspace/inksight/backend
nohup .venv/bin/python -m uvicorn api.index:app --host 0.0.0.0 --port 8080 \
  >> logs/backend.log 2>&1 &
```

然后在 WebApp 配置页给设备勾选需要的 LLM 模式（POETRY / ZEN / QUOTE / ROAST / BRIEFING 等）。

说明：

- 也可以不配服务器级 Key，而是登录 WebApp 后在「个人信息 / 模型配置」里填自己的 Key
  （用户级 Key 优先于服务器环境变量）。
- 未配置 Key 时：LLM 类模式不可用（设备会显示「API key 无效或已过期」提示图，WebApp 预览返回 400）；
  静态/外部数据模式（WEATHER / CALENDAR / DAILY / MEMO / TIMETABLE 等）**完全正常**。
- `ARTWALL` 用的是阿里图像生成，需要 `DASHSCOPE_API_KEY`；`ALMANAC` 的黄历数据需要 `TIANAPI_KEY`，
  没配时走降级文案。
- 天气默认用 Open-Meteo（免 Key），`DEFAULT_CITY=杭州`；和风天气 `QWEATHER_*` 是备用源，可不填。
- 本地部署已在 `backend/.env` 里设置 **`INKSIGHT_BILLING_ENABLED=0`**（关闭免费额度计费/拦截）。
  不关的话，没有额度记录的账号在 DAILY / CALENDAR 这类含 LLM 步骤的模式上会被拦成
  「当前设备 owner 免费额度已用完」。想恢复线上计费行为，删掉该行并重启后端即可。

---

## 6. 验证命令（复制即用）

```bash
# --- 后端 ---
curl -s -o /dev/null -w "health           : %{http_code}\n" http://127.0.0.1:8080/api/health

# 960x540 设备图（BMP，1bpp）：期望 200、64862 字节、BMP 头 62 字节 + 64800 像素数据
curl -s -o /tmp/papers3.bmp -w "render 960x540   : %{http_code} %{size_download} bytes\n" \
  "http://127.0.0.1:8080/api/render?persona=WEATHER&w=960&h=540"
file /tmp/papers3.bmp

# 960x540 PNG 预览：期望 200、PNG 960x540
curl -s -o /tmp/papers3.png -w "preview 960x540  : %{http_code}\n" \
  "http://127.0.0.1:8080/api/preview?persona=WEATHER&w=960&h=540"
file /tmp/papers3.png
open /tmp/papers3.png      # 用「预览」直接看效果

# 设备握手三步（把 MAC 换成真实值）
MAC=AA:BB:CC:DD:EE:FF
TOKEN=$(curl -s -X POST "http://127.0.0.1:8080/api/device/$MAC/token" | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
curl -s -o /tmp/pair.bmp -w "render(token)    : %{http_code}\n" \
  "http://127.0.0.1:8080/api/render?mac=$MAC&w=960&h=540" -H "X-Device-Token: $TOKEN"
curl -s -w " heartbeat        : %{http_code}\n" -X POST "http://127.0.0.1:8080/api/device/$MAC/heartbeat" \
  -H "Content-Type: application/json" -H "X-Device-Token: $TOKEN" -d '{"voltage":4.0,"rssi":-60}'

# --- WebApp ---
for p in / /config /preview /flash /login /claim; do
  curl -sL -o /dev/null -w "webapp $p -> %{http_code}\n" "http://127.0.0.1:3000$p"
done
curl -s -o /tmp/w.png -w "webapp proxy preview: %{http_code}\n" \
  "http://127.0.0.1:3000/api/preview?persona=WEATHER&w=960&h=540"

# --- 刷机固件（同源可下载）---
curl -s -o /dev/null -w "firmware static   : %{http_code} %{size_download} bytes\n" \
  "http://192.168.3.6:3000/firmware/inksight-paperdiy-s3.bin"     # 期望 200 + 1965360
curl -s -w "\nfirmware validate : %{http_code}\n" \
  "http://127.0.0.1:3000/api/firmware/validate-url?url=http%3A%2F%2F192.168.3.6%3A3000%2Ffirmware%2Finksight-paperdiy-s3.bin"
curl -s -o /dev/null -w "firmware proxy    : %{http_code} %{size_download} bytes\n" \
  "http://127.0.0.1:3000/api/firmware/download?url=http%3A%2F%2F192.168.3.6%3A3000%2Ffirmware%2Finksight-paperdiy-s3.bin"
```

预期：以上抛出的都是 `200`（WebApp 的 `/` 会 307 跳到 `/zh/...`，用 `-L` 跟随即可；
固件相关三条分别是 200 / 200 / 200，最后一个下载 1,965,360 字节）。

---

## 7. 常见问题

| 现象 | 排查 |
|------|------|
| 设备一直显示「欢迎使用 InkSight / 配对码」 | 设备还没绑定账号 → §4.4；确认后端日志里该 MAC 的 `/api/render` 返回 200 |
| 设备显示「API key 无效或已过期」 | 配置里有 LLM 模式但没配 Key → §5，或先在 WebApp 取消这些模式 |
| 设备显示「免费额度已用完」 | 本地部署在 `backend/.env` 里设置 `INKSIGHT_BILLING_ENABLED=0` 并重启后端（见 §5） |
| 设备连不上后端 | ① 手机能打开 `http://192.168.3.6:8080/api/health` 吗？② 设备填的地址是否带 `/` 或协议写错；③ macOS 防火墙是否拦了 Python（系统设置 → 网络 → 防火墙）；④ 是否同一 Wi-Fi（很多路由器开了「AP 隔离」会挡住设备访问 Mac） |
| Mac 重启后设备连不上 / 页面打不开 | 本机服务不会自动启动（macOS 对 `~/Documents` 有 TCC 隐私保护，launchd/登录项直接读取仓库会被拒绝；本次尝试后按用户要求放弃自启）。开机/登录后手动执行一次：`backend/scripts/local-servers.sh start` |
| WebApp 局域网打开 404 `Not Found` | 早期版本只允许固定 host；本仓库已放行 `localhost/127.0.0.1/192.168.*/10.*/172.16-31.*`。若用自定义域名，加环境变量 `INKSIGHT_ALLOWED_WEB_HOSTS=your.domain` 后重启 WebApp |
| WebApp 改了代码不生效 | 必须 `npm run build` 后重启 `next start`（生产模式不是热更新） |
| 端口被占用 | `lsof -nP -iTCP:8080` / `lsof -nP -iTCP:3000`，先停掉旧进程；同时记得改 `INKSIGHT_BACKEND_API_BASE` |
| 想重置设备/配置数据 | 停后端 → `rm backend/inksight.db backend/cache.db`（**会清空所有配置/账号**）→ 重启后端 |
| 词库/`VOCAB_REVIEW` 显示「暂无词卡」 | 上游词库仓库结构变了，`backend/scripts/import_kylebing_vocab.py` 旧的下载地址已 404（本次未改动）。其余模式不受影响 |
| 日志里很多 `[FONT] Failed to load bitmap font ... OSError: invalid pixel size` | **无害**。960x540 下正文/标题字号超过内置 PCF 点阵档位时会回退到矢量 TTF 渲染，1-bit 输出依然清晰（见 `backend/logs/verify/e2e-*.png`）。该 warning 每个字体只打一次 |
| 浏览器刷机页提示「Only GitHub URLs are allowed」 | 已修复（放行本机/局域网 `.bin`）。若仍报错，确认 WebApp 已 `rebuild` 到最新代码 |
| 固件 URL 校验失败 | 用 `curl -I http://192.168.3.6:3000/firmware/inksight-paperdiy-s3.bin` 确认 200；后端必须能访问该 URL（校验是后端发起的） |
| `npm` 报缓存权限错误 | 始终加 `npm_config_cache=/Users/chen/Documents/deepseek-harness/default-workspace/.npm-cache` |
| `pip` 报缓存不可写 | 加 `PIP_CACHE_DIR=/Users/chen/Documents/deepseek-harness/default-workspace/.pip-cache` |

---

## 8. 本次本地化改动清单（相对上游 main）

后端（`backend/`）：

1. `.env`：从 `.env.example` 生成；三个 LLM Key 留空并加了醒目 TODO 注释；
   开启 `INKSIGHT_ALLOWED_HOSTS=*`、`INKSIGHT_CORS_ALLOW_LAN=1`（设备走局域网 IP 访问必需）；
   设置 `INKSIGHT_BILLING_ENABLED=0`（本地自托管关闭额度计费/拦截）。
   `.env.example` 中也补充了 `INKSIGHT_BILLING_ENABLED` 的说明。
2. `api/shared.py`：设备**未绑定时的配对引导图**字号/间距/边距按 `screen_h/300` 缩放
   （960x540 上标题≈36px、配对码≈25px，之前在 4.7" 屏上小到看不清）；
   `API key 无效` 提示图同样按屏幕高度缩放。
3. `core/patterns/error.py`：`render_error` 错误页字体/图标/位置按屏幕高度缩放（400x300 上保持原样）。
4. `core/modes/builtin/memo.json`：新增 `960x540` 的 `layout_overrides`（加大左内边距），
   修复 MEMO 便签在大屏上「图标压住标题/正文」的问题。

WebApp（`webapp/`）：

5. `.env`：`INKSIGHT_BACKEND_API_BASE=http://127.0.0.1:8080`。
6. `components/ui/screen-size-select.tsx`：屏幕尺寸新增 **4.7"（960x540）** 选项（PaperDIY / PaperS3 通用）。
7. `proxy.ts`：放行私有网段 host（`192.168.*` / `10.*` / `172.16-31.*` 等），
   否则用 `http://192.168.3.6:3000` 打开 WebApp 会 404；`proxy.test.ts` 增加对应用例。

脚本 / 资源 / 文档：

8. `backend/scripts/seed-papers3-device.py`：4.7"（PaperDIY / PaperS3）设备预置脚本
   （token → 配置 → 可选本地账号绑定 + 50 次额度初始化 / 否则输出配对码）；
   根目录 `scripts/seed-papers3-device.py` 是兼容入口（根目录 `scripts/*` 被 .gitignore 忽略）。
9. `backend/scripts/local-servers.sh`：本地一键启动/停止/重启/构建/状态/日志脚本
   （nohup + PID 文件 + 健康检查）。
10. `webapp/public/firmware/inksight-paperdiy-s3.bin`：从
    `firmware/dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin` 复制来的合并固件
    （1,965,360 B，offset 0），供 WebFlasher 同源下载；该目录已加进 `webapp/.gitignore`。
11. `webapp/app/api/firmware/download/route.ts`：固件下载代理放行「本机/局域网 `.bin` URL」
    （原先只允许 GitHub），否则 WebFlasher 的手动 URL 模式无法刷本地固件。
12. `backend/logs/.gitignore`、`webapp/logs/.gitignore`、`webapp/.gitignore`：
    忽略运行日志 / PID / 验证截图 / 本地固件（保持 `git status` 干净）。
13. `docs/deploy-local.md`：本文。

### 验证与证据

- 后端 `pytest`：**354 passed**；WebApp `npm run lint` 0 error、`npm run build` 通过、
  `npx tsx --test proxy.test.ts` 5 passed。
- 端到端绑定测试（webapp 注册 → 登录 → 设备 token → 配对码 → claim → 960x540 配置 → 渲染）：
  证据与截图在 `backend/logs/verify/`（`e2e-evidence.txt`、`e2e-01-pairing.png`、
  `e2e-02-WEATHER.png`、`e2e-02-CALENDAR.png`、`e2e-02-MEMO.png`、`e2e-contact-sheet.png`）。
  该目录被 `backend/logs/.gitignore` 忽略；测试账号/设备行已在测试后清理，用户 DB 是干净的。

> 未改动 `firmware/` 与 `inksight-mobile/`。后端测试：`354 passed`；WebApp：`lint` 0 error、`next build` 通过。
