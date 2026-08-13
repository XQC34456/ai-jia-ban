"""Wealth Engine · Family Wealth Score：七维度加权财富评分。

每个分项都必须可解释、可追溯——每维返回 score（0-100）+ reasons（文本理由），
权重集中定义在 WEIGHTS，总分 = Σ(维度分 × 权重)。
"""
from __future__ import annotations

from typing import Any

from . import allocation, metrics

__all__ = ["WEIGHTS", "wealth_score"]

WEIGHTS = {
    "cashflow": 0.20,    # 现金流 / 储蓄率
    "liquidity": 0.15,   # 流动性 / 应急月数
    "debt": 0.15,        # 负债压力 / DTI
    "protection": 0.15,  # 保障 / 保险覆盖
    "allocation": 0.15,  # 配置 / 集中度
    "goals": 0.10,       # 目标可行性
    "retirement": 0.10,  # 养老准备
}


def wealth_score(family_data: dict[str, Any], profile: dict | None = None) -> dict[str, Any]:
    dims = [
        _cashflow_dim(family_data), _liquidity_dim(family_data), _debt_dim(family_data),
        _protection_dim(family_data), _allocation_dim(family_data), _goals_dim(family_data),
        _retirement_dim(family_data),
    ]
    total = sum(d["score"] * WEIGHTS[d["name"]] for d in dims)
    score_val = round(max(0.0, min(100.0, total)))
    level = "稳健" if score_val >= 75 else ("需关注" if score_val >= 50 else "脆弱")
    for d in dims:
        d["weight"] = WEIGHTS[d["name"]]
    return {"score": score_val, "level": level, "dimensions": dims}


def _cashflow_dim(family_data):
    sr = metrics.savings_rate(family_data.get("cashflows", []),
                              family_data.get("liabilities", []))
    if sr is None:
        return {"name": "cashflow", "score": 40, "reasons": ["尚未记录收入，无法评估现金流"]}
    if sr >= 0.2:
        score = 100
    elif sr >= 0:
        score = 60
    else:
        score = 20
    reasons = [f"储蓄率 {sr*100:.0f}%"]
    if sr < 0.2:
        reasons.append("储蓄率低于 20% 健康线")
    return {"name": "cashflow", "score": score, "reasons": reasons}


def _liquidity_dim(family_data):
    em = metrics.emergency_months(family_data.get("assets", []),
                                  family_data.get("cashflows", []),
                                  family_data.get("liabilities", []))
    if em is None:
        return {"name": "liquidity", "score": 40, "reasons": ["尚未记录支出，无法评估应急能力"]}
    if em >= 6:
        score = 100
    elif em >= 3:
        score = 70
    elif em > 0:
        score = 40
    else:
        score = 10
    reasons = [f"应急资金覆盖 {em:.1f} 个月"]
    if em < 6:
        reasons.append("建议补足 6 个月生活开支的应急金")
    return {"name": "liquidity", "score": score, "reasons": reasons}


def _debt_dim(family_data):
    liabilities = family_data.get("liabilities", [])
    if not liabilities:
        return {"name": "debt", "score": 100, "reasons": ["无负债，无还款压力"]}
    dti = metrics.debt_to_income(liabilities, family_data.get("cashflows", []))
    if dti is None:
        return {"name": "debt", "score": 40, "reasons": ["有负债但尚未记录收入，无法评估压力"]}
    if dti <= 0.3:
        score = 100
    elif dti <= 0.5:
        score = 60
    else:
        score = 20
    reasons = [f"月供占收入 {dti*100:.0f}%"]
    if dti > 0.3:
        reasons.append("负债压力偏高，建议控制在 30% 以内")
    return {"name": "debt", "score": score, "reasons": reasons}


def _protection_dim(family_data):
    """保障维度：保险作为「风险转移」独立评估，只读 insurance 表，不当作投资资产。"""
    insurances = family_data.get("insurance", [])
    if not insurances:
        return {"name": "protection", "score": 10,
                "reasons": ["未配置任何保险，家庭风险敞口完全裸露"]}
    total_coverage = sum(float(i.get("coverage") or 0) for i in insurances)
    total_premium = sum(float(i.get("annual_premium") or 0) for i in insurances)
    annual_income = metrics.monthly_income(family_data.get("cashflows", [])) * 12
    reasons = [f"配置 {len(insurances)} 份保险，总保额 {total_coverage:,.0f} 元，年保费 {total_premium:,.0f} 元"]
    if annual_income > 0:
        ratio = total_coverage / (annual_income * 5)  # 保额达到 5 倍年收入 = 满分
        score = min(100.0, ratio * 100)
        if ratio < 1:
            reasons.append(f"保额约为年收入的 {ratio*5:.1f} 倍，建议达到 5 倍以上")
    else:
        score = 60.0
        reasons.append("已配置保险，但尚未记录收入，无法评估保额充足性")
    return {"name": "protection", "score": round(score), "reasons": reasons}


def _allocation_dim(family_data):
    assets = family_data.get("assets", [])
    if not assets:
        return {"name": "allocation", "score": 40, "reasons": ["尚未记录资产，无法评估配置"]}
    c = allocation.concentration(assets)
    if c["real_estate_pct"] > 0.7:
        score = 30
        reasons = [f"房产占 {c['real_estate_pct']*100:.0f}%，资产过度集中于房产"]
    elif c["hhi"] > 0.5:
        score = 50
        reasons = [f"资产集中度 HHI={c['hhi']:.2f}，分散不足"]
    else:
        score = 85
        reasons = ["资产大类相对分散"]
    return {"name": "allocation", "score": score, "reasons": reasons}


def _goals_dim(family_data):
    goals = family_data.get("goals", [])
    if not goals:
        return {"name": "goals", "score": 60, "reasons": ["尚未设定理财目标"]}
    surplus = metrics.monthly_surplus(family_data.get("cashflows", []),
                                      family_data.get("liabilities", []))
    funding = metrics.goals_funding(goals, surplus)
    if funding["feasible"]:
        score = 90
        reasons = ["各目标月度定存合计在当前结余能力内"]
    else:
        score = 40
        reasons = [f"目标每月需存 {funding['total_monthly_needed']:,.0f} 元，"
                   f"超出月结余 {funding['monthly_surplus']:,.0f} 元"]
    return {"name": "goals", "score": score, "reasons": reasons}


def _retirement_dim(family_data):
    """养老准备：按 4% 法则（净资产达到 25 倍年支出为财务自由）评估。"""
    nw = metrics.net_worth(family_data.get("assets", []), family_data.get("liabilities", []))
    annual_exp = metrics.monthly_expense(family_data.get("cashflows", []),
                                         family_data.get("liabilities", [])) * 12
    if annual_exp <= 0:
        return {"name": "retirement", "score": 40, "reasons": ["尚未记录支出，无法评估养老准备"]}
    ratio = nw / (annual_exp * 25)
    score = min(100.0, ratio * 100)
    reasons = [f"按 4% 法则，净资产约为年支出的 {ratio*25:.1f} 倍（目标 25 倍）"]
    if ratio < 1:
        reasons.append("距 25 倍年支出的养老目标仍有差距")
    return {"name": "retirement", "score": round(score), "reasons": reasons}
