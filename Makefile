# QuantOffice — 常用 uv / make 命令
# 使用：`make help` 查看所有命令

.PHONY: help install sync sync-dev run dev test test-cov lint fmt clean lock-export \
        fe-install fe-dev fe-build fe-typecheck fe-clean

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 安装 uv（如果没有）
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	@uv --version

sync:  ## 安装运行时依赖
	uv sync --no-dev

sync-dev:  ## 安装运行时 + 开发依赖
	uv sync --group dev

run:  ## 启动 FastAPI 后端
	uv run python run.py

dev:  ## 启动开发服务器（热重载）
	uv run python run.py --reload --port 8000

test:  ## 运行后端测试
	uv run pytest -v

test-cov:  ## 运行测试并生成覆盖率报告
	uv run pytest --cov=quant_office --cov-report=html --cov-report=term

lint:  ## 代码检查（Python）
	uv run ruff check .

fmt:  ## 代码格式化（Python）
	uv run ruff format .

lock-export:  ## 同步 pyproject.toml -> requirements.txt
	uv lock
	uv export --no-hashes --format requirements-txt > requirements.txt
	uv export --no-hashes --format requirements-txt --group dev > requirements-dev.txt
	@echo "✓ requirements.txt 和 requirements-dev.txt 已更新"

# ==================== 前端（bun + vite） ====================
fe-install:  ## 安装前端依赖（需要 bun）
	@command -v bun >/dev/null || { echo "✗ bun 未安装，请先运行: curl -fsSL https://bun.sh/install | bash"; exit 1; }
	cd frontend && bun install

fe-dev:  ## 启动 Vite 开发服务器（端口 5173）
	cd frontend && bun run dev

fe-build:  ## 生产构建前端（输出 frontend/dist/）
	cd frontend && bun run build

fe-typecheck:  ## 前端 TypeScript 类型检查
	cd frontend && bun run typecheck

fe-preview:  ## 预览生产构建
	cd frontend && bun run preview

# ==================== 一键全栈开发 ====================
dev-all:  ## 同时启动后端 + 前端（需要安装 tmux 或两个终端）
	@echo "Terminal 1: make dev         (FastAPI :8000)"
	@echo "Terminal 2: make fe-dev      (Vite    :5173)"

clean:  ## 清理所有缓存
	rm -rf .venv .pytest_cache .ruff_cache .coverage htmlcov build dist
	rm -rf frontend/dist frontend/node_modules frontend/.vite frontend/bun.lockb
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
