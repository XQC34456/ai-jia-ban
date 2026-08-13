"""A3 Response 组装：从工具返回确定性取数 → AgentResponse。

铁律（A3.1 冻结）：
- metric value 必带 source 字段路径（MetricRef 硬闸，防编造）
- 只做「字段读取」，绝不计算、绝不 round、绝不自行产出数字
- known_limitations 逐字透传，不增删改
"""
from __future__ import annotations

from ..schemas.agent import AgentResponse, MetricRef

__all__ = ["build_metrics", "known_limitations_of", "build_response"]

# (key, 中文名, unit, source 字段路径, 取值器)
_OVERVIEW_SPECS = (
    ("wealth_score", "财富评分", "score", "overview.wealth_score",
     lambda o: o.get("wealth_score")),
    ("net_worth", "净资产", "money", "overview.net_worth",
     lambda o: o.get("net_worth")),
    ("cashflow_surplus", "月度现金流结余", "money", "overview.cashflow.surplus",
     lambda o: (o.get("cashflow") or {}).get("surplus")),
    ("dti", "负债率 DTI", "pct", "overview.debt.dti",
     lambda o: (o.get("debt") or {}).get("dti")),
    ("liquidity_months", "应急资金（月）", "months", "overview.liquidity.emergency_months",
     lambda o: (o.get("liquidity") or {}).get("emergency_months")),
)

_RETIREMENT_SPECS = (
    ("rfr", "养老可投资覆盖 RFR", "ratio", "overview.retirement.rfr",
     lambda r: r.get("rfr")),
    ("nwc", "养老净资产覆盖 NWC", "ratio", "overview.retirement.nwc",
     lambda r: r.get("nwc")),
)

_ALLOCATION_CLASSES = ("cash", "fixed_income", "equity", "real_estate", "alternative", "other")
_ALLOCATION_LABELS = {
    "cash": "现金", "fixed_income": "固收", "equity": "权益",
    "real_estate": "房产", "alternative": "另类", "other": "其他",
}


def _mk(specs, target) -> list[MetricRef]:
    out = []
    for key, label, unit, source, get in specs:
        v = get(target)
        if v is not None:
            out.append(MetricRef(key=key, label=label, unit=unit, value=v, source=source))
    return out


def _allocation_metrics(o: dict) -> list[MetricRef]:
    classes = ((o.get("asset_allocation") or {}).get("classes")) or {}
    out = []
    for cls in _ALLOCATION_CLASSES:
        pct = (classes.get(cls) or {}).get("pct")
        if pct is not None:
            out.append(MetricRef(key=f"{cls}_pct", label=f"{_ALLOCATION_LABELS[cls]}占比",
                                 unit="pct", value=pct,
                                 source=f"overview.asset_allocation.classes.{cls}.pct"))
    return out


def _compare_metrics(result: dict) -> list[MetricRef]:
    """九指标对比表逐行透传：delta（变化量）优先，否则 option；两者都无 → value=None。"""
    rows = ((result.get("comparison") or {}).get("A")) or []
    out = []
    for row in rows:
        delta = row.get("delta")
        option = row.get("option")
        if delta is not None:
            out.append(MetricRef(key=row["key"], label=row["label"], unit=row["unit"],
                                 value=delta, source=f"comparison.A.{row['key']}.delta"))
        elif option is not None:
            out.append(MetricRef(key=row["key"], label=row["label"], unit=row["unit"],
                                 value=option, source=f"comparison.A.{row['key']}.option"))
        else:
            out.append(MetricRef(key=row["key"], label=row["label"], unit=row["unit"]))
    return out


def build_metrics(intent: str, result: dict | None) -> list[MetricRef]:
    """按意图从工具返回确定性取数；value→source 封闭。"""
    if result is None:
        return []
    if intent == "VIEW_OVERVIEW":
        return _mk(_OVERVIEW_SPECS, result)
    if intent == "CHECK_RETIREMENT":
        return _mk(_RETIREMENT_SPECS, result.get("retirement") or {})
    if intent == "CHECK_ALLOCATION":
        return _allocation_metrics(result)
    if intent == "SCENARIO_COMPARE":
        return _compare_metrics(result)
    return []   # CHECK_ISSUES / CHECK_GOALS / EXPLAIN_RESULT 不产出数值指标


def known_limitations_of(result: dict | None) -> list[str]:
    """逐字透传 known_limitations（不增删改）。CompareResponse 读 baseline.retirement。"""
    if not result:
        return []
    base = result.get("baseline", result)
    return ((base.get("retirement") or {}).get("known_limitations")) or []


def build_response(intent: str, status: str, result: dict | None = None,
                   summary: str = "", finding: str | None = None,
                   next_actions: list[str] | None = None,
                   recommendations: list[str] | None = None) -> AgentResponse:
    """组装 AgentResponse：metrics 来自取数（value→source），limitations 逐字透传。"""
    metrics = build_metrics(intent, result)
    return AgentResponse(
        intent=intent,
        status=status,
        summary=summary,
        finding=finding,
        metrics=metrics,
        recommendations=recommendations or [],
        next_actions=next_actions or [],
        limitations=known_limitations_of(result),
        source=[m.source for m in metrics if m.source],
    )
