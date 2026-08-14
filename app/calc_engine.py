"""兼容层：转发到 app.engine.metrics，旧 import 路径（from . import calc_engine）不变。

⚠️ 历史 shim：main.py / report.py / decision.simulate 仍通过 `from . import calc_engine` 引用。
V2.1 数据治理不清理（有 test_calc_engine.py test lock），迁移时机留后续阶段。
"""
from app.engine.metrics import *  # noqa: F401,F403
