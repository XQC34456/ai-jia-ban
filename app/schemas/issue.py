"""财富问题对象 Schema：Decision Layer 的统一输出结构。

AI Agent / 前端 / 提醒系统 / 报告系统全部读取这个对象，而不是各自拼字符串。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["Recommendation", "Issue"]


class Recommendation(BaseModel):
    """一条「动作化」建议——只到资产类别/行为层，绝不推荐具体产品。"""
    action: str                        # 动作名，如「增加金融资产」
    detail: str = ""                   # 一句话说明为什么 + 怎么做
    target: str | None = None          # 量化目标，如「RFR 0.48 → ≥1.0」


class Issue(BaseModel):
    """一个财富问题（问题 → 原因 → 指标 → 目标 → 建议 → 方案）。"""
    issue_id: str                      # 稳定 ID，如 RETIREMENT_LIQUIDITY_001
    type: str                          # cashflow/liquidity/debt/allocation/retirement/goals/decision
    severity: str                      # P0 / P1 / P2
    title: str                         # 一句话问题，如「退休流动资金不足」
    finding: str = ""                  # 关键发现，如「RFR 仅为 0.48」
    reason: list[str] = Field(default_factory=list)   # 原因列表
    metric: dict = Field(default_factory=dict)        # 支撑指标（rfr/nwc/dti 等）
    target: dict = Field(default_factory=dict)        # 目标指标
    recommendations: list[Recommendation] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)  # 可触发的场景方案
