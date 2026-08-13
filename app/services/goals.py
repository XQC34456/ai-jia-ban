"""Goal Engine：把 lump_sum / cashflow 目标统一成同一个目标对象。

复用 engine 的 metrics.goal_gap（内部已分派两种目标类型），本层只做「统一形状」。
"""
from __future__ import annotations

from app.engine import metrics

__all__ = ["build_goals"]


def build_goals(family_data: dict) -> list[dict]:
    """返回统一目标对象列表（GoalOut 形状），供 Overview 与 Goal API 复用。"""
    out: list[dict] = []
    for g in family_data.get("goals", []):
        gap = metrics.goal_gap(g)
        kind = g.get("goal_kind") or ("cashflow" if gap.get("kind") == "cashflow" else "lump_sum")
        out.append({
            "goal_id": g.get("id"),
            "type": g.get("type") or "其他",
            "name": gap["name"],
            "goal_kind": kind,
            "target_amount": gap["target_amount"],
            "target_date": g.get("target_date"),
            "current_saved": gap["current_saved"],
            "monthly_needed": gap["monthly_needed"],
            "gap": gap["gap"],
            "coverage": round(gap["progress"], 4),
            "priority": g.get("priority"),
        })
    return out
