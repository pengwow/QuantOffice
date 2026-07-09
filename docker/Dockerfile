FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" \
    "pydantic>=2.6" "pydantic-settings>=2.2" \
    "sqlalchemy>=2.0" "aiosqlite>=0.20" \
    "pyarrow>=15.0" "httpx>=0.27"

# 应用代码
COPY quant_office ./quant_office
COPY run.py ./

# 数据目录
RUN mkdir -p /app/data
ENV QUANT_OFFICE_DATA_DIR=/app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
