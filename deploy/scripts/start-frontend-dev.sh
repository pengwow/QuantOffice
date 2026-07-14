#!/usr/bin/env bash
# =============================================================================
# QuantOffice 前端 Vite dev 启动 wrapper
# -----------------------------------------------------------------------------
# 解决的问题(按出现顺序):
#
# 1) `bun run dev` → `bun x vite` → vite.js 第 7 行
#        `await import('source-map-support')` 报
#        "SyntaxError: Unexpected reserved word"
#    根因: 老版 bun(< 1.1)的 `bun x` fallback 到 Node CJS loader
#    修复: 强制 `bun --bun run dev`(PR #18)
#
# 2) bun 1.3.x baseline 版在完全没 AVX 的 CPU 上仍然 panic
#    "CPU lacks AVX support. Please consider upgrading to a newer CPU.
#     panic(main thread): Illegal instruction"
#    根因: bun 1.3+ 的 jsc 内核在 baseline build 里仍硬编码了部分 AVX
#         指令,即使 CPU 没 avx flag 也会 SIGILL
#    修复: 优先用 node 跑 vite(本轮 PR #20)
#         - 探测 node 路径(PATH / nvm / 常见安装点)
#         - node 18+ 都能跑 vite,无 SIMD 要求
#         - 没 node 才退化到 bun baseline(并打 warning)
#
# 用法: deploy/scripts/start-frontend-dev.sh
# 装位置: /opt/quantoffice/scripts/start-frontend-dev.sh
# =============================================================================
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/QuantOffice}"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
LOG_PREFIX="[start-frontend-dev]"

# -----------------------------------------------------------------------------
# 1. CPU AVX/AVX2 探测(信息用,不做硬阻断)
# -----------------------------------------------------------------------------
cpu_has_avx2() {
    if [[ -r /proc/cpuinfo ]] && grep -qE '(^| )avx2( |$)' /proc/cpuinfo; then
        return 0
    fi
    return 1
}

# -----------------------------------------------------------------------------
# 2. 找 node(vite 真正需要的 runtime)
# -----------------------------------------------------------------------------
find_node() {
    # 优先 PATH
    local n
    n="$(command -v node 2>/dev/null || true)"
    if [[ -n "$n" && -x "$n" ]]; then
        # 验证 node 能跑(node 没有 SIGILL 问题,跑下 --version)
        if "$n" --version >/dev/null 2>&1; then
            echo "$n"
            return 0
        fi
    fi
    # nvm: 每个用户目录下的 node
    for candidate in \
        "$HOME/.nvm/versions/node/*/bin/node" \
        /root/.nvm/versions/node/*/bin/node \
        /home/*/.nvm/versions/node/*/bin/node \
        /usr/local/bin/node \
        /usr/bin/node \
        /opt/node/bin/node
    do
        for c in $candidate; do
            if [[ -x "$c" ]] && "$c" --version >/dev/null 2>&1; then
                echo "$c"
                return 0
            fi
        done
    done
    return 1
}

# -----------------------------------------------------------------------------
# 3. 找 bun(只在没 node 时用,且 baseline 版仍可能崩)
# -----------------------------------------------------------------------------
find_bun() {
    local candidates=(
        "$HOME/.bun/bin/bun"
        /root/.bun/bin/bun
        /opt/quantoffice/bun/bin/bun
        /home/*/.bun/bin/bun
        /opt/bun/bin/bun
        /usr/local/bin/bun
        /usr/bin/bun
    )
    for c in "${candidates[@]}"; do
        for cc in $c; do
            if [[ -x "$cc" ]] && "$cc" --version >/dev/null 2>&1; then
                echo "$cc"
                return 0
            fi
        done
    done
    return 1
}

# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------
echo "$LOG_PREFIX 启动 Vite dev wrapper (project=$PROJECT_ROOT)"

if ! cpu_has_avx2; then
    echo "$LOG_PREFIX [INFO] CPU 不支持 AVX2 — bun 1.3+ baseline 也会 panic,改用 node 跑 vite"
fi

# 校验 frontend
if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "$LOG_PREFIX [FATAL] 找不到 $FRONTEND_DIR(检查 supervisor 配置里的 PROJECT_ROOT)" >&2
    exit 1
fi
if [[ ! -d "$FRONTEND_DIR/node_modules/vite" ]]; then
    echo "$LOG_PREFIX [WARN] $FRONTEND_DIR/node_modules/vite 不存在"
    echo "$LOG_PREFIX 提示: 先跑 (cd $FRONTEND_DIR && bun install) 或 ./deploy.sh install"
fi

# -----------------------------------------------------------------------------
# 4. 选 runtime
#    优先 node 18+(稳,无 SIMD 要求)
#    fallback bun --bun(可能 SIGILL,但至少试一下)
# -----------------------------------------------------------------------------
NODE_BIN="$(find_node 2>/dev/null || true)"
BUN_BIN="$(find_bun 2>/dev/null || true)"

if [[ -n "$NODE_BIN" ]]; then
    NODE_VER="$("$NODE_BIN" --version 2>/dev/null || echo '?')"
    echo "$LOG_PREFIX 使用 node: $NODE_BIN ($NODE_VER)"

    cd "$FRONTEND_DIR"
    # 直接用 node 跑 vite 的 bin 脚本,绕开 bun
    # vite 5.x 兼容 node 18+
    exec "$NODE_BIN" ./node_modules/vite/bin/vite.js
else
    echo "$LOG_PREFIX [WARN] 没找到 node,退化到 bun"
    if [[ -z "$BUN_BIN" ]]; then
        echo "$LOG_PREFIX [FATAL] node 和 bun 都没装,装 node 18+ 后重试" >&2
        echo "$LOG_PREFIX   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -" >&2
        echo "$LOG_PREFIX   sudo apt install -y nodejs" >&2
        exit 127
    fi
    BUN_VER="$("$BUN_BIN" --version 2>/dev/null || echo '?')"
    echo "$LOG_PREFIX 使用 bun: $BUN_BIN ($BUN_VER) — 注意: bun 1.3+ baseline 在没 avx 的 CPU 上仍可能 SIGILL"
    cd "$FRONTEND_DIR"
    exec "$BUN_BIN" --bun run dev
fi
