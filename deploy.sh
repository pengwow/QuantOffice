#!/usr/bin/env bash
# =============================================================================
# QuantOffice 一键部署脚本
# -----------------------------------------------------------------------------
# 功能：
#   env      环境检查（python / uv / bun / curl / 端口可用性）
#   install  安装后端(uv sync) + 前端(bun install) + 构建前端(bun run build)
#   init     初始化数据库 + 注入演示数据
#   start    后台拉起后端服务（写入 PID 文件）
#   stop     通过 PID 文件停止服务
#   restart  停 + 拉
#   status   查看服务状态 / 端口 / 日志尾部
#   e2e      跑 P7 全链路探针（依赖服务已起）
#   all      env → install → init → start 一条龙
#   help     打印帮助
#
# 用法：
#   ./deploy.sh all                 # 一键全流程
#   ./deploy.sh install --with-rl   # 安装并加装 RL 扩展
#   ./deploy.sh start --port 8765   # 自定义端口
#   ./deploy.sh stop
#   ./deploy.sh restart
#   ./deploy.sh status
#
# 设计目标：CI=true / 非 TTY 环境也能直接跑；
#          所有阻塞命令都带超时；失败即退出（set -euo pipefail）。
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# 常量
# -----------------------------------------------------------------------------
SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 从 .python-version 读 Python 版本要求
PYTHON_VERSION="$(cat .python-version 2>/dev/null | tr -d ' \n' || echo '3.14')"

# 运行时目录
LOGS_DIR="$SCRIPT_DIR/logs"
DATA_DIR="$SCRIPT_DIR/data"
RUN_DIR="$SCRIPT_DIR/.run"
PID_FILE="$RUN_DIR/backend.pid"
LOG_FILE="$LOGS_DIR/backend.log"

# 服务默认值（可用 CLI 覆盖）
HOST="0.0.0.0"
PORT="8765"
WITH_AXON=0
WITH_RL=0
SKIP_FRONTEND=0
SKIP_E2E=0
LOW_MEM=0
E2E_BASE=""  # 默认拼 http://127.0.0.1:$PORT

# 颜色（CI=true 时自动关闭）
if [[ "${CI:-false}" == "true" || ! -t 1 ]]; then
    C_RESET=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""
else
    C_RESET="\033[0m"; C_RED="\033[31m"; C_GREEN="\033[32m"
    C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_BOLD="\033[1m"
fi

# -----------------------------------------------------------------------------
# 日志工具
# -----------------------------------------------------------------------------
log()   { printf "%b[INFO]%b  %s\n" "$C_BLUE"  "$C_RESET" "$*"; }
ok()    { printf "%b[ OK ]%b  %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf "%b[WARN]%b  %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
err()   { printf "%b[FAIL]%b  %s\n" "$C_RED"   "$C_RESET" "$*" >&2; }
die()   { err "$*"; exit 1; }
title() { printf "\n%b== %s ==%b\n" "$C_BOLD$C_BLUE" "$*" "$C_RESET"; }

# -----------------------------------------------------------------------------
# 帮助
# -----------------------------------------------------------------------------
usage() {
    cat <<EOF
${C_BOLD}QuantOffice 一键部署脚本${C_RESET}

${C_BOLD}用法:${C_RESET}
  $SCRIPT_NAME <command> [options]

${C_BOLD}命令:${C_RESET}
  env          环境检查（python / uv / bun / curl / 端口）
  install      安装全部依赖（uv sync + bun install + 前端构建）
  init         初始化数据库 + 注入演示数据
  start        后台拉起后端（写 PID 到 $PID_FILE）
  stop         停止后端
  restart      停 + 拉
  status       服务状态 / 端口 / 日志尾部
  e2e          跑 P7 全链路探针（服务须已起）
  all          env → install → init → start 一条龙
  help         打印本帮助

${C_BOLD}通用选项:${C_RESET}
  --port PORT        监听端口（默认 8765）
  --host HOST        监听地址（默认 0.0.0.0）
  --with-axon        uv sync --extra axon
  --with-rl          uv sync --extra rl
  --skip-frontend    install 时跳过前端 bun install / build
  --skip-e2e         all / install 时不强制 e2e
  --low-mem          强制低内存模式(限制 Vite/Node 堆内存,适合 1H1G)
  -h, --help         打印帮助

${C_BOLD}示例:${C_RESET}
  $SCRIPT_NAME all
  $SCRIPT_NAME install --with-axon
  $SCRIPT_NAME start --port 8765
  $SCRIPT_NAME restart
  $SCRIPT_NAME status
  $SCRIPT_NAME e2e --port 8765
EOF
}

# -----------------------------------------------------------------------------
# 参数解析
# -----------------------------------------------------------------------------
CMD="${1:-help}"
shift || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)            PORT="$2"; shift 2 ;;
        --host)            HOST="$2"; shift 2 ;;
        --with-axon)       WITH_AXON=1; shift ;;
        --with-rl)         WITH_RL=1; shift ;;
        --skip-frontend)   SKIP_FRONTEND=1; shift ;;
        --skip-e2e)        SKIP_E2E=1; shift ;;
        --low-mem)         LOW_MEM=1; shift ;;
        -h|--help)         usage; exit 0 ;;
        *) die "未知参数: $1（用 $SCRIPT_NAME help 查看用法）" ;;
    esac
done

E2E_BASE="${E2E_BASE:-http://127.0.0.1:${PORT}}"

# -----------------------------------------------------------------------------
# 目录准备
# -----------------------------------------------------------------------------
ensure_dirs() {
    mkdir -p "$LOGS_DIR" "$DATA_DIR" "$RUN_DIR"
}

# -----------------------------------------------------------------------------
# 环境检查
# -----------------------------------------------------------------------------
check_command() {
    local cmd="$1" min_version="${2:-}"
    if command -v "$cmd" >/dev/null 2>&1; then
        local ver
        ver="$("$cmd" --version 2>/dev/null | head -n1 || true)"
        if [[ -n "$min_version" ]]; then
            ok "[$cmd] $ver"
        else
            ok "[$cmd] $ver"
        fi
        return 0
    else
        err "[$cmd] 未安装"
        return 1
    fi
}

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        ok "[uv] $(uv --version)"
        return 0
    fi
    warn "[uv] 未安装，正在安装 ..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
    else
        die "请先安装 curl，再重试（uv 安装脚本依赖 curl）"
    fi
    # 刷新 PATH（uv 默认装到 ~/.local/bin）
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null 2>&1 || die "uv 安装失败，请手动安装"
    ok "[uv] 已安装: $(uv --version)"
}

ensure_bun() {
    if command -v bun >/dev/null 2>&1; then
        ok "[bun] $(bun --version)"
        return 0
    fi
    warn "[bun] 未安装，正在安装 ..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL https://bun.sh/install | bash >/dev/null
    else
        die "请先安装 curl，再重试（bun 安装脚本依赖 curl）"
    fi
    # 刷新 PATH（bun 默认装到 ~/.bun/bin）
    export PATH="$HOME/.bun/bin:$PATH"
    command -v bun >/dev/null 2>&1 || die "bun 安装失败，请手动安装"
    ok "[bun] 已安装: $(bun --version)"
}

check_python_version() {
    if ! command -v python"$PYTHON_VERSION" >/dev/null 2>&1 \
       && ! command -v python3 >/dev/null 2>&1; then
        err "Python $PYTHON_VERSION / python3 均未找到"
        return 1
    fi
    local py
    py="$(command -v python"$PYTHON_VERSION" 2>/dev/null || command -v python3)"
    local ver
    ver="$("$py" -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
    if [[ "$ver" != "$PYTHON_VERSION"* ]]; then
        warn "检测到 Python $ver，项目要求 $PYTHON_VERSION（uv 会自动下载匹配版本，不强制阻断）"
    else
        ok "[python] $ver"
    fi
    return 0
}

check_port_free() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        if ss -ltn 2>/dev/null | awk '{print $4}' | grep -E "[:.]${port}$" >/dev/null; then
            err "端口 $port 已被占用（ss）"
            return 1
        fi
    elif command -v lsof >/dev/null 2>&1; then
        if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            err "端口 $port 已被占用（lsof）"
            return 1
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -ltn 2>/dev/null | awk '{print $4}' | grep -E "[:.]${port}$" >/dev/null; then
            err "端口 $port 已被占用（netstat）"
            return 1
        fi
    else
        warn "ss / lsof / netstat 均不可用，跳过端口检查"
    fi
    return 0
}

# 探测可用内存(GB,两位小数);Linux 读 /proc/meminfo,失败返回空串
detect_memory_gb() {
    if [[ -r /proc/meminfo ]]; then
        awk '/MemAvailable:/ {printf "%.2f", $2/1024/1024}' /proc/meminfo
    fi
}

# mem_lt <gb> <threshold>:浮点比较,避免依赖 bc(用 awk 做)
mem_lt() {
    awk -v m="${1:-0}" -v t="${2:-0}" 'BEGIN{exit !(m+0 < t+0)}'
}

# -----------------------------------------------------------------------------
# 子命令: env
# -----------------------------------------------------------------------------
cmd_env() {
    title "环境检查 (要求 Python $PYTHON_VERSION)"
    local fail=0
    check_command bash || fail=1
    check_command curl || fail=1
    check_python_version || fail=1
    ensure_uv || fail=1
    ensure_bun || fail=1
    check_port_free "$PORT" || fail=1

    # 内存检测(1H1G 机器友好性)
    local mem_gb
    mem_gb="$(detect_memory_gb)"
    if [[ -n "$mem_gb" ]]; then
        if mem_lt "$mem_gb" 1.5; then
            warn "[mem] ${mem_gb}G 可用 — 低内存机器,建议 ./deploy.sh install --skip-frontend 然后用 Vite dev 模式"
            LOW_MEM=1
        else
            ok "[mem] ${mem_gb}G 可用"
        fi
    else
        warn "[mem] 无法探测可用内存(无 /proc/meminfo)"
    fi

    if [[ $fail -ne 0 ]]; then
        die "环境检查未通过（详见上方 [FAIL]）"
    fi
    ok "环境检查通过 ✓"
}

# -----------------------------------------------------------------------------
# 子命令: install
# -----------------------------------------------------------------------------
cmd_install() {
    title "安装依赖"
    ensure_uv
    ensure_bun
    ensure_dirs

    # ---- 后端 ----
    title "后端依赖 (uv sync)"
    local extra_flags=()
    [[ $WITH_AXON -eq 1 ]] && extra_flags+=("--extra" "axon")
    [[ $WITH_RL   -eq 1 ]] && extra_flags+=("--extra" "rl")
    log "执行: uv sync ${extra_flags[*]:-}"
    uv sync "${extra_flags[@]}"

    # ---- 前端 ----
    if [[ $SKIP_FRONTEND -eq 1 ]]; then
        warn "已 --skip-frontend，跳过前端安装 / 构建"
        warn "前端请用 dev 模式: cd frontend && bun run dev (Vite :5173 自动代理 :$PORT)"
    else
        title "前端依赖 (bun install)"
        if [[ ! -d frontend ]]; then
            warn "frontend/ 目录不存在，跳过前端步骤"
        else
            (cd frontend && bun install)

            title "前端构建 (bun run build)"
            # 低内存机器:Vite/Rollup 在 transforming 阶段容易 OOM 卡死
            # 限制 Node 堆内存到 512M,显著降低被杀概率
            local mem_gb
            mem_gb="$(detect_memory_gb)"
            if [[ $LOW_MEM -eq 1 ]] || { [[ -n "$mem_gb" ]] && mem_lt "$mem_gb" 2.0; }; then
                warn "[low-mem] 检测到 ${mem_gb:-?}G 可用,Vite 限制堆内存到 512M"
                warn "[low-mem] 如果还卡住,直接 Ctrl+C 然后跑: ./deploy.sh install --skip-frontend"
                warn "[low-mem] 再用 'cd frontend && bun run dev' 走 Vite 开发模式(HMR 即时刷新)"
                export NODE_OPTIONS="--max-old-space-size=512"
            fi
            (cd frontend && bun run build)
            ok "前端构建产物: frontend/dist/"
        fi
    fi

    ok "依赖安装完成 ✓"
}

# -----------------------------------------------------------------------------
# 子命令: init
# -----------------------------------------------------------------------------
cmd_init() {
    title "初始化数据"
    ensure_uv
    ensure_dirs

    export QUANT_OFFICE_DATA_DIR="$DATA_DIR"
    export QUANT_OFFICE_PROJECT_ROOT="$SCRIPT_DIR"

    # 1) 建表（lifespan 会做，但 init 提前兜底）
    log "建表 + 注入演示数据 ..."
    if ! uv run python -c "
import asyncio
from quant_office.data.database import init_database
from quant_office.demo import seed_if_empty, reset_and_seed
import sys

init_database()
mode = sys.argv[1] if len(sys.argv) > 1 else 'seed'
if mode == 'reset':
    counts = asyncio.run(reset_and_seed())
else:
    counts = asyncio.run(seed_if_empty())
print('counts=' + str(counts))
" "${INIT_MODE:-seed}"; then
        die "数据库初始化失败"
    fi

    ok "数据库初始化完成 ✓"
    log "DB 文件: $DATA_DIR/quant_office.db"
}

# -----------------------------------------------------------------------------
# 子命令: start
# -----------------------------------------------------------------------------
is_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" 2>/dev/null
}

cmd_start() {
    title "拉起后端服务"
    ensure_uv
    ensure_dirs

    if is_running; then
        warn "服务已在运行 (PID $(cat "$PID_FILE"))，跳过"
        return 0
    fi

    check_port_free "$PORT" || die "端口 $PORT 被占，请 --port 指定其它端口或先 stop"

    export QUANT_OFFICE_DATA_DIR="$DATA_DIR"
    export QUANT_OFFICE_PROJECT_ROOT="$SCRIPT_DIR"

    log "启动: uv run python run.py --host $HOST --port $PORT"
    log "日志: $LOG_FILE"
    log "PID : $PID_FILE"

    # nohup + setsid 避免脚本退出导致子进程被收尸
    nohup uv run python run.py --host "$HOST" --port "$PORT" \
        >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    disown "$pid" 2>/dev/null || true

    # 等待健康检查
    log "等待健康检查 $E2E_BASE/api/health ..."
    local ok_health=0
    for i in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            err "进程已退出，查看日志: $LOG_FILE"
            tail -n 50 "$LOG_FILE" || true
            rm -f "$PID_FILE"
            die "启动失败"
        fi
        if curl -fsS --max-time 2 "$E2E_BASE/api/health" >/dev/null 2>&1; then
            ok_health=1
            break
        fi
        sleep 1
    done

    if [[ $ok_health -ne 1 ]]; then
        warn "30s 内未通过健康检查，但进程仍在运行 (PID $pid)，请查看日志"
    else
        ok "服务已起: $E2E_BASE  (PID $pid)"
        log "API 文档: $E2E_BASE/docs"
        log "前端 UI: $E2E_BASE/"
    fi
}

# -----------------------------------------------------------------------------
# 子命令: stop
# -----------------------------------------------------------------------------
cmd_stop() {
    title "停止后端服务"
    if ! is_running; then
        warn "服务未在运行"
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    log "向 PID $pid 发送 SIGTERM ..."
    kill -TERM "$pid" 2>/dev/null || true
    for i in {1..15}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            ok "服务已停止"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    warn "15s 未退出，发送 SIGKILL"
    kill -KILL "$pid" 2>/dev/null || true
    sleep 1
    rm -f "$PID_FILE"
    ok "强制停止完成"
}

# -----------------------------------------------------------------------------
# 子命令: restart
# -----------------------------------------------------------------------------
cmd_restart() {
    cmd_stop || true
    sleep 1
    cmd_start
}

# -----------------------------------------------------------------------------
# 子命令: status
# -----------------------------------------------------------------------------
cmd_status() {
    title "服务状态"
    if is_running; then
        local pid
        pid="$(cat "$PID_FILE")"
        ok "运行中  PID=$pid  端口=$PORT  base=$E2E_BASE"
    else
        warn "未运行  (期望 PID 文件: $PID_FILE)"
    fi

    # 健康检查
    if curl -fsS --max-time 3 "$E2E_BASE/api/health" >/dev/null 2>&1; then
        ok "健康检查 OK: $E2E_BASE/api/health"
    else
        warn "健康检查失败: $E2E_BASE/api/health（可能未启动 / 端口不一致）"
    fi

    # 日志尾部
    if [[ -f "$LOG_FILE" ]]; then
        echo
        log "日志尾部 (last 20 lines of $LOG_FILE):"
        tail -n 20 "$LOG_FILE" || true
    else
        warn "日志文件不存在: $LOG_FILE"
    fi
}

# -----------------------------------------------------------------------------
# 子命令: e2e
# -----------------------------------------------------------------------------
cmd_e2e() {
    title "E2E 全链路探针"
    ensure_uv
    if ! is_running; then
        warn "服务未在运行，自动 start ..."
        cmd_start
    fi
    log "执行: uv run python scripts/e2e_smoke.py --base $E2E_BASE"
    uv run python scripts/e2e_smoke.py --base "$E2E_BASE"
}

# -----------------------------------------------------------------------------
# 子命令: all
# -----------------------------------------------------------------------------
cmd_all() {
    cmd_env
    cmd_install
    cmd_init
    cmd_start
    if [[ $SKIP_E2E -eq 0 ]]; then
        cmd_e2e || warn "E2E 探针未通过（不阻断部署），请查看 reports/e2e_*.json"
    fi
    title "一键部署完成"
    cmd_status
}

# -----------------------------------------------------------------------------
# 路由
# -----------------------------------------------------------------------------
case "$CMD" in
    env)      cmd_env ;;
    install)  cmd_install ;;
    init)     cmd_init ;;
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    status)   cmd_status ;;
    e2e)      cmd_e2e ;;
    all)      cmd_all ;;
    help|-h|--help) usage ;;
    *)        usage; die "未知命令: $CMD" ;;
esac
