"""conftest — pytest 共享配置。"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保 ``import quant_office`` 能找到包
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
