# QuantOffice — 常用 uv / make 命令
# 使用：`make help` 查看所有命令

.PHONY: help install sync sync-dev run dev test test-cov lint fmt clean lock-export

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 安装 uv（如果没有）
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	@uv --version

sync:  ## 安装运行时依赖
	uv sync --no-dev

sync-dev:  ## 安装运行时 + 开发依赖
	uv sync --group dev

run:  ## 启动服务器
	uv run python run.py

dev:  ## 启动开发服务器（热重载）
	uv run python run.py --reload --port 8000

test:  ## 运行测试
	uv run pytest -v

test-cov:  ## 运行测试并生成覆盖率报告
	uv run pytest --cov=quant_office --cov-report=html --cov-report=term

lint:  ## 代码检查
	uv run ruff check .

fmt:  ## 代码格式化
	uv run ruff format .

lock-export:  ## 同步 pyproject.toml -> requirements.txt
	uv lock
	uv export --no-hashes --format requirements-txt > requirements.txt
	uv export --no-hashes --format requirements-txt --group dev > requirements-dev.txt
	@echo "✓ requirements.txt 和 requirements-dev.txt 已更新"

clean:  ## 清理缓存
	rm -rf .venv .pytest_cache .ruff_cache .coverage htmlcov build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
