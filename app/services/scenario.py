"""Wealth Service · 情景对比编排：baseline + 多方案完整 Overview（C3）。

铁律：本层只做「编排」——baseline = build_overview(data)，每个 option =
build_overview(apply_scenario(data, name, params))。comparison 只是对两个
Overview 做「选字段 + 减法」的展示辅助，绝不新增任何财富计算。
"""
from __future__ import annotations

from app.engine import scenario
from app.schemas.scenario import SCENARIO_METRICS
from app.services.overview import build_overview

__all__ = ["compare_scenarios"]


def _avg_goal_coverage(o: dict) -> float | None:
    """目标完成度（展示辅助）：对 build_goals 已返回的 coverage 取平均，不重算。"""
    goals = o.get("goals") or []
    if not goals:
        return None
    cov = [float(g.get("coverage") or 0) for g in goals]
    return round(sum(cov) / len(cov), 4)


# 9 个固定对比维度的取值器（纯字段读取，无计算）。
# 键 / 中文名 / 单位 / 顺序 的单一事实来源在 schemas.SCENARIO_METRICS（契约冻结），
# 这里只负责「从 Overview 取哪个字段」，绝不新增财富公式。
_EXTRACTORS = {
    "net_worth": lambda o: o.get("net_worth"),
    "wealth_score": lambda o: o.get("wealth_score"),
    "rfr": lambda o: (o.get("retirement") or {}).get("rfr"),
    "nwc": lambda o: (o.get("retirement") or {}).get("nwc"),
    "cashflow": lambda o: (o.get("cashflow") or {}).get("surplus"),
    "liquidity": lambda o: (o.get("liquidity") or {}).get("emergency_months"),
    "dti": lambda o: (o.get("debt") or {}).get("dti"),
    "real_estate_pct": lambda o: ((o.get("asset_allocation") or {}).get("classes") or {}).get("real_estate", {}).get("pct"),
    "goal_completion": _avg_goal_coverage,
}


def _diff(baseline: dict, option: dict) -> list[dict]:
    """展示辅助：对两个 Overview 做字段选取 + 减法，产出 Δ（不重算任何财富指标）。"""
    rows = []
    for key, label, unit in SCENARIO_METRICS:
        extract = _EXTRACTORS[key]
        a = extract(baseline)
        b = extract(option)
        delta = round(b - a, 4) if (a is not None and b is not None) else None
        rows.append({"key": key, "label": label, "unit": unit,
                     "baseline": a, "option": b, "delta": delta})
    return rows


def compare_scenarios(data: dict, name: str, options: list[dict]) -> dict:
    """编排 baseline + 多方案完整 Overview。

    每个 option 都从同一份 baseline data 独立 apply（apply_scenario 内部深拷贝），
    绝不链式 apply。comparison 为每 option 一份展示差值。
    """
    baseline = build_overview(data)
    results = []
    comparison = {}
    for opt in options:
        modified = scenario.apply_scenario(data, name, opt.get("params") or {})
        overview = build_overview(modified)
        oid = opt.get("id")
        results.append({"id": oid, "name": opt.get("name") or oid, "overview": overview})
        comparison[oid] = _diff(baseline, overview)
    return {"scenario": name, "baseline": baseline, "options": results, "comparison": comparison}
