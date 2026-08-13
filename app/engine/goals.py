"""Wealth Engine · 目标测算：现金流型目标（如教育金每年 N 万 × M 年）规划。

明确假设参数（显式传入，绝不由 LLM 生成或计算）：
- inflation：年通胀率（小数，0.03 = 3%）；
- return_rate：目标资金积累期的年化收益率（小数）。
"""
from __future__ import annotations

__all__ = ["plan_cashflow_goal", "allocation_recommendation"]


def plan_cashflow_goal(annual_amount, duration_years, years_until_start,
                       current_saved=0.0, inflation=0.03, return_rate=0.03):
    """现金流型目标测算：每年需 annual_amount、持续 duration_years 年的支出。

    返回：目标终值 fv_target、已备资金终值 fv_saved、缺口 gap、
    每月需存 monthly_save、以及按期限给出的配置建议 allocation。
    """
    fv_target = annual_amount * duration_years * (1 + inflation) ** years_until_start
    fv_saved = current_saved * (1 + return_rate) ** years_until_start
    gap = max(fv_target - fv_saved, 0.0)
    n = years_until_start * 12
    if n <= 0:
        monthly_save = gap
    else:
        r = return_rate / 12.0
        monthly_save = gap * r / ((1 + r) ** n - 1) if r > 0 else gap / n
    return {
        "fv_target": round(fv_target, 2),
        "fv_saved": round(fv_saved, 2),
        "gap": round(gap, 2),
        "monthly_save": round(monthly_save, 2),
        "allocation": allocation_recommendation(years_until_start),
    }


def allocation_recommendation(years_until_need: int) -> dict:
    """按距离用款年限给出保守/进取配置建议（保守占比 + 进取占比）。"""
    if years_until_need <= 3:
        return {"conservative_pct": 0.8, "aggressive_pct": 0.2}
    if years_until_need <= 7:
        return {"conservative_pct": 0.6, "aggressive_pct": 0.4}
    return {"conservative_pct": 0.3, "aggressive_pct": 0.7}
