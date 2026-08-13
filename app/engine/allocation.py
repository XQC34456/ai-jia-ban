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
    "allocation_policy", "analyze",
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
