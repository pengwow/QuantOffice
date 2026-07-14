#!/usr/bin/env bash
# =============================================================================
# QuantOffice 前端 Vite dev 启动 wrapper
# -----------------------------------------------------------------------------
# 解决: `bun run dev` 走 npm script → `bun x vite` → vite.js 第 7 行
#       `await import('source-map-support')` 被 Node 的 CJS loader 加载
#       报 "SyntaxError: Unexpected reserved word"。
#
# 根因: 老版 bun(< 1.1)的 `bun x` 会 fallback 到 Node 的 ESM loader,
#       Node 的 CJS bridge 不支持 top-level await。
#
# 修复: 强制 `bun --bun run dev`, --bun 标志让 bun runtime 跑整条调用链,
#       不会 fallback 到 Node loader。
#
# 同时做 bun 路径自动发现,避免不同安装方式(mise / 官方脚本 / 系统包)
# 路径不一致的麻烦。
# =============================================================================
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/QuantOffice}"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
LOG_PREFIX="[start-frontend-dev]"

# 1. 找 bun: PATH 优先,然后扫常见安装路径
BUN_BIN="$(command -v bun 2>/dev/null || true)"
if [[ -z "$BUN_BIN" || ! -x "$BUN_BIN" ]]; then
    for candidate in \
        "$HOME/.bun/bin/bun" \
        /root/.bun/bin/bun \
        /home/*/.bun/bin/bun \
        /opt/bun/bin/bun \
        /usr/local/bin/bun \
        /usr/bin/bun
    do
        if [[ -x "$candidate" ]]; then
            BUN_BIN="$candidate"
            break
        fi
    done
fi
if [[ -z "$BUN_BIN" || ! -x "$BUN_BIN" ]]; then
    echo "$LOG_PREFIX [FATAL] 找不到 bun,请先安装 bun https://bun.sh" >&2
    exit 127
fi
echo "$LOG_PREFIX 使用 bun: $BUN_BIN ($($BUN_BIN --version 2>/dev/null || echo '?') )"

# 2. 校验 frontend
if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "$LOG_PREFIX [FATAL] 找不到 $FRONTEND_DIR" >&2
    exit 1
fi
if [[ ! -d "$FRONTEND_DIR/node_modules/vite" ]]; then
    echo "$LOG_PREFIX [WARN] $FRONTEND_DIR/node_modules/vite 不存在,先跑: (cd $FRONTEND_DIR && bun install)"
fi

# 3. 进项目
cd "$FRONTEND_DIR"

# 4. 启动: 关键! --bun 强制 bun runtime 跑整条 script 调用链
#    不加 --bun 时,bun x vite 会 fallback 到 Node ESM loader 报
#    "SyntaxError: Unexpected reserved word"
echo "$LOG_PREFIX 启动 Vite dev (强制 bun runtime) ..."
exec "$BUN_BIN" --bun run dev
