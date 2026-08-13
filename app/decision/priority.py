"""问题优先级：severity 排序（P0 > P1 > P2）。"""
from __future__ import annotations

__all__ = ["SEVERITY_ORDER", "rank"]

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def rank(issues: list[dict]) -> list[dict]:
    """按 severity（P0→P2）排序；同级保持检测顺序稳定。"""
    return sorted(issues, key=lambda i: SEVERITY_ORDER.get(i.get("severity", "P2"), 9))
