"""Arrow / Parquet 时序数据存储。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

from ..config import settings
from ..logging_config import get_logger

logger = get_logger("data.arrow")

try:  # pragma: no cover - 可选依赖
    import pyarrow as pa
    import pyarrow.parquet as pq

    _ARROW_OK = True
except Exception:  # pragma: no cover
    _ARROW_OK = False


class ArrowStore:
    """Arrow RecordBatch / Parquet 文件存储。"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir or settings.resolved_data_dir) / "arrow"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, timeframe: str) -> Path:
        return self.base_dir / f"{symbol}_{timeframe}.parquet"

    def save_bars(self, symbol: str, timeframe: str, bars: List[dict]) -> Optional[Path]:
        if not _ARROW_OK or not bars:
            return None
        try:
            table = pa.Table.from_pylist(bars)
            path = self._path(symbol, timeframe)
            pq.write_table(table, path)
            return path
        except Exception as exc:  # pragma: no cover
            logger.warning("Arrow 保存失败: %s", exc)
            return None

    def load_bars(self, symbol: str, timeframe: str) -> List[dict]:
        if not _ARROW_OK:
            return []
        path = self._path(symbol, timeframe)
        if not path.exists():
            return []
        try:
            table = pq.read_table(path)
            return table.to_pylist()
        except Exception as exc:  # pragma: no cover
            logger.warning("Arrow 加载失败: %s", exc)
            return []
