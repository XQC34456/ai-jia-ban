"""A3 Agent Runtime：把「用户消息」编排成 AgentResponse（纯确定性骨架，LLM 为插件）。

铁律（A3.1 冻结）：
- 只取数·识别·映射·引用·解释，绝不加工·再计算·自行产出财富数字
- 财富计算唯一入口仍是 build_overview（经 A2 工具透传），Runtime 绝不复刻公式
- metric value 必带 source（MetricRef 硬闸）；known_limitations 逐字透传
- 缺参数 → need_clarification 追问，绝不填默认值
"""
from __future__ import annotations

from ..schemas.agent import AgentResponse
from .advisor import advise
from .dispatch import dispatch
from .errors import map_tool_error
from .params import extract_scenario_params
from .provider import LLMProvider
from .response import build_response
from .router import refusal_gate, route_intent
from .tools import ToolError, get_issues
from .vip import value_first

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
           context: dict | None = None, wealth_context: str | None = None,
           memory_context: str | None = None,
           advisor_ctx=None) -> AgentResponse:
    """编排一次完整交互：拒算门 → 意图路由 → 参数提取 → 工具分派 → 组装响应。

    advisor_ctx（Phase 1b 解析层 AdvisorContext，entry 入口构建）携带页面 intent_hint
    进入路由（SEED 非 OVERRIDE），供缺数检测底座取用。缺省 None 时行为与改造前一致。
    """
    # ① 拒算门（优先于普通意图路由）
    refusal = refusal_gate(message)
    if refusal is not None:
        if refusal.get("disambiguate"):
            # 意图消歧：有 LLM 走 advisor_path（知识问答 / 纯计算拒绝 / 家庭影响），
            # 无 LLM 或失败 → 回退确定性反问。
            if llm is not None:
                resp = advise(user, message, llm, wealth_context=wealth_context,
                              memory_context=memory_context, intent="VIEW_OVERVIEW",
                              advisor_ctx=advisor_ctx)
                if resp is not None:
                    return resp
            return build_response("EXPLAIN_RESULT", "need_clarification", None,
                                  summary=_DISAMBIGUATE_SUMMARY)
        intent = "SCENARIO_COMPARE"
        hint = refusal["scenario"]
    else:
        # 页面 intent_hint 只作 SEED：关键词强路由优先（用户当前 query 压倒 hint），
        # hint 仅在关键词未命中时、于 LLM 兜底之前生效（见 route_intent）。
        intent_hint = (advisor_ctx.request.intent_hint
                       if advisor_ctx is not None else None)
        intent = route_intent(message, llm, wealth_context=wealth_context,
                              memory_context=memory_context, intent_hint=intent_hint)
        hint = None

    # ② advisor_path：所有意图（含 EXPLAIN_RESULT）先走顾问式 tool_loop（LLM 为插件）。
    #    有 LLM 能力时「顾问」接管，失败 / 无 LLM → 回退确定性 dispatch（③④⑤）。
    #    EXPLAIN_RESULT 也走 advisor_path，单轮内由 LLM 调工具解释（跨轮上下文留 V2.4）。
    if llm is not None:
        resp = advise(user, message, llm, wealth_context=wealth_context,
                      memory_context=memory_context, intent=intent,
                      advisor_ctx=advisor_ctx)
        if resp is not None:
            return resp

    # ③ SCENARIO_COMPARE：确定性参数提取 + 分派（advisor_path 降级兜底）
    if intent == "SCENARIO_COMPARE":
        pr = extract_scenario_params(message, llm, scenario_hint=hint)
        if pr.missing or pr.error:
            return build_response(intent, "need_clarification", None,
                                  summary=_clarify(pr.missing))
        try:
            result = dispatch(intent, user, pr.scenario, pr.params)
        except ToolError as e:
            return _error_response(intent, e, user, pr.scenario)
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


def _error_response(intent: str, err: ToolError, user: dict | None = None,
                    scenario: str | None = None) -> AgentResponse:
    # P2-A 价值前置：Free 触发情景模拟（forbidden）→ 先给基础判断，再展示 VIP 边界，
    # 不再冷冰冰「该功能需要升级」。基础判断来自免费基线 get_issues（Decision 确定性），
    # 数字只走 metrics/source，本层绝不编造。
    if err.kind == "forbidden" and intent == "SCENARIO_COMPARE":
        return _vip_value_first_response(user, scenario)
    status, summary, next_actions = map_tool_error(err.kind, err.detail)
    return build_response(intent, status, None, summary=summary, next_actions=next_actions)


def _vip_value_first_response(user: dict | None, scenario: str | None) -> AgentResponse:
    """确定性兜底路径的价值前置响应：基础判断（get_issues 主要矛盾）+ VIP 边界。

    复用 build_response(CHECK_ISSUES) 确定性取数（finding/metrics/recommendations 均来自
    Decision），再把意图改回 SCENARIO_COMPARE 并注入 vip_boundary；status 保持 ok（已交付
    基础价值），非 refused。
    """
    basic, further = value_first(scenario)
    issues = get_issues(user) if user else {}
    base = build_response("CHECK_ISSUES", "ok", issues, summary=basic,
                          next_actions=["升级 VIP 解锁完整情景模拟"])
    return base.model_copy(update={
        "intent": "SCENARIO_COMPARE",
        "vip_boundary": further,
        # 基础判断用 summary 承载（情景方向性结论）；不派生「健康体检」finding，
        # 以免 layered ④判断 喧宾夺主（①结论 已给出主要矛盾）。
        "finding": None,
    })
