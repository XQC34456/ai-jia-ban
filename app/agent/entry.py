"""AI 顾问统一入口：抽取（建档）优先，否则走七意图 Agent。

V2.1 新增：进入 handle 前预取 Wealth Context 文本（V2.1 只在 LLM 兜底消费，
V2.2/V2.3 将全量消费）。A3 handle() 编排逻辑零改动，仅扩展可选参数。
"""
from __future__ import annotations

from .. import db
from ..schemas.agent import AgentResponse, ConfirmCard
from .context import build_wealth_context, context_to_text
from .layers import attach_layers
from .memory import build_memory_context, detect_invalidation, record_turn
from .profile import create_confirm, extract_actions, looks_like_filing
from .provider import LLMProvider
from .response import build_response
from .runtime import handle

__all__ = ["converse"]

_FILING_CLARIFY_SUMMARY = (
    "我识别到你在介绍家庭财务情况，但有些金额我还没听清。"
    "请说得更具体些，例如：月收入多少、房贷月供多少、存款大概多少。"
)


def converse(message: str, user: dict, llm: LLMProvider | None = None,
             context: dict | None = None) -> ConfirmCard | AgentResponse:
    """先抽取建档动作：命中则返回确认卡片；否则交给七意图 Agent。

    V27.1 三级：抽取命中 → 确认卡；抽空但像建档 → need_clarification 明确追问；
    否则 → 七意图 Agent。user 需含 family_id（tier 供 SCENARIO_COMPARE 的 VIP 门）。

    内测观察期埋点：每条用户消息 → 一条 intent_asked（记「最终路由后」的 intent，
    建档路径记 filing）；失效触发 → 一条 stale_detected。只记事实，不参与财富计算。
    """
    family_id = user["family_id"]
    actions = extract_actions(message, llm=llm)
    if actions:
        db.record_event(family_id, "intent_asked", intent="filing")
        return create_confirm(family_id, actions)
    if looks_like_filing(message):
        db.record_event(family_id, "intent_asked", intent="filing",
                        meta={"status": "need_clarification"})
        return build_response("EXPLAIN_RESULT", "need_clarification", None,
                              summary=_FILING_CLARIFY_SUMMARY)
    wealth_context = _wealth_context_text(user)
    invalidation = detect_invalidation(family_id)   # 先确定性失效检测（标记 stale）
    if invalidation:
        db.record_event(family_id, "stale_detected", meta={"count": len(invalidation)})
    memory_context = build_memory_context(family_id, invalidation=invalidation)
    result = handle(message, user, llm=llm, context=context, wealth_context=wealth_context,
                    memory_context=memory_context)
    if isinstance(result, AgentResponse):
        result = attach_layers(result, family_id, invalidation)
        db.record_event(family_id, "intent_asked", intent=result.intent,
                        meta={"status": result.status})
    record_turn(family_id, message, result)
    return result


def _wealth_context_text(user: dict) -> str | None:
    """预取 Wealth Context 文本（组装器纯函数，数字带 source）。"""
    data = db.dump_family(user["family_id"])
    return context_to_text(build_wealth_context(data))
