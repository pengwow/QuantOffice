"""QuantOffice CLI 入口 — 暴露 ``quant-office`` 命令。

两种启动方式等价：
- ``python run.py``（仓库根目录）
- ``quant-office``（安装后任意目录）
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quant-office",
        description="QuantOffice 量化交易指挥中枢（独立模式）",
    )
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    parser.add_argument("--log-level", default="info", help="uvicorn 日志级别")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print("错误: 未安装 uvicorn，请先 `uv sync`", file=sys.stderr)
        return 1

    print(f"QuantOffice 启动中... http://{args.host}:{args.port}")
    print(f"   API 文档:    http://localhost:{args.port}/docs")
    print(f"   像素办公室:  http://localhost:{args.port}/")
    print(f"   WebSocket:   ws://localhost:{args.port}/ws")
    print()

    uvicorn.run(
        "quant_office.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
