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

# 现金流「固定/弹性」分类关键字（纯展示分类，不改变任何金额，非财富计算）。
_FIXED_KEYWORDS = ("贷", "租", "物业", "保险", "学费", "教育", "社保", "养老",
                   "水电", "燃气", "通信", "话费", "宽带", "月供")


def _expense_kind(category: str) -> str:
    """支出分类：固定/弹性。关键字映射的展示口径，非财务事实。"""
    return "fixed" if any(k in (category or "") for k in _FIXED_KEYWORDS) else "elastic"


def _cashflow_breakdown(cashflows: list[dict]) -> dict:
    """现金流明细：按 category 分组 + 年→月归一化（复用 Engine metrics._monthly 口径）。

    只做「分组 + 归一化 + 展示分类」，金额零新增、零改写，数字仍来自 Engine 口径。
    """
    incomes: dict[str, float] = {}
    expenses: dict[str, float] = {}
    for c in cashflows:
        amt = metrics._monthly(float(c.get("amount") or 0), c.get("period", "月"))
        cat = c.get("category") or "其他"
        bucket = incomes if c.get("flow_type") == "income" else expenses
        bucket[cat] = bucket.get(cat, 0) + amt
    exp_list = [{"category": k, "amount": round(v, 2), "kind": _expense_kind(k)}
                for k, v in expenses.items()]
    return {
        "incomes": [{"category": k, "amount": round(v, 2)} for k, v in incomes.items()],
        "expenses": exp_list,
        # 固定/弹性总额在后端算好，前端只读、不自行求和。
        "fixed_total": round(sum(x["amount"] for x in exp_list if x["kind"] == "fixed"), 2),
        "elastic_total": round(sum(x["amount"] for x in exp_list if x["kind"] == "elastic"), 2),
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
        "dimensions": ws["dimensions"],
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
            "breakdown": _cashflow_breakdown(cashflows),
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
            "items": [
                {"type": l.get("type"), "name": l.get("name"),
                 "principal": float(l.get("principal") or 0),
                 "monthly_payment": float(l.get("monthly_payment") or 0),
                 "interest_rate": l.get("interest_rate"),
                 "remaining_months": l.get("remaining_months")}
                for l in liabilities
            ],
        },

        "protection": _protection(family_data.get("insurance", []), cashflows,
                                  family_data.get("persons", [])),

        "goals": build_goals(family_data),
        "retirement": _retirement_block(rfr),

        "issues": decision["issues"],
        "alerts": decision["alerts"],
        "priorities": decision["priorities"],
        "recommendations": decision["recommendations"],
    }


def _protection(insurance: list[dict], cashflows: list[dict], persons: list[dict]) -> dict:
    """保障块：保险作为风险转移独立呈现，不算投资资产。members 按成员归组（join person）。"""
    total_coverage = sum(float(i.get("coverage") or 0) for i in insurance)
    total_premium = sum(float(i.get("annual_premium") or 0) for i in insurance)
    annual_income = metrics.monthly_income(cashflows) * 12
    ratio = total_coverage / annual_income if annual_income > 0 else None

    by_person: dict[int | None, dict] = {}
    for i in insurance:
        pid = i.get("person_id")
        g = by_person.setdefault(pid, {"coverage": 0.0, "premium": 0.0, "count": 0})
        g["coverage"] += float(i.get("coverage") or 0)
        g["premium"] += float(i.get("annual_premium") or 0)
        g["count"] += 1
    person_map = {p.get("id"): p for p in persons if p.get("id") is not None}
    members = []
    for pid, v in by_person.items():
        p = person_map.get(pid)
        members.append({
            "name": (p.get("name") if p else None) or "家庭/未指定",
            "relation": (p.get("relation") if p else None) or "",
            "coverage": round(v["coverage"], 2),
            "premium": round(v["premium"], 2),
            "policy_count": v["count"],
        })
    return {
        "insurance_count": len(insurance),
        "total_coverage": round(total_coverage, 2),
        "total_premium": round(total_premium, 2),
        "coverage_ratio": round(ratio, 3) if ratio is not None else None,
        "members": members,
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
