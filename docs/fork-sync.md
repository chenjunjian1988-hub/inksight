# Fork 同步与分支策略（InkSight）

本仓库是从 [`datascale-ai/inksight`](https://github.com/datascale-ai/inksight) fork 出来的
（`chenjunjian1988-hub/inksight`），并在此基础上加入了 **M5Stack PaperDIY 适配 + 本地部署** 的定制。

## 1. 当前分支约定

| 分支 | 作用 | 与上游关系 |
|------|------|-----------|
| `main` | **只跟随上游**，不直接提交定制代码 | 与 `upstream/main` 保持一致 |
| `feat/paperdiy` | 本仓库全部定制（PaperDIY 固件、960×540 优化、本地部署、文档） | 基于上游 `main`，含 8+ 个定制 commit |

```
origin   = git@github.com:chenjunjian1988-hub/inksight.git   （你的 fork）
upstream = https://github.com/datascale-ai/inksight.git      （原作者仓库）
```

日常开发/使用在 `feat/paperdiy` 分支；`main` 保持干净，方便随时 “Sync fork”。

## 2. 上游更新时怎么同步

### 方式 A：网页（最简单）
你的仓库页 → **Sync fork** → **Update branch**。这会把上游合并进 `main`（保留已有提交）。

### 方式 B：命令行（推荐，可控）

```bash
cd ~/Documents/deepseek-harness/default-workspace/inksight
# 一次性：添加上游远程（本机已加好）
git remote add upstream https://github.com/datascale-ai/inksight.git

# 1) 拉上游 main（本地 main 已跟踪 upstream/main，可快进）
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main

# 2) 把更新合进定制分支（二选一）
git switch feat/paperdiy
git merge main        # 保留历史，冲突时手动解决
# 或
git rebase main       # 历史更线性；冲突时解决后 git rebase --continue
git push origin feat/paperdiy
```

或直接用脚本（自动完成 1，可选自动 rebase 2）：

```bash
backend/scripts/sync-upstream.sh                  # 只同步 main
backend/scripts/sync-upstream.sh --rebase-feature # 同步 main + rebase 定制分支并推送
```

### 冲突高发文件（我们改过的）
- `firmware/platformio.ini`、`firmware/src/{config.h,epd_driver.cpp,main.cpp,network.cpp,ota.cpp,board_hooks.*}`
- `backend/core/config.py`、`backend/core/modes/builtin/memo.json`、`backend/api/shared.py`
- `webapp/proxy.ts`、`webapp/app/api/firmware/download/route.ts`、`webapp/components/ui/screen-size-select.tsx`
- `docs/`、`README*`

解决冲突后记得跑一遍验证：

```bash
cd backend && .venv/bin/python -m pytest -q
cd ../webapp && npm run lint && npm run build
cd ../firmware && pio run -e epd_47_m5paperdiy_s3
```

## 3. 本地部署怎么跟着更新

| 改动类型 | 生效方式 |
|---|---|
| 后端 Python / JSON 模式 / `.env` | `backend/scripts/local-servers.sh restart` |
| WebApp 前端 | `backend/scripts/local-servers.sh rebuild`（会 `npm run build` 再重启） |
| 固件 `firmware/` | 重新 `pio run -e epd_47_m5paperdiy_s3` + 刷机（USB，见 `firmware/FLASH_M5PAPERDIY.md`） |
| 上游新增/变更的默认配置 | 检查 `backend/.env.example` 与 `docs/deploy-local.md` 是否需要补 |

## 4. 要不要推给上游？

- **不需要**。`git push origin` 只影响你自己的 fork；上游不会自动收到。
- 想让原作者收录（比如 PaperDIY 适配、960×540 布局修复）→ 在 GitHub 上开 **Pull Request**
  （`chenjunjian1988-hub:feat/paperdiy` → `datascale-ai:main`），由上游维护者决定是否合并。
- 不开 PR 的话，定制只存在于你的 fork 和本地，完全够自用。

## 5. 常见问题

- **`main` 和上游不一致了？** 本仓库已把 `main` 重置为上游基线（`ea73138`），定制在
  `feat/paperdiy`。如果你在 `main` 上误提交了，cherry-pick 到 `feat/paperdiy` 后
  `git switch main && git reset --hard upstream/main`，再 `git push --force-with-lease origin main`。
- **同步时 rebase 冲突太多？** 改用 `git merge main`（保留历史）通常更省事。
- **仓库是浅克隆（shallow）？** 需要完整历史时执行 `git fetch --unshallow upstream`。
- **不要对上游仓库 force push**：你只有 fork 的写权限，上游需要走 PR。
