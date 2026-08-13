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


# ---------- CHECK_ISSUES / CHECK_GOALS / EXPLAIN_RESULT 取数（P1 修复） ----------
# 问题由 build_issues/build_goals 决定，本层只读字段映射成 MetricRef，绝不编数字。

_ISSUE_METRIC_LABELS = {
    "emergency_months": "应急资金（月）",
    "dti": "负债率 DTI",
    "savings_rate": "储蓄率",
    "monthly_surplus": "月结余",
    "monthly_income": "月收入",
    "monthly_expense": "月支出",
    "total_debt": "总负债",
    "max_interest_rate": "最高利率",
    "allocation_fitness": "配置适配度",
    "real_estate_pct": "房产占比",
    "deviation": "配置偏离",
    "rfr": "养老 RFR",
    "nwc": "养老 NWC",
    "gap": "目标缺口",
    "monthly_needed": "每月需存",
    "shortfall": "资金缺口",
    "total_monthly_needed": "每月需存合计",
}
_ISSUE_METRIC_UNITS = {
    "dti": "pct", "savings_rate": "pct", "max_interest_rate": "pct",
    "real_estate_pct": "pct", "rfr": "ratio", "nwc": "ratio",
    "emergency_months": "months", "allocation_fitness": "score",
}


def _issue_metrics(result: dict) -> list[MetricRef]:
    """从 build_issues 的 issues[].metric 确定性取数；非数值（goal 名 / deviation dict）跳过。"""
    out: list[MetricRef] = []
    for i in (result.get("issues") or []):
        iid = i.get("issue_id") or i.get("type")
        for k, v in (i.get("metric") or {}).items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            out.append(MetricRef(
                key=f"{iid}_{k}", label=_ISSUE_METRIC_LABELS.get(k, k),
                unit=_ISSUE_METRIC_UNITS.get(k, "money"), value=v,
                source=f"issues.{iid}.metric.{k}"))
    return out


def _goal_metrics(result: dict) -> list[MetricRef]:
    """从 build_goals 的 goals[] 确定性取数（gap / coverage）。"""
    out: list[MetricRef] = []
    for g in (result.get("goals") or []):
        gid = g.get("goal_id") or g.get("name")
        if g.get("gap") is not None:
            out.append(MetricRef(key=f"goal_{gid}_gap", label="目标缺口", unit="money",
                                 value=g["gap"], source=f"goals.{gid}.gap"))
        if g.get("coverage") is not None:
            out.append(MetricRef(key=f"goal_{gid}_coverage", label="目标覆盖率", unit="pct",
                                 value=g["coverage"], source=f"goals.{gid}.coverage"))
    return out


def _context_metrics(result: dict) -> list[MetricRef]:
    """EXPLAIN_RESULT：context 若带 metrics 则原样重放（逐字，不增删改）。"""
    raw = result.get("metrics") if isinstance(result, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[MetricRef] = []
    for m in raw:
        if isinstance(m, MetricRef):
            out.append(m)
        elif isinstance(m, dict) and m.get("value") is not None:
            try:
                out.append(MetricRef(**m))
            except Exception:
                continue
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
    if intent == "CHECK_ISSUES":
        return _issue_metrics(result)
    if intent == "CHECK_GOALS":
        return _goal_metrics(result)
    if intent == "EXPLAIN_RESULT":
        return _context_metrics(result)
    return []


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
    """组装 AgentResponse：metrics 来自取数（value→source），limitations 逐字透传。

    finding/recommendations 未显式传入时，从 result 确定性推导（问题由 build_issues
    决定，本层只读字段，绝不编数字）。
    """
    metrics = build_metrics(intent, result)
    if finding is None and result:
        finding = _derive_finding(intent, result)
    if recommendations is None and result:
        recommendations = _derive_recommendations(intent, result)
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


def _derive_finding(intent: str, result: dict) -> str | None:
    """从结构化结果确定性推导 finding（只读字段，不编数字）。"""
    if intent == "CHECK_ISSUES":
        issues = result.get("issues") or []
        if not issues:
            return "暂未发现需要关注的财富问题。"
        return "；".join(f"{i['title']}：{i['finding']}" for i in issues[:3])
    if intent == "CHECK_GOALS":
        goals = result.get("goals") or []
        gapped = [g for g in goals if (g.get("gap") or 0) > 0]
        if not goals:
            return "尚未设置家庭目标。"
        if not gapped:
            return f"共 {len(goals)} 个目标，暂未发现资金缺口。"
        biggest = max(gapped, key=lambda g: g["gap"] or 0)
        return (f"共 {len(goals)} 个目标，其中 {len(gapped)} 个存在资金缺口，"
                f"最大缺口是「{biggest['name']}」{biggest['gap']:,.0f} 元。")
    if intent == "EXPLAIN_RESULT":
        return result.get("finding")
    return None


def _derive_recommendations(intent: str, result: dict) -> list[str]:
    """从结构化结果确定性推导 recommendations（只读字段，不编数字）。"""
    if intent == "CHECK_ISSUES":
        out = []
        for r in (result.get("recommendations") or [])[:3]:
            out.append(f"{r.get('action')}：{r.get('detail')}".strip("："))
        return [s for s in out if s]
    if intent == "CHECK_GOALS":
        out = []
        for g in (result.get("goals") or []):
            gap = g.get("gap") or 0
            if gap <= 0:
                continue
            saved = g.get("current_saved") or 0
            target = g.get("target_amount") or 0
            line = f"「{g['name']}」：已备 {saved:,.0f} / {target:,.0f} 元，缺口 {gap:,.0f} 元"
            mn = g.get("monthly_needed")
            if mn:
                line += f"，每月需存 {mn:,.0f} 元"
            out.append(line)
        return out[:3]
    if intent == "EXPLAIN_RESULT":
        return result.get("recommendations") or []
    return []
