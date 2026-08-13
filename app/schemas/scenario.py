"""情景模拟请求 Schema：统一 Scenario API 的输入契约。"""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["ScenarioRequest"]

# 引擎支持的情景名（engine.scenario.SCENARIOS 的键）
SCENARIO_NAMES = ("buy_house", "prepay", "invest", "income_change")


class ScenarioRequest(BaseModel):
    """情景模拟请求体。params 为场景参数，由 engine.scenario 各自解析。"""
    params: dict = Field(default_factory=dict)
