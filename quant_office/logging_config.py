"""统一日志配置 — 独立模式与插件模式共享。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    *,
    force: bool = False,
) -> logging.Logger:
    """初始化 QuantOffice 日志。

    Parameters
    ----------
    level:
        日志级别，默认 ``INFO``。
    log_file:
        可选的文件输出路径。插件模式一般由宿主提供 logger，本函数不强制输出文件。
    force:
        是否覆盖已有 handler（用于测试隔离）。
    """
    global _initialized
    root = logging.getLogger("quant_office")

    if _initialized and not force:
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        return root

    for handler in list(root.handlers):
        root.removeHandler(handler)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # 抑制某些嘈杂的库
    for noisy in ("uvicorn.access", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _initialized = True
    return root


def get_logger(name: str) -> logging.Logger:
    """获取 ``quant_office`` 命名空间下的 logger。"""
    return logging.getLogger(f"quant_office.{name}")
