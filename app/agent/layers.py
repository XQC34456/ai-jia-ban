"""V2.6 五层结构化回答契约：把「系统层」与「LLM 叙事层」分离。

铁律：
- 系统层（①结论 ②关键变化 ③财务画像 ⑤下一步行动）全部来自确定性
  overview / review-status，本模块只做「字段搬运 + 图表块选取」，绝不计算财富数字。
- LLM 叙事层（④我的判断）直接复用 AgentResponse.finding（已在组装层数字剥离）。

本模块为纯函数，入口 attach_layers() 在 converse() 里对 AgentResponse 附加 layers，
不改变 Agent 主流程，也不影响 V2.3 之前的扁平字段（只扩不减）。
"""
from __future__ import annotations

from .. import db
from ..schemas.agent import AdvisorLayers, ActionPlanRef, AgentResponse, ChartBlock, FollowUpRef
from ..services import build_overview
from .followup import follow_up_questions
from .memory import INVALIDATION_LABELS

__all__ = ["attach_layers"]

# 图表组件名 → 确定性 overview 子块取数器（零计算，只取已算好的字段）。
def _dimensions(o): return o.get("dimensions")
def _cashflow(o): return o.get("cashflow")
def _allocation(o): return (o.get("asset_allocation") or {}).get("classes")
def _debt(o): return o.get("debt")
def _protection(o): return o.get("protection")
def _goals(o): return o.get("goals")
def _retirement(o): return o.get("retirement")

# 意图 → 触发的证据块（按用户问题触发，不固定 6 张图）：
#   (chart 组件名, 财务问题, overview 取数器)
_INTENT_CHARTS: dict[str, list[tuple[str, str, object]]] = {
    "VIEW_OVERVIEW": [
        ("radar", "我家整体健不健康？哪维最弱？", _dimensions),
        ("cashflow", "钱去哪了？每月能存多少？", _cashflow),
    ],
    "CHECK_ISSUES": [
        ("radar", "我家整体健不健康？哪维最弱？", _dimensions),
    ],
    "CHECK_RETIREMENT": [
        ("retirement", "退休后钱够不够？资产能否覆盖需求？", _retirement),
    ],
    "CHECK_ALLOCATION": [
        ("allocation", "钱放在哪？配置合理吗？", _allocation),
    ],
    "CHECK_GOALS": [
        ("goals", "哪个目标落后？钱够不够？", _goals),
    ],
    "SCENARIO_COMPARE": [],   # 走 _build_scenario_chart（baseline vs 方案证据图），非 overview 画像块
    "EXPLAIN_RESULT": [],     # 纯解释，无端点、无画像
}


def _nonempty(data) -> bool:
    """证据块数据是否非空：None 或空 list/dict 一律不触发图表。"""
    if data is None:
        return False
    if isinstance(data, (list, dict)) and len(data) == 0:
        return False
    return True


def _build_conclusion(overview: dict) -> str | None:
    """① 结论：wealth_level + 财富评分 + 首要矛盾，全部来自确定性 overview。"""
    parts: list[str] = []
    level = overview.get("wealth_level")
    score = overview.get("wealth_score")
    if level:
        s = f"你的家庭财务{level}"
        if score is not None:
            s += f"（财富评分 {score:.0f} 分）"
        parts.append(s)
    priorities = overview.get("priorities") or []
    if priorities:
        title = priorities[0].get("title")
        severity = priorities[0].get("severity")
        if title:
            parts.append(f"当前最需要关注：{title}" + (f"（{severity}）" if severity else ""))
    return "；".join(parts) if parts else None


def _build_changes(invalidation: list[dict] | None) -> list[dict]:
    """② 关键变化：detect_invalidation 的 changed 清单 → 人话标签（数字来自确定性 diff）。"""
    out = []
    for c in invalidation or []:
        key = c.get("key")
        out.append({
            "key": key,
            "label": INVALIDATION_LABELS.get(key, key),
            "before": c.get("before"),
            "after": c.get("after"),
        })
    return out


def _build_charts(intent: str, overview: dict) -> list[ChartBlock]:
    """③ 财务画像证据块：按意图选取，data 为确定性 overview 子块原样搬运。"""
    out = []
    for chart, question, getter in _INTENT_CHARTS.get(intent, []):
        data = getter(overview)
        if _nonempty(data):
            out.append(ChartBlock(chart=chart, question=question, data=data))
    return out


# 情景证据图只取 5 个最扎眼指标（现金流/应急/DTI/净资产/评分），避免一屏 9 组过密。
_SCENARIO_CHART_METRICS = ("cashflow", "liquidity", "dti", "net_worth", "wealth_score")


def _build_scenario_chart(comparison: dict) -> ChartBlock | None:
    """③ 情景证据图：baseline vs 方案的关键指标对比。

    comparison = {"A": [9行 ComparisonMetric(baseline/option/delta)]，...}；单方案取 A，
    只读 baseline/option（对比值由 compare_scenarios 确定性算出），绝不加工财富数字。
    """
    rows = (comparison or {}).get("A") or []
    by_key = {row["key"]: row for row in rows if isinstance(row, dict)}
    series = []
    for key in _SCENARIO_CHART_METRICS:
        row = by_key.get(key)
        if not row:
            continue
        series.append({
            "key": row["key"], "label": row["label"], "unit": row["unit"],
            "baseline": row.get("baseline"), "option": row.get("option"),
        })
    if not series:
        return None
    return ChartBlock(
        chart="scenario_compare",
        question="这个决定会让你家更好还是更差？",
        data={"series": series},
    )


def _build_action_plans(overview: dict) -> list[dict]:
    """⑤ 下一步的可采纳结构：来自 Decision recommendations，逐字透传 action/detail，
    从 recommendation_id（{issue_id}-R{idx}）解析 issue_id，供「＋采纳」落地 action_plan。

    只读确定性 recommendations，绝不计算财富数字、绝不自造建议。
    """
    out = []
    for rec in (overview.get("recommendations") or [])[:3]:
        action = rec.get("action")
        if not action:
            continue
        rid = rec.get("recommendation_id") or ""
        issue_id = rid.rsplit("-R", 1)[0] if "-R" in rid else rid
        out.append({
            "recommendation_id": rid,
            "issue_id": issue_id,
            "action": action,
            "detail": rec.get("detail"),
        })
    return out


def _build_action_plan(overview: dict) -> list[str]:
    """⑤ 下一步行动（人话短句，向后兼容）：由可采纳结构拼成「动作：细节」，绝不自造。"""
    return [f"{r['action']}：{r['detail']}" if r["detail"] else r["action"]
            for r in _build_action_plans(overview)]


def attach_layers(resp: AgentResponse, family_id: int,
                  invalidation: list[dict] | None) -> AgentResponse:
    """对 AgentResponse 附加五层结构化契约（幂等：已附加则原样返回）。

    系统层全部确定性取值：overview 复算一次（纯函数，与 handle 内部结果一致），
    变化来自 detect_invalidation 的确定性 diff，行动来自 overview.recommendations；
    LLM 叙事层（④判断）复用 resp.finding（已在组装层数字剥离）。
    """
    if resp.layers is not None:
        return resp
    if resp.status != "ok":
        return resp   # 澄清/拒绝/错误 → 旧扁平渲染，不套五层
    data = db.dump_family(family_id)
    overview = build_overview(data)
    # 情景对比走专用证据图（baseline vs 方案分组条形图），不再用 overview 画像块。
    if resp.intent == "SCENARIO_COMPARE" and resp.scenario_comparison:
        scenario_chart = _build_scenario_chart(resp.scenario_comparison)
        charts = [scenario_chart] if scenario_chart else []
    else:
        charts = _build_charts(resp.intent, overview)
    layers = AdvisorLayers(
        conclusion=_build_conclusion(overview),
        changes=_build_changes(invalidation),
        charts=charts,
        judgment=resp.finding,
        action_plan=_build_action_plan(overview),
        action_plans=[ActionPlanRef(**a) for a in _build_action_plans(overview)],
    )
    # ⑥ 结构化追问：系统缺数检测（deterministic），与五层同源、同幂等。
    follow_ups = [FollowUpRef(**f) for f in follow_up_questions(resp.intent, data)]
    return resp.model_copy(update={"layers": layers, "follow_up_questions": follow_ups})
