"""Wealth Engine · 资产配置分析：大类占比 / 集中度 / 目标区间 Policy / 偏离与调整。

Asset Class 采用可配置映射（ASSET_CLASS_MAP），目标区间采用 Policy 数据结构，
B 端可注入覆盖，绝不硬编码比例。
"""
from __future__ import annotations

from typing import Any

from . import metrics

__all__ = [
    "ASSET_CLASSES", "ASSET_CLASS_MAP", "DEFAULT_POLICY",
    "classify_asset", "asset_class_breakdown", "concentration",
    "allocation_policy", "personalized_policy", "allocation_fitness", "analyze",
]

# 六大资产大类（可扩展枚举）
ASSET_CLASSES = ("cash", "fixed_income", "equity", "real_estate", "alternative", "other")

# 资产类型 → 大类映射（可配置；记录上的 asset_class 字段优先，此表作兜底回填）
ASSET_CLASS_MAP = {
    "房产": "real_estate", "存款": "cash", "现金": "cash", "活期": "cash",
    "货币基金": "cash", "理财": "fixed_income", "基金": "fixed_income",
    "债券": "fixed_income", "股票": "equity", "保险现金价值": "other", "其他": "other",
}

# 默认目标配置区间（Policy 数据结构，B 端可注入覆盖；只覆盖可配置的金融资产，
# 房产/另类通过 concentration 单独评估，不给硬编码区间）
DEFAULT_POLICY = {
    "conservative": {"cash": [0.10, 0.20], "fixed_income": [0.35, 0.55], "equity": [0.05, 0.20]},
    "balanced":     {"cash": [0.05, 0.15], "fixed_income": [0.20, 0.40], "equity": [0.20, 0.45]},
    "aggressive":   {"cash": [0.02, 0.10], "fixed_income": [0.10, 0.30], "equity": [0.40, 0.70]},
}


def classify_asset(asset_type: str) -> str:
    """按资产类型映射大类（未知类型归 other）。"""
    return ASSET_CLASS_MAP.get(asset_type, "other")


def _asset_class_of(asset: dict[str, Any]) -> str:
    """优先用记录上的 asset_class 字段，缺失时按 type 映射兜底。"""
    cls = asset.get("asset_class")
    if cls:
        return cls
    return classify_asset(asset.get("type"))


def asset_class_breakdown(assets: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """按大类聚合资产金额与占比。"""
    total = sum(float(a.get("value") or 0) for a in assets)
    out = {k: {"value": 0.0, "pct": 0.0} for k in ASSET_CLASSES}
    for a in assets:
        cls = _asset_class_of(a)
        if cls not in out:
            cls = "other"
        out[cls]["value"] += float(a.get("value") or 0)
    if total > 0:
        for k in out:
            out[k]["pct"] = round(out[k]["value"] / total, 4)
    return out


def concentration(assets: list[dict[str, Any]]) -> dict[str, float]:
    """集中度：HHI / 最大单项占比 / 房产占比 / 单只股票占比。"""
    vals = sorted((float(a.get("value") or 0) for a in assets), reverse=True)
    total = sum(vals)
    if total <= 0:
        return {"hhi": 0.0, "top_asset_pct": 0.0, "real_estate_pct": 0.0, "single_stock_pct": 0.0}
    hhi = sum((v / total) ** 2 for v in vals)
    real_estate = sum(float(a.get("value") or 0) for a in assets if _asset_class_of(a) == "real_estate")
    single_stock = sum(float(a.get("value") or 0) for a in assets if a.get("type") == "股票")
    return {
        "hhi": round(hhi, 4),
        "top_asset_pct": round(vals[0] / total, 4),
        "real_estate_pct": round(real_estate / total, 4),
        "single_stock_pct": round(single_stock / total, 4),
    }


def allocation_policy(risk_profile: str, time_horizon: int, policy: dict | None = None) -> dict:
    """目标配置区间：由风险画像 + 期限动态决定（Policy 可注入，非硬编码）。"""
    source = policy or DEFAULT_POLICY
    base = source.get(risk_profile, source.get("balanced", {}))
    # 期限修正：越短越偏保守，越长越偏进取
    adj = -0.10 if time_horizon <= 3 else (0.10 if time_horizon > 7 else 0.0)
    return {k: [max(0.0, lo + adj), min(1.0, hi + adj)] for k, (lo, hi) in base.items()}


def _deviation(current: dict, target: dict) -> dict[str, str]:
    out = {}
    for cls, (lo, hi) in target.items():
        pct = current.get(cls, {}).get("pct", 0.0)
        out[cls] = "below" if pct < lo else ("above" if pct > hi else "in_range")
    return out


def _adjustments(current: dict, target: dict) -> list[dict[str, Any]]:
    adv = []
    for cls, (lo, hi) in target.items():
        pct = current.get(cls, {}).get("pct", 0.0)
        if pct < lo:
            adv.append({"asset_class": cls, "action": "增配", "current_pct": pct,
                        "target_low": lo, "gap_pct": round(lo - pct, 4)})
        elif pct > hi:
            adv.append({"asset_class": cls, "action": "减配", "current_pct": pct,
                        "target_high": hi, "gap_pct": round(pct - hi, 4)})
    adv.sort(key=lambda x: x["gap_pct"], reverse=True)
    return adv


def _liquidity(assets, cashflows, liabilities):
    liq = sum(float(a.get("value") or 0) for a in assets if _asset_class_of(a) == "cash")
    total = sum(float(a.get("value") or 0) for a in assets)
    em = None
    if cashflows is not None:
        exp = metrics.monthly_expense(cashflows, liabilities)
        em = round(liq / exp, 1) if exp > 0 else None
    return {
        "liquid_amount": round(liq, 2),
        "liquid_pct": round(liq / total, 4) if total > 0 else 0.0,
        "emergency_months": em,
    }


def analyze(assets, profile=None, cashflows=None, liabilities=None) -> dict:
    """资产配置综合分析（设计 G1 的输出结构）。"""
    profile = profile or {}
    current = asset_class_breakdown(assets)
    risk_profile = profile.get("risk_profile", "balanced")
    horizon = profile.get("investment_horizon", 10)
    target = allocation_policy(risk_profile, horizon)
    return {
        "current": current,
        "concentration": concentration(assets),
        "liquidity": _liquidity(assets, cashflows, liabilities),
        "target_range": target,
        "deviation": _deviation(current, target),
        "adjustments": _adjustments(current, target),
    }


def personalized_policy(profile=None, goals=None, liabilities=None, cashflows=None, policy=None) -> dict:
    """家庭专属目标配置区间：基础 Policy + 目标期限/负债修正。

    房产/另类不进入区间（由 concentration 单独评估），只对可配置的
    金融资产（cash/fixed_income/equity）做个性化调整。
    """
    profile = profile or {}
    target = allocation_policy(profile.get("risk_profile", "balanced"),
                               profile.get("investment_horizon", 10), policy)
    target = {k: list(v) for k, v in target.items()}
    reasons = []
    if _has_short_term_goal(goals):
        target["cash"][0] = max(0.0, target["cash"][0] + 0.05)
        target["equity"][1] = max(0.0, target["equity"][1] - 0.10)
        reasons.append("存在 3 年内用款目标，提高现金下限、压降权益上限")
    dti = metrics.debt_to_income(liabilities or [], cashflows or [])
    if dti is not None and dti > 0.5:
        target["equity"][1] = max(0.0, target["equity"][1] - 0.10)
        reasons.append("负债压力偏高（DTI>50%），压降权益上限")
    return {"target": target, "reasons": reasons}


def _has_short_term_goal(goals) -> bool:
    """是否存在 3 年内需要用款的目标（lump_sum 看 target_date，cashflow 看 start_year）。"""
    from datetime import date as _date
    today = _date.today()
    for g in goals or []:
        if g.get("goal_kind") == "cashflow":
            if 0 <= int(g.get("start_year") or 0) <= 3:
                return True
        elif g.get("target_date"):
            months = metrics._months_until(g["target_date"], today)
            if months is not None and 0 < months <= 36:
                return True
    return False


def allocation_fitness(assets, profile=None, cashflows=None, liabilities=None, goals=None) -> dict:
    """Allocation Fitness Score：目标约束下的配置适配度（100 分制，可解释）。

    Fitness = 100 - 偏离惩罚(≤40) - 集中度惩罚(≤30) - 流动性惩罚(≤30)。
    每项有明确公式与 reasons，评分可逐项追溯，不是黑箱。
    """
    current = asset_class_breakdown(assets)
    pol = personalized_policy(profile, goals, liabilities, cashflows)
    target = pol["target"]
    reasons = list(pol["reasons"])

    # 1. 偏离惩罚：金融资产相对目标区间，每偏离 1% 扣 1 分（上限 40）
    deviation_penalty = 0.0
    for cls in ("cash", "fixed_income", "equity"):
        pct = current[cls]["pct"]
        lo, hi = target[cls]
        if pct < lo:
            deviation_penalty += (lo - pct) * 100
            reasons.append(f"{cls} 占比 {pct*100:.0f}% 低于目标下限 {lo*100:.0f}%")
        elif pct > hi:
            deviation_penalty += (pct - hi) * 100
            reasons.append(f"{cls} 占比 {pct*100:.0f}% 高于目标上限 {hi*100:.0f}%")
    deviation_penalty = min(deviation_penalty, 40.0)

    # 2. 集中度惩罚：房产/股票/未分类资产过重（上限 30）
    conc = concentration(assets)
    conc_penalty = 0.0
    if conc["real_estate_pct"] > 0.5:
        conc_penalty += (conc["real_estate_pct"] - 0.5) * 100
        reasons.append(f"房产占 {conc['real_estate_pct']*100:.0f}%，超出 50% 合理上限")
    if conc["single_stock_pct"] > 0.2:
        conc_penalty += (conc["single_stock_pct"] - 0.2) * 50
        reasons.append(f"股票占 {conc['single_stock_pct']*100:.0f}%，超过 20% 分散上限")
    if current["other"]["pct"] > 0.2:
        conc_penalty += (current["other"]["pct"] - 0.2) * 100
        reasons.append(f"其他/未分类资产占 {current['other']['pct']*100:.0f}%，配置不透明")
    conc_penalty = min(conc_penalty, 30.0)

    # 3. 流动性惩罚：应急金不足（上限 30）
    liq = _liquidity(assets, cashflows, liabilities)
    liq_penalty = 0.0
    em = liq["emergency_months"]
    if em is not None and em < 6:
        liq_penalty = min((6 - em) * 5, 30.0)
        reasons.append(f"应急资金仅 {em:.1f} 个月，低于 6 个月安全线")

    score = max(0.0, min(100.0, 100.0 - deviation_penalty - conc_penalty - liq_penalty))
    return {
        "score": round(score),
        "target": target,
        "current": current,
        "deviation": _deviation(current, target),
        "concentration": conc,
        "liquidity": liq,
        "penalties": {
            "deviation": round(deviation_penalty, 1),
            "concentration": round(conc_penalty, 1),
            "liquidity": round(liq_penalty, 1),
        },
        "reasons": reasons,
    }
