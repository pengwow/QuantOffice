FROM python:3.12-slim

# ---- uv 安装 ----
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- 依赖层（利用 Docker 缓存）----
# 1) 仅复制 lock 文件 + pyproject.toml，先解析依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# 2) 复制源码并安装项目本身
COPY quant_office ./quant_office
COPY run.py ./
RUN uv sync --no-dev --frozen

# 数据目录
RUN mkdir -p /app/data
ENV QUANT_OFFICE_DATA_DIR=/app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
