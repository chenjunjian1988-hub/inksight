#!/usr/bin/env bash
# 从上游 datascale-ai/inksight 同步更新到本 fork。
#
#   backend/scripts/sync-upstream.sh                    # 同步 main（快进 + 推送到 origin）
#   backend/scripts/sync-upstream.sh --rebase-feature   # 再把 feat/paperdiy rebase 到 main 并推送
#
# 约定：main 只跟随上游；定制在 feat/paperdiy（见 docs/fork-sync.md）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/datascale-ai/inksight.git}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
FEATURE_BRANCH="${FEATURE_BRANCH:-feat/paperdiy}"
REBASE_FEATURE=0
for arg in "$@"; do
  case "$arg" in
    --rebase-feature) REBASE_FEATURE=1 ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

echo "==> repo: $REPO_ROOT"
if ! git remote get-url upstream >/dev/null 2>&1; then
  echo "==> adding upstream remote: $UPSTREAM_URL"
  git remote add upstream "$UPSTREAM_URL"
fi

echo "==> fetching upstream/$MAIN_BRANCH ..."
git fetch upstream "$MAIN_BRANCH"

echo "==> syncing local $MAIN_BRANCH ..."
git switch "$MAIN_BRANCH"
git merge --ff-only "upstream/$MAIN_BRANCH"

echo "==> pushing $MAIN_BRANCH to origin ..."
git push origin "$MAIN_BRANCH"

echo "==> upstream base: $(git rev-parse --short upstream/"$MAIN_BRANCH")"

if [ -z "$(git branch --list "$FEATURE_BRANCH")" ]; then
  echo "==> 没有 $FEATURE_BRANCH 分支，跳过定制分支同步"
  exit 0
fi

git switch "$FEATURE_BRANCH"
if [ "$REBASE_FEATURE" = "1" ]; then
  echo "==> rebasing $FEATURE_BRANCH onto $MAIN_BRANCH ..."
  git rebase "$MAIN_BRANCH"
  echo "==> pushing $FEATURE_BRANCH to origin (force-with-lease) ..."
  git push --force-with-lease origin "$FEATURE_BRANCH"
else
  echo "==> $FEATURE_BRANCH 未变更；如需 rebase 到最新上游，执行："
  echo "    backend/scripts/sync-upstream.sh --rebase-feature"
fi

echo "✅ done ($(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD))"
