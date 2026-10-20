# ⚠️ 注意：你手上的真机是 **PaperDIY**，请优先看 [`paperdiy-quickstart.md`](paperdiy-quickstart.md)。
# 本文是 PaperS3（C139）版本，保留给 PaperS3 用户参考（固件仍支持该板）。

# InkSight × M5Stack PaperS3 快速上手（本机已部署）

> 目标硬件：**M5Stack PaperS3（SKU C139，ESP32-S3，4.7" 960×540 墨水屏）**
> 本机：macOS，仓库 `~/Documents/deepseek-harness/default-workspace/inksight`（下称「仓库根目录」）
>
> 这份文档是「拿到机器后照着做就能用」的快速上手；细节部署见
> [`docs/deploy-local.md`](deploy-local.md)，固件细节见
> [`firmware/FLASH_M5PAPERS3.md`](../firmware/FLASH_M5PAPERS3.md)。

---

## 0. 现在的状态

| 项目 | 状态 |
|------|------|
| 后端 FastAPI | ✅ 运行中 `http://127.0.0.1:8080`（局域网 `http://192.168.3.6:8080`） |
| WebApp Next.js | ✅ 运行中 `http://127.0.0.1:3000`（局域网 `http://192.168.3.6:3000`） |
| PaperS3 固件 | ✅ 已编译、字节级校验通过，**尚未上真机验证**（当前电脑没有接设备） |
| 固件下载（WebFlasher 用） | `http://192.168.3.6:3000/firmware/inksight-papers3-s3.bin`（1,969,168 B） |
| 数据 | `backend/inksight.db`（设备/账号/配置）、`backend/cache.db`（渲染缓存），当前为空库（干净状态） |
| LLM Key | ❌ 未配置（天气/日历/备忘/清单等无需 Key；AI 类模式会提示或走降级文案） |

本机局域网 IP 是 **192.168.3.6**。设备要是同一个 Wi-Fi 下的设备，填的后端地址就是
`http://192.168.3.6:8080`。**Mac 的 IP 由路由器 DHCP 分配，重启/换网后可能变化**（见 §5）。

服务管理（一个命令搞定）：

```bash
cd ~/Documents/deepseek-harness/default-workspace/inksight
backend/scripts/local-servers.sh status     # 看端口/健康检查/当前局域网地址
backend/scripts/local-servers.sh restart    # 改后端代码或 .env 后重启
backend/scripts/local-servers.sh rebuild    # 改 webapp 代码后重新 build 再重启
backend/scripts/local-servers.sh stop|start
backend/scripts/local-servers.sh logs       # 同时 tail 两个日志
```

日志：`backend/logs/backend.log`、`webapp/logs/webapp.log`。

---

## 1. 刷固件（第一次，约 3 分钟）

准备：**USB-C 数据线**（必须能传数据，不能是纯充电线）。PaperS3 的 USB-C 接的是 ESP32-S3
原生 USB Serial/JTAG，macOS 上会枚举成 `/dev/cu.usbmodem*`。

### 方式 A（推荐）：命令行 esptool

本仓库已自带一个隔离的 esptool 环境（`.tooling/venv`，esptool 5.6.0），不用动系统 Python：

```bash
cd ~/Documents/deepseek-harness/default-workspace/inksight/firmware

# 1) 插上 USB-C，按下侧键开机，确认端口出现（应看到 /dev/cu.usbmodemXXXX）
ls /dev/cu.usbmodem*

# 2) 刷入合并镜像（含 bootloader + 分区表 + 应用，写 0x0）
../.tooling/venv/bin/esptool --chip esp32s3 \
  --port /dev/cu.usbmodemXXXX --baud 921600 \
  write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
  0x0 dist/papers3/inksight-firmware-papers3_s3-0.1.0-papers3.bin
```

也可以直接用仓库里的封装脚本（自动找端口/镜像，兼容 esptool v4/v5）：

```bash
cd ~/Documents/deepseek-harness/default-workspace/inksight/firmware
ESPTOOL=../.tooling/venv/bin/esptool ./scripts/flash_papers3.sh
```

### 方式 B：浏览器 WebFlasher（需 Chrome / Edge）

1. 打开 `http://192.168.3.6:3000/zh/flash`
2. 选择「手动 URL」，填入
   `http://192.168.3.6:3000/firmware/inksight-papers3-s3.bin`
3. 点「刷写固件」→ 弹出串口选择框 → 选 `/dev/cu.usbmodemXXXX`
4. 等待完成，设备自动重启

> 也可以插到 Mac 上后用 `pio run -e epd_47_m5papers3_s3 -t upload` 刷（PlatformIO 环境已装好，
> 见 FLASH 文档）。

### 刷不进去时

- 关闭串口监视器 / Arduino IDE（端口独占）。
- 进下载模式：长按侧键约 2 秒关机，按住侧键重新插 USB（或开机后立刻长按），
  背面右下角红灯闪烁即进入下载模式，再执行上面的命令。
- 确认端口：`ls /dev/cu.usbmodem*`；`esptool --chip esp32s3 --port ... chip-id` 能应答即可。
- 彻底清空（会连 WiFi 配置一起清掉，下次开机自动进配网模式）：
  `../.tooling/venv/bin/esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX erase-flash`
  然后重新刷合并镜像。

---

## 2. 配网 + 绑定（第一次开机）

1. 刷完自动重启；**没有 WiFi 配置 → 自动进入配网模式**，屏幕画出「SETUP WIFI」大字
   （960×540 满屏刷新需要几秒，属正常）。
2. 手机/电脑连它的热点：`InkSight-XXXXX`（后 5 位是 MAC）。
3. 浏览器打开 **http://192.168.4.1**（手机可能提示「登录网络」，选继续）。
4. 填：
   - 你家 WiFi 的 SSID + 密码；
   - **服务器地址**：`http://192.168.3.6:8080`（一定要带 `:8080`，IP 换成 Mac 当前局域网 IP）；
   - 城市、偏好。
5. 保存 → 设备连 WiFi、访问后端 → 屏幕显示 **配对码**（如 `7LQ5EWX6`）。
6. 电脑打开 WebApp `http://192.168.3.6:3000`（或 `http://127.0.0.1:3000`）：
   - 注册 / 登录（本地账号，邮箱必填、密码 ≥ 4 位）；
   - 进「设备配置」→ 输入屏幕上的配对码 → 绑定；
   - 屏幕尺寸选 **4.7"（960×540）**；
   - 勾选想显示的模式（推荐先选 `WEATHER`、`CALENDAR`、`MEMO` 这类不依赖 LLM 的）；
   - 保存。
7. 设备下一次刷新（默认间隔可在配置页改）就会拉取并显示内容。

> 也可以不做 Web 绑定，用脚本直接给设备预置配置（适合已知 MAC 的情况）：
> `backend/scripts/seed-papers3-device.py --help`，详见 `docs/deploy-local.md` §4.2。

---

## 3. 加 DeepSeek Key（启用 AI 类模式）

二选一（推荐第一种，改完重启）：

```bash
cd ~/Documents/deepseek-harness/default-workspace/inksight
# 编辑 backend/.env，把这一行填成真实 Key：
#   DEEPSEEK_API_KEY=sk-xxxxxxxx
backend/scripts/local-servers.sh restart
```

或者在 WebApp 的「个人信息」页里填自己的模型 / API Key（按账号生效）。

> 没有 Key 时：`WEATHER / CALENDAR / MEMO / COUNTDOWN / HABIT` 等仍正常；
> 纯 LLM 模式（`QUOTE / POETRY / ZEN / ARTWALL / AI_CHAT` 等）会显示「API key 无效或已过期」
> 提示图或走 fallback 文案，属预期行为。

---

## 4. 已经验证过的（可复现）

- 960×540 契约：`/api/render` 返回 1-bit BMP 960×540（64862 B = 62 头 + 64800 像素），
  `/api/preview` 返回 960×540 PNG；`w=960&h=540` 全程可用。
- **端到端绑定流程**（注册 → 登录 → 设备 token → 配对码 → 绑定 → 保存 960×540 配置 →
  设备拉取到真实内容 WEATHER/CALENDAR/MEMO，而非配对图）。证据图：
  `backend/logs/verify/e2e-contact-sheet.png` 等。
- 后端测试：`backend/.venv/bin/python -m pytest -q` → **354 passed**。
- WebApp：`npm run lint` 0 error、`npm run build` 成功、`proxy.test.ts` 5/5。
- 固件镜像：esptool 校验通过（ESP32-S3、16MB、80MHz、DIO、checksum/hash valid，
  分区表匹配 `firmware/partitions/inksight_16mb_ota.csv`）。
- 浏览器刷机链路：同源固件 URL 200、sha256 与构建产物一致、下载代理 200。
- 其它板子回归：`pio run -e epd_42_wsv2_ssd1683_c3_promini` 仍然编译通过。

## 5. 换 IP / 重新配网

- 建议在路由器里给这台 Mac 做 **DHCP 静态保留**（绑定 MAC），避免 IP 变化。
- 如果 IP 变了：设备连续 3 个刷新周期连不上后端后，会自动打开 `InkSight-XXXXX` 热点（3 分钟），
  连上去在 http://192.168.4.1 把服务器地址改成新 IP 即可（不用 USB）。
- WiFi 密码改了 / 连不上：设备连不上所有已存 WiFi 时也会自动进配网模式。
- 想强制清空配置（保留固件）：擦 NVS 分区
  `../.tooling/venv/bin/esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX erase-region 0x9000 0x4000`
  （esptool v4 用 `erase_region`）。

## 6. 还没验证的部分（没有真机）——第一次上机请留意

| 项 | 可能现象 | 一句话修复 |
|----|----------|------------|
| 面板初始化 / 灰度波形 | 白屏、花屏、刷新很慢 | 看串口日志 `[EPD] PaperS3 init: board=... display=960x540 psram=...`；先确认能打印 |
| 屏幕方向 | 画面转 90° | `epd_driver.cpp` 里 `M5.Display.setRotation(1)` 改成 `0` 重新编译 |
| 黑白反色 | 字白底黑 / 整体反相 | `papers3Push1bpp()` 里 `TFT_WHITE, TFT_BLACK` 两个参数对调 |
| 深度睡眠 / 唤醒 | 睡下去不醒 / 耗电大 | 用 USB 供电先验证，串口看 `[SLEEP] PaperS3: ...`；唤醒依赖 BM8563 闹钟 + PMS150G |
| 电池电压 | 显示不准 | `M5.Power.getBatteryVoltage()`（GPIO3 分压比 2.0），下一步校准 |
| 配网 / WiFi | 热点不出来 | 长按侧键关机重开；或 `erase-region` 清 NVS 后重来 |
| 触摸 | 无（本版未使用） | PaperS3 的 GT911 已初始化但未接功能；交互靠 Web 配置页 |

其它已知现象：

- 后端日志里 `[FONT] Failed to load bitmap font ... invalid pixel size` 是**无害告警**
  （960×540 下请求字号超过点阵字体的档位，自动回退到矢量字体，1-bit 边缘依然清晰）。
- 词库导入脚本（`import_kylebing_vocab.py`）依赖的上游 raw URL 已 404（上游仓库改了布局），
  与本次部署无关；VOCAB 复习会显示空词表。
- **PaperS3 的 OTA 已在固件里禁用**：官方发布的是 4.2" 400×300 固件，刷进去驱动不了这块屏。
  升级只能 USB 重新刷机。
- WebApp 只允许 localhost / 局域网私有 IP 访问（`webapp/proxy.ts` 白名单已加 192.168.x/10.x/172.16-31.x），
  方便手机在局域网里打开配置页。

---

## 7. 本次改动 / 产物清单

**固件（`firmware/`）**

- 新增 PlatformIO 环境 `epd_47_m5papers3_s3`（espressif32@8.0.0 / arduino-esp32 3.3.12，
  OPI PSRAM、16MB 分区、M5GFX 0.2.33 + M5Unified 0.2.26）。
- `src/epd_driver.cpp`：PaperS3 分支，M5GFX `Panel_EPD` 并行总线驱动，1-bit → 16 灰波形；
  无局刷；深度睡眠走 `M5.Power.timerSleep()`（BM8563 闹钟 + PMS150G）。
- `src/board_hooks.{h,cpp}`：板级电源/电池钩子（其他板子为空实现，行为不变）。
- `src/config.h`：`BOARD_PROFILE_M5PAPERS3` + `PIN_CFG_BTN=-1` + `configButtonDown()` 统一判键。
- `src/main.cpp`：无按键板子的「连续 3 次连不上后端 → 自动开配网热点」恢复路径；
  无局刷屏不再每分钟全屏刷时钟。
- `src/network.h → src/inksight_network.h`：修 arduino-esp32 3.x 在 macOS 大小写不敏感文件系统上
  与框架 `Network.h` 冲突的编译问题。
- `src/ota.cpp`：PaperS3 禁用 OTA。
- 新文档/脚本：`FLASH_M5PAPERS3.md`、`scripts/{collect_papers3_artifacts.sh,flash_papers3.sh,check_papers3_artifacts.py}`。
- 构建产物（git 忽略）：`firmware/dist/papers3/`（合并镜像、bootloader/分区表/app、manifest.json）。

**后端（`backend/`）**

- 960×540 字号缩放：配对图（`api/shared.py`）、API Key 无效图、错误页（`core/patterns/error.py`）。
- MEMO 模式新增 `960x540` layout override，修图钉与正文重叠。
- `scripts/local-servers.sh`（服务管理）、`scripts/seed-papers3-device.py`（预置设备配置）。
- `.env.example` 增加 `INKSIGHT_BILLING_ENABLED=0` 说明（本地自用关闭额度拦截）。
- 本地 `.env`：Key 留空并有 TODO 标记；`INKSIGHT_BILLING_ENABLED=0`、`DEFAULT_CITY=杭州`。

**WebApp（`webapp/`）**

- 屏幕尺寸选项新增 **4.7"（960×540）**。
- `proxy.ts` 允许 localhost + 局域网私有 IP 访问（手机可打开配置页）。
- `app/api/firmware/download/route.ts` 允许同源/局域网 `.bin`（WebFlasher 本地刷机）。
- `public/firmware/inksight-papers3-s3.bin`（git 忽略，构建后拷贝）。

**文档**

- `docs/deploy-local.md`（部署/运维/排错，440 行）
- `firmware/FLASH_M5PAPERS3.md`（固件构建/刷机/分区/恢复）
- 本文
