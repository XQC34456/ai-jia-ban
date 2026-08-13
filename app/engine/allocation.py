"""Wealth Engine · 资产配置分析：大类占比 / 集中度 / 目标 Policy / 偏离与调整。

核心原则：
- 目标配置只覆盖「可配置金融资产」cash / fixed_income / equity 三个大类；
  房产 / 另类 / 其他不进入目标区间，通过 concentration 与 liquidity 单独评估。
- 每个风险画像的区间必须「可行」（Σ 下限 ≤ 100% ≤ Σ 上限），并能归一化出
  一个 Σ = 100% 的点目标（point target），保证 Policy 在数学上完整。
- 期限修正只在 equity 与 fixed_income 之间转移（不碰 cash），绝不破坏 Σ。
"""
from __future__ import annotations

from typing import Any

from . import metrics

__all__ = [
    "ASSET_CLASSES", "ASSET_CLASS_MAP", "DEFAULT_POLICY", "FINANCIAL_TARGET_CLASSES",
    "classify_asset", "asset_class_breakdown", "concentration",
    "allocation_policy", "personalized_policy", "allocation_fitness", "analyze",
    "_normalize_target", "_financial_breakdown",
]

# 六大资产大类（可扩展枚举）
ASSET_CLASSES = ("cash", "fixed_income", "equity", "real_estate", "alternative", "other")

# 进入目标区间、参与 Σ=100% 归一化的可配置金融资产
FINANCIAL_TARGET_CLASSES = ("cash", "fixed_income", "equity")

# 资产类型 → 大类映射（可配置；记录上的 asset_class 字段优先，此表作兜底回填）
ASSET_CLASS_MAP = {
    "房产": "real_estate", "存款": "cash", "现金": "cash", "活期": "cash",
    "货币基金": "cash", "理财": "fixed_income", "基金": "fixed_income",
    "债券": "fixed_income", "股票": "equity", "保险现金价值": "other", "其他": "other",
}

# 默认目标配置区间（Policy 数据结构，B 端可注入覆盖）。
# 区间必须可行：Σ 下限 ≤ 1 且 Σ 上限 ≥ 1，才能归一化出 Σ=100% 的点目标。
DEFAULT_POLICY = {
    "conservative": {"cash": [0.20, 0.30], "fixed_income": [0.50, 0.65], "equity": [0.05, 0.20]},
    "balanced":     {"cash": [0.10, 0.20], "fixed_income": [0.40, 0.55], "equity": [0.25, 0.40]},
    "aggressive":   {"cash": [0.03, 0.10], "fixed_income": [0.20, 0.35], "equity": [0.55, 0.75]},
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
    """目标配置区间：由风险画像 + 期限动态决定（Policy 可注入，非硬编码）。

    期限修正只在 equity ↔ fixed_income 之间转移（越短越保守：权益↓固收↑），
    现金区间不动，保证修正后区间仍可行（Σ 不变）。
    """
    source = policy or DEFAULT_POLICY
    base = source.get(risk_profile, source.get("balanced", {}))
    out = {k: [float(lo), float(hi)] for k, (lo, hi) in base.items()}

    if time_horizon <= 3:
        shift = -0.10
    elif time_horizon > 7:
        shift = 0.10
    else:
        shift = 0.0

    if shift and "equity" in out and "fixed_income" in out:
        eq_lo, eq_hi = out["equity"]
        fi_lo, fi_hi = out["fixed_income"]
        out["equity"] = [max(0.0, eq_lo + shift), max(0.0, eq_hi + shift)]
        out["fixed_income"] = [max(0.0, fi_lo - shift), max(0.0, fi_hi - shift)]
    return out


def _normalize_target(ranges: dict) -> dict[str, float]:
    """由可行区间 [lo, hi] 生成 Σ=100% 的点目标，且保证 lo ≤ target ≤ hi。

    统一归一化规则：取区间中点为初值 → 归一化到 100% → 逐项夹紧到区间 →
    夹紧产生的残差在未到边界的项之间按剩余可调空间比例再分配，迭代至收敛。
    区间不可行（Σlo>1 或 Σhi<1）时退化为「按区间宽度加权」的最优逼近。
    """
    keys = [k for k in FINANCIAL_TARGET_CLASSES if k in ranges]
    if not keys:
        return {}
    lo = {k: max(0.0, float(ranges[k][0])) for k in keys}
    hi = {k: min(1.0, float(ranges[k][1])) for k in keys}
    target = {k: (lo[k] + hi[k]) / 2 for k in keys}

    for _ in range(100):
        total = sum(target.values())
        if total <= 0:
            target = {k: 1.0 / len(keys) for k in keys}
            break
        for k in keys:  # 归一化到 100%
            target[k] /= total
        clipped = {k: min(max(target[k], lo[k]), hi[k]) for k in keys}
        residual = 1.0 - sum(clipped.values())
        if abs(residual) < 1e-6:
            target = clipped
            break
        free = [k for k in keys if lo[k] < clipped[k] < hi[k]]
        if not free:
            target = clipped
            break
        if residual > 0:
            slack = sum(hi[k] - clipped[k] for k in free)
        else:
            slack = sum(clipped[k] - lo[k] for k in free)
        if slack <= 0:
            target = clipped
            break
        for k in free:
            if residual > 0:
                target[k] = clipped[k] + residual * (hi[k] - clipped[k]) / slack
            else:
                target[k] = clipped[k] + residual * (clipped[k] - lo[k]) / slack
        for k in keys:
            if k not in free:
                target[k] = clipped[k]

    return {k: round(target[k], 4) for k in keys}


def _financial_breakdown(breakdown: dict[str, dict[str, float]]) -> dict[str, float]:
    """金融资产口径占比：cash/fixed_income/equity 在「金融资产合计」中的占比。

    分母 = cash + fixed_income + equity 的金额（房产/另类/其他不进入分母）。
    """
    denom = sum(breakdown[cls]["value"] for cls in FINANCIAL_TARGET_CLASSES)
    if denom <= 0:
        return {cls: 0.0 for cls in FINANCIAL_TARGET_CLASSES} | {"denom": 0.0}
    out = {cls: round(breakdown[cls]["value"] / denom, 4) for cls in FINANCIAL_TARGET_CLASSES}
    out["denom"] = round(denom, 2)
    return out


def _deviation(financial_pct: dict, target_range: dict) -> dict[str, str]:
    """金融资产口径相对目标区间：below / in_range / above。"""
    out = {}
    for cls in FINANCIAL_TARGET_CLASSES:
        if cls not in target_range:
            continue
        lo, hi = target_range[cls]
        pct = financial_pct.get(cls, 0.0)
        out[cls] = "below" if pct < lo else ("above" if pct > hi else "in_range")
    return out


def _adjustments(financial_pct: dict, target_range: dict) -> list[dict[str, Any]]:
    """金融资产口径的增配/减配建议（相对目标区间）。"""
    adv = []
    for cls in FINANCIAL_TARGET_CLASSES:
        if cls not in target_range:
            continue
        lo, hi = target_range[cls]
        pct = financial_pct.get(cls, 0.0)
        if pct < lo:
            adv.append({"asset_class": cls, "action": "增配", "current_pct": round(pct, 4),
                        "target_low": lo, "gap_pct": round(lo - pct, 4)})
        elif pct > hi:
            adv.append({"asset_class": cls, "action": "减配", "current_pct": round(pct, 4),
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
    """资产配置综合分析（设计 G1 的输出结构）。

    返回：current（6 大类总资产口径）、financial_pct（金融资产口径）、
    concentration、liquidity、target（Σ=100% 点目标）、target_range（区间）、
    deviation（金融口径 vs 区间）、adjustments。
    """
    profile = profile or {}
    current = asset_class_breakdown(assets)
    financial_pct = _financial_breakdown(current)
    risk_profile = profile.get("risk_profile", "balanced")
    horizon = profile.get("investment_horizon", 10)
    target_range = allocation_policy(risk_profile, horizon)
    return {
        "current": current,
        "financial_pct": {k: v for k, v in financial_pct.items() if k != "denom"},
        "financial_denom": financial_pct.get("denom", 0.0),
        "concentration": concentration(assets),
        "liquidity": _liquidity(assets, cashflows, liabilities),
        "target": _normalize_target(target_range),
        "target_range": target_range,
        "deviation": _deviation(financial_pct, target_range),
        "adjustments": _adjustments(financial_pct, target_range),
    }


def personalized_policy(profile=None, goals=None, liabilities=None, cashflows=None, policy=None) -> dict:
    """家庭专属目标配置：基础 Policy + 目标期限/负债修正，输出 Σ=100% 点目标 + 区间。

    房产/另类不进入目标（由 concentration 单独评估），只对可配置金融资产
    （cash/fixed_income/equity）做个性化调整；修正后经 _normalize_target 保证
    数学完整（Σ=100% 且 lo ≤ target ≤ hi）。
    """
    profile = profile or {}
    rng = allocation_policy(profile.get("risk_profile", "balanced"),
                            profile.get("investment_horizon", 10), policy)
    rng = {k: list(v) for k, v in rng.items()}
    reasons = []
    if _has_short_term_goal(goals):
        rng["cash"][0] = min(rng["cash"][0] + 0.05, rng["cash"][1])
        rng["equity"][1] = max(rng["equity"][0], rng["equity"][1] - 0.10)
        reasons.append("存在 3 年内用款目标，提高现金下限、压降权益上限")
    dti = metrics.debt_to_income(liabilities or [], cashflows or [])
    if dti is not None and dti > 0.5:
        rng["equity"][1] = max(rng["equity"][0], rng["equity"][1] - 0.10)
        reasons.append("负债压力偏高（DTI>50%），压降权益上限")
    return {"target": _normalize_target(rng), "range": rng, "reasons": reasons}


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
    偏离惩罚用「金融资产口径占比 vs Σ=100% 点目标」的绝对距离，
    每偏离 1% 扣 1 分；集中度/流动性惩罚保持不变。
    """
    current = asset_class_breakdown(assets)
    financial_pct = _financial_breakdown(current)
    pol = personalized_policy(profile, goals, liabilities, cashflows)
    target = pol["target"]
    target_range = pol["range"]
    reasons = list(pol["reasons"])

    # 1. 偏离惩罚：金融资产占比 vs 点目标（距离 × 100，上限 40）
    deviation_penalty = 0.0
    if financial_pct.get("denom", 0.0) <= 0:
        deviation_penalty = 40.0
        reasons.append("无现金/固收/权益等可配置金融资产，无法形成有效配置")
    else:
        for cls in FINANCIAL_TARGET_CLASSES:
            pct = financial_pct[cls]
            tgt = target.get(cls, 0.0)
            deviation_penalty += abs(pct - tgt) * 100
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
        "target_range": target_range,
        "current": current,
        "financial_pct": {k: v for k, v in financial_pct.items() if k != "denom"},
        "deviation": _deviation(financial_pct, target_range),
        "concentration": conc,
        "liquidity": liq,
        "penalties": {
            "deviation": round(deviation_penalty, 1),
            "concentration": round(conc_penalty, 1),
            "liquidity": round(liq_penalty, 1),
        },
        "reasons": reasons,
    }
