"""A3 Agent Runtime：把「用户消息」编排成 AgentResponse（纯确定性骨架，LLM 为插件）。

铁律（A3.1 冻结）：
- 只取数·识别·映射·引用·解释，绝不加工·再计算·自行产出财富数字
- 财富计算唯一入口仍是 build_overview（经 A2 工具透传），Runtime 绝不复刻公式
- metric value 必带 source（MetricRef 硬闸）；known_limitations 逐字透传
- 缺参数 → need_clarification 追问，绝不填默认值
"""
from __future__ import annotations

from ..schemas.agent import AgentResponse
from .dispatch import dispatch
from .errors import map_tool_error
from .params import extract_scenario_params
from .provider import LLMProvider
from .response import build_response
from .router import refusal_gate, route_intent
from .tools import ToolError

__all__ = ["handle"]

# ok 状态话术模板（无任何数字 → 无编造风险；数字只活在 metrics.value+source）。
_OK_SUMMARY = {
    "VIEW_OVERVIEW": "已为你生成家庭财富总览，关键指标见下方。",
    "CHECK_ISSUES": "已为你梳理当前需要关注的财富问题。",
    "CHECK_RETIREMENT": "已为你测算养老准备情况，关键指标见下方。",
    "CHECK_ALLOCATION": "已为你分析当前资产配置，关键指标见下方。",
    "CHECK_GOALS": "已为你汇总家庭目标与进度。",
    "SCENARIO_COMPARE": "已完成情景对比，各方案财富影响见下方。",
    "EXPLAIN_RESULT": "以下是对上次结果的说明。",
}

_CLARIFY_PREFIX = "需要补充以下信息："

_DISAMBIGUATE_SUMMARY = (
    "你是想知道复利本身怎么计算，还是想看看它对你家庭未来资产有什么影响？"
    "前者是独立金融计算，我不能自行测算；后者我可以结合你的家庭数据做情景模拟。"
)


def handle(message: str, user: dict, llm: LLMProvider | None = None,
           context: dict | None = None, wealth_context: str | None = None) -> AgentResponse:
    """编排一次完整交互：拒算门 → 意图路由 → 参数提取 → 工具分派 → 组装响应。"""
    # ① 拒算门（优先于普通意图路由）
    refusal = refusal_gate(message)
    if refusal is not None:
        if refusal.get("disambiguate"):
            return build_response("EXPLAIN_RESULT", "need_clarification", None,
                                  summary=_DISAMBIGUATE_SUMMARY)
        intent = "SCENARIO_COMPARE"
        hint = refusal["scenario"]
    else:
        intent = route_intent(message, llm, wealth_context=wealth_context)
        hint = None

    # ② SCENARIO_COMPARE：参数提取 + 分派
    if intent == "SCENARIO_COMPARE":
        pr = extract_scenario_params(message, llm, scenario_hint=hint)
        if pr.missing or pr.error:
            return build_response(intent, "need_clarification", None,
                                  summary=_clarify(pr.missing))
        try:
            result = dispatch(intent, user, pr.scenario, pr.params)
        except ToolError as e:
            return _error_response(intent, e)
        return build_response(intent, "ok", result, summary=_OK_SUMMARY[intent])

    # ③ EXPLAIN_RESULT：复用上下文，不调工具
    if intent == "EXPLAIN_RESULT":
        if context is None:
            return build_response(intent, "need_clarification", None,
                                  summary="请先查看某个结果，我再为你解释。")
        return build_response(intent, "ok", context, summary=_OK_SUMMARY[intent])

    # ④ 其余四类：直接分派到 A2 工具
    result = dispatch(intent, user)
    return build_response(intent, "ok", result, summary=_OK_SUMMARY[intent])


def _clarify(missing: list[str]) -> str:
    return _CLARIFY_PREFIX + "、".join(missing)


def _error_response(intent: str, err: ToolError) -> AgentResponse:
    status, summary, next_actions = map_tool_error(err.kind, err.detail)
    return build_response(intent, status, None, summary=summary, next_actions=next_actions)
