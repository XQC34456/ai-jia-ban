"""目标对象 Schema：Goal Engine 的统一输出。

把 lump_sum（一次性）与 cashflow（现金流型）目标统一成同一个对象，
前端/Agent 无需区分底层测算路径。
"""
from __future__ import annotations

from pydantic import BaseModel

__all__ = ["GoalOut"]


class GoalOut(BaseModel):
    """一个统一目标对象。

    coverage 为当前资金对目标金额的覆盖程度（0~1，确定性测算，非概率）。
    priority 沿用 goal 表语义：1=高 / 2=中 / 3=低。
    """
    goal_id: int | None = None
    type: str = "其他"                 # 教育/买房/养老/旅行/创业/大额消费/其他
    name: str = ""
    goal_kind: str = "lump_sum"        # lump_sum / cashflow
    target_amount: float = 0.0         # 目标终值（cashflow 型为 fv_target）
    target_date: str | None = None
    current_saved: float = 0.0
    monthly_needed: float | None = None  # 每月需投入
    gap: float = 0.0                   # 资金缺口
    coverage: float = 0.0              # 当前资金 / 目标金额（0~1）
    priority: int | None = None        # 1/2/3
