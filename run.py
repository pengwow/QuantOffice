#!/usr/bin/env python3
"""QuantOffice 独立模式启动入口。

示例：
    python run.py --port 8000 --reload
"""
from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="QuantOffice 量化交易指挥中枢（独立模式）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    parser.add_argument("--log-level", default="info", help="uvicorn 日志级别")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
