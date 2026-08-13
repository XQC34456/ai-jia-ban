"""A3 Tool Dispatcher：intent → A2 工具（纯映射，零 LLM、零财富计算）。

CHECK_RETIREMENT / CHECK_ALLOCATION 复用 get_overview 后读子字段（不新增工具）；
EXPLAIN_RESULT 复用上下文、不调工具；SCENARIO_COMPARE 需要 scenario + params。
"""
from __future__ import annotations

from .tools import compare_scenario, get_goals, get_issues, get_overview

__all__ = ["INTENT_TOOL", "dispatch"]

INTENT_TOOL = {
    "VIEW_OVERVIEW": get_overview,
    "CHECK_ISSUES": get_issues,
    "CHECK_GOALS": get_goals,
    "CHECK_RETIREMENT": get_overview,
    "CHECK_ALLOCATION": get_overview,
    "SCENARIO_COMPARE": None,    # 需 scenario + params，见 dispatch 特判
    "EXPLAIN_RESULT": None,      # 复用上下文，不调工具
}


def dispatch(intent: str, user: dict, scenario: str | None = None,
             params: dict | None = None):
    """按意图分派到 A2 工具。SCENARIO_COMPARE 调 compare_scenario；EXPLAIN_RESULT 返回 None。"""
    if intent == "SCENARIO_COMPARE":
        return compare_scenario(user, scenario, params)
    if intent == "EXPLAIN_RESULT":
        return None
    return INTENT_TOOL[intent](user)
