"""统一 I/O Schema：Wealth Engine API 的 JSON Contract（pydantic v2）。

engine 内部继续用 dict（纯函数、零依赖），Schema 只负责 API 边界的请求/响应契约，
是前端 / AI Agent / 驾驶舱 / 财富沙盘共同读取的唯一数据结构定义。
"""
from .family import FamilyData
from .issue import Issue, Recommendation
from .goal import GoalOut
from .scenario import ScenarioRequest
from .wealth import (
    Overview, RetirementBlock, CashflowBlock, LiquidityBlock, DebtBlock, ProtectionBlock,
)

__all__ = [
    "FamilyData",
    "Issue", "Recommendation",
    "GoalOut",
    "ScenarioRequest",
    "Overview", "RetirementBlock", "CashflowBlock", "LiquidityBlock", "DebtBlock", "ProtectionBlock",
]
