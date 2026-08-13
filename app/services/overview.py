"""Wealth Overview 编排：把 Engine + Decision Layer 组合成驾驶舱全量状态。

这是 /api/wealth/overview 的核心逻辑——纯函数、零数据库依赖，可独立单测。
前端只消费这一个对象，不自行计算任何财富逻辑。
"""
from __future__ import annotations

from app.decision import build_issues, compute_context, retirement_quadrant
from app.engine import metrics

from .goals import build_goals

__all__ = ["build_overview", "KNOWN_LIMITATIONS"]

# 模型能力边界：注入响应，供 AI Agent / 报告如实声明，不夸大当前模型能力。
KNOWN_LIMITATIONS = {
    "retirement": [
        "retirement_debt_service_not_included",
        "goal_retirement_semantic_overlap",
        "other_asset_liquidity_assumption",
    ],
}


def build_overview(family_data: dict) -> dict:
    """返回家庭财富驾驶舱的完整 JSON Contract（Overview 形状）。"""
    ctx = compute_context(family_data)
    snap = ctx["snap"]
    ws = ctx["ws"]
    fit = ctx["fit"]
    alloc = ctx["alloc"]
    rfr = ctx["rfr"]

    assets = family_data.get("assets", [])
    liabilities = family_data.get("liabilities", [])
    cashflows = family_data.get("cashflows", [])
    liquid = metrics.liquid_assets(assets)

    decision = build_issues(family_data, ctx)

    return {
        "currency": "CNY",
        "wealth_score": ws["score"],
        "wealth_level": ws["level"],
        "net_worth": snap["net_worth"],
        "total_assets": snap["total_assets"],
        "total_liabilities": snap["total_liabilities"],
        "liquid_assets": liquid,

        "asset_allocation": {
            "classes": alloc["current"],
            "financial_pct": alloc["financial_pct"],
            "concentration": alloc["concentration"],
        },
        "allocation_fitness": fit["score"],
        "allocation_target": fit["target"],

        "cashflow": {
            "income": snap["monthly_income"],
            "expense": snap["monthly_expense"],
            "surplus": snap["monthly_surplus"],
            "savings_rate": snap["savings_rate"],
        },
        "liquidity": {
            "liquid_assets": liquid,
            "emergency_months": snap["emergency_months"],
        },
        "debt": {
            "total_debt": snap["total_liabilities"],
            "monthly_payment": round(
                sum(float(l.get("monthly_payment") or 0) for l in liabilities), 2),
            "dti": metrics.debt_to_income(liabilities, cashflows),
        },

        "protection": _protection(family_data.get("insurance", []), cashflows),

        "goals": build_goals(family_data),
        "retirement": _retirement_block(rfr),

        "issues": decision["issues"],
        "alerts": decision["alerts"],
        "priorities": decision["priorities"],
        "recommendations": decision["recommendations"],
    }


def _protection(insurance: list[dict], cashflows: list[dict]) -> dict:
    """保障块：保险作为风险转移独立呈现，不算投资资产。"""
    total_coverage = sum(float(i.get("coverage") or 0) for i in insurance)
    total_premium = sum(float(i.get("annual_premium") or 0) for i in insurance)
    annual_income = metrics.monthly_income(cashflows) * 12
    ratio = total_coverage / annual_income if annual_income > 0 else None
    return {
        "insurance_count": len(insurance),
        "total_coverage": round(total_coverage, 2),
        "total_premium": round(total_premium, 2),
        "coverage_ratio": round(ratio, 3) if ratio is not None else None,
    }


def _retirement_block(rfr: dict | None) -> dict | None:
    """养老块：RFR/NWC 双指标 + 四象限 + known_limitations。无年龄/支出时为 None。"""
    if rfr is None:
        return None
    fr = rfr["funding_ratio"]
    nwc = rfr["net_worth_coverage"]
    return {
        "rfr": fr,
        "nwc": nwc,
        "quadrant": retirement_quadrant(fr, nwc),
        "investable_at_retirement": rfr["investable_at_retirement"],
        "net_worth_at_retirement": rfr["net_worth_at_retirement"],
        "retirement_need_pv": rfr["retirement_need_pv"],
        "known_limitations": KNOWN_LIMITATIONS["retirement"],
    }
