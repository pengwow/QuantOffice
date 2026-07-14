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
#    修复: 强制 `bun --bun run dev`
#
# 2) bun 1.3.6 在没有 AVX/AVX2 的 CPU 上 panic
#        "CPU lacks AVX support ... panic ... Illegal instruction"
#    根因: 1H1G 廉价服务器常用老 Intel Atom / Xeon,CPU 没 AVX
#    而 bun 官方 release 默认是 `+avx2` 构建,baseline 是单独 zip
#    修复: 探测 /proc/cpuinfo 没 avx2 flag 时,自动下载并切换到
#          bun-linux-x64-baseline.zip(去掉 SIMD 优化,普通 x86_64 都能跑)
#
# 用法: deploy/scripts/start-frontend-dev.sh
# 装位置: /opt/quantoffice/scripts/start-frontend-dev.sh
# =============================================================================
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/workspace/QuantOffice}"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
LOG_PREFIX="[start-frontend-dev]"
BUN_VERSION="${BUN_VERSION:-1.3.6}"
BUN_INSTALL_DIR="${BUN_INSTALL_DIR:-/opt/quantoffice/bun}"
BUN_BIN="$BUN_INSTALL_DIR/bin/bun"

# -----------------------------------------------------------------------------
# 1. CPU AVX/AVX2 探测
# -----------------------------------------------------------------------------
cpu_has_avx2() {
    # /proc/cpuinfo 读 flags,avx2 在就 echo 1
    if [[ -r /proc/cpuinfo ]]; then
        grep -qE '(^| )avx2( |$)' /proc/cpuinfo && return 0
    fi
    return 1
}

# -----------------------------------------------------------------------------
# 2. 装 baseline 版 bun(如果还没装且 CPU 不支持 AVX2)
# -----------------------------------------------------------------------------
install_bun_baseline() {
    echo "$LOG_PREFIX [INFO] 装 baseline 版 bun(v$BUN_VERSION, 无 AVX 需求)到 $BUN_INSTALL_DIR"

    local tmp_zip
    tmp_zip="$(mktemp --suffix=.zip)"
    local url="https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-x64-baseline.zip"

    if ! command -v curl >/dev/null 2>&1; then
        echo "$LOG_PREFIX [FATAL] 需要 curl 装 bun baseline" >&2
        exit 127
    fi
    if ! command -v unzip >/dev/null 2>&1; then
        echo "$LOG_PREFIX [FATAL] 需要 unzip 装 bun baseline" >&2
        exit 127
    fi

    curl -fsSL -o "$tmp_zip" "$url" \
        || { echo "$LOG_PREFIX [FATAL] 下载 $url 失败" >&2; rm -f "$tmp_zip"; exit 1; }

    mkdir -p "$BUN_INSTALL_DIR"
    unzip -oq -d "$BUN_INSTALL_DIR" "$tmp_zip" \
        || { echo "$LOG_PREFIX [FATAL] 解压 $tmp_zip 失败" >&2; rm -f "$tmp_zip"; exit 1; }
    rm -f "$tmp_zip"

    chmod +x "$BUN_BIN" 2>/dev/null || true
    echo "$LOG_PREFIX [OK] baseline bun 装好: $($BUN_BIN --version 2>/dev/null || echo '?')"
}

# -----------------------------------------------------------------------------
# 3. 找 / 准备 bun
# -----------------------------------------------------------------------------
ensure_bun() {
    # 优先用我们自己装的 baseline(无 AVX 需求)
    if [[ -x "$BUN_BIN" ]]; then
        # sanity check:跑一下 --version,如果 SIGILL 就当它坏了
        if "$BUN_BIN" --version >/dev/null 2>&1; then
            return 0
        else
            echo "$LOG_PREFIX [WARN] $BUN_BIN 跑不了(可能 SIGILL),重新装 baseline"
            rm -rf "$BUN_INSTALL_DIR"
        fi
    fi

    # 退化:用 PATH 里的 bun(但如果是 AVX 版会在老 CPU 上崩)
    local path_bun
    path_bun="$(command -v bun 2>/dev/null || true)"
    if [[ -n "$path_bun" && -x "$path_bun" ]]; then
        if "$path_bun" --version >/dev/null 2>&1; then
            BUN_BIN="$path_bun"
            echo "$LOG_PREFIX [WARN] 用 PATH 里的 bun: $BUN_BIN(没 avx2 时它会崩,改用 baseline)"
            return 0
        fi
    fi

    # 兜底:扫常见安装路径
    for candidate in \
        "$HOME/.bun/bin/bun" \
        /root/.bun/bin/bun \
        /home/*/.bun/bin/bun \
        /opt/bun/bin/bun \
        /usr/local/bin/bun \
        /usr/bin/bun
    do
        if [[ -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
            BUN_BIN="$candidate"
            return 0
        fi
    done

    # 都找不到,直接装 baseline
    install_bun_baseline
}

# 主流程
echo "$LOG_PREFIX 启动 Vite dev wrapper (project=$PROJECT_ROOT)"

# CPU 不支持 avx2 + 还没装 baseline bun → 装
if ! cpu_has_avx2 && [[ ! -x "$BUN_BIN" ]]; then
    echo "$LOG_PREFIX [INFO] CPU 不支持 AVX2(常见 1H1G 廉价 VPS)"
    install_bun_baseline
fi

ensure_bun

# 再次确认 bun 能跑(尤其是 PATH 来的 bun 可能是 AVX 版)
if ! "$BUN_BIN" --version >/dev/null 2>&1; then
    echo "$LOG_PREFIX [WARN] 当前 bun 跑不了,改装 baseline"
    rm -rf "$BUN_INSTALL_DIR"
    install_bun_baseline
fi

echo "$LOG_PREFIX 使用 bun: $BUN_BIN ($($BUN_BIN --version))"

# -----------------------------------------------------------------------------
# 4. 校验 frontend
# -----------------------------------------------------------------------------
if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "$LOG_PREFIX [FATAL] 找不到 $FRONTEND_DIR" >&2
    echo "$LOG_PREFIX 提示: 检查 supervisor 配置里的 PROJECT_ROOT" >&2
    exit 1
fi
if [[ ! -d "$FRONTEND_DIR/node_modules/vite" ]]; then
    echo "$LOG_PREFIX [WARN] $FRONTEND_DIR/node_modules/vite 不存在"
    echo "$LOG_PREFIX 提示: 先跑 (cd $FRONTEND_DIR && bun install) 或 ./deploy.sh install"
fi

# -----------------------------------------------------------------------------
# 5. 启动 Vite dev
#    关键: --bun 强制 bun runtime 跑整条 script 链
#    避免 bun x fallback 到 Node CJS loader 报 "Unexpected reserved word"
# -----------------------------------------------------------------------------
cd "$FRONTEND_DIR"
exec "$BUN_BIN" --bun run dev
