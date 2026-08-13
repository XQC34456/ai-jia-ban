"""Decision Layer 共享上下文：把 Engine 结果一次性算好，供各检测器复用。"""
from __future__ import annotations

from app.engine import allocation, metrics, score

__all__ = ["compute_context"]


def compute_context(family_data: dict) -> dict:
    """计算 Decision Layer 与 Overview 共同需要的 Engine 结果。

    返回 {snap, ws, fit, alloc, rfr}：
    - snap: metrics.snapshot（现金流/流动性/负债/目标资金竞争）
    - ws:   score.wealth_score（七维度财富评分）
    - fit:  allocation.allocation_fitness（配置适配度 + 集中度 + 偏离 + 理由）
    - alloc: allocation.analyze（六类占比 + 增配/减配建议）
    - rfr:  score.retirement_ratio（RFR/NWC，无年龄信息时为 None）
    """
    assets = family_data.get("assets", [])
    liabilities = family_data.get("liabilities", [])
    cashflows = family_data.get("cashflows", [])
    goals = family_data.get("goals", [])
    profile = family_data.get("family_profile") or {}

    return {
        "snap": metrics.snapshot(family_data),
        "ws": score.wealth_score(family_data),
        "fit": allocation.allocation_fitness(assets, profile, cashflows, liabilities, goals),
        "alloc": allocation.analyze(assets, profile, cashflows, liabilities),
        "rfr": score.retirement_ratio(family_data),
    }
