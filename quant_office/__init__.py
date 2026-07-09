"""QuantOffice 入口包。

两种运行模式共享的业务代码：
- 独立模式：``quant_office.app:app``  (FastAPI)
- 插件模式：``quant_office.plugin:register_plugin``  (QuantCell PluginBase)
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
