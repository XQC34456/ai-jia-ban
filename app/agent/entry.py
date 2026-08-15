"""AI 顾问统一入口：抽取（建档）优先，否则走七意图 Agent。

V2.1 新增：进入 handle 前预取 Wealth Context 文本（V2.1 只在 LLM 兜底消费，
V2.2/V2.3 将全量消费）。A3 handle() 编排逻辑零改动，仅扩展可选参数。
"""
from __future__ import annotations

from .. import db
from ..schemas.agent import AgentResponse, ConfirmCard
from ..schemas.context import QUESTION_SOURCES, AdvisorContext, build_advisor_context
from .context import build_wealth_context, context_to_text
from .layers import attach_layers
from .memory import build_memory_context, detect_invalidation, record_turn
from .profile import cancel_confirmation, create_confirm, extract_actions, looks_like_filing
from .provider import LLMProvider
from .response import build_response
from .runtime import handle

__all__ = ["converse", "cancel_and_reanswer"]

_FILING_CLARIFY_SUMMARY = (
    "我识别到你在介绍家庭财务情况，但有些金额我还没听清。"
    "请说得更具体些，例如：月收入多少、房贷月供多少、存款大概多少。"
)


def converse(message: str, user: dict, llm: LLMProvider | None = None,
             context: dict | None = None) -> ConfirmCard | AgentResponse:
    """先建 AdvisorContext（Phase 1b），再按建档判定走确认卡 / 明确追问 / 七意图。

    Phase 1b 重构（G1）：提问面来源（goals/retirement/allocation/sandbox/overview）
    天然按提问处理，建档判定不参与（见本函数主体注释）。source=chat（含无 context）
    保留原三级：抽取命中 → 确认卡；抽空但像建档 → need_clarification 明确追问；
    否则 → 七意图 Agent。user 需含 family_id（tier 供 SCENARIO_COMPARE 的 VIP 门）。

    内测观察期埋点：每条用户消息 → 一条 intent_asked（记「最终路由后」的 intent，
    建档路径记 filing）；失效触发 → 一条 stale_detected。只记事实，不参与财富计算。
    """
    family_id = user["family_id"]
    # Context 阶段（先于 intent）：构建解析层 AdvisorContext（request 归一 + family_state）。
    # 数字只由系统确定性写入；payload 白名单剥离禁止字段（T6）；query 缺省回退 message（G3）。
    advisor_ctx = build_advisor_context(message, user, context)
    # G1 解法（设计 §3）：提问面来源（goals/retirement/allocation/sandbox/overview）天然是
    # 「提问」——source 是构造事实，建档判定不参与意图。source=chat 保留现状建档判定，
    # 只作「非情景词 + 非问句 + 有金额」时的兜底，不再抢先覆盖回答。
    # Step 4（G3 闭环）：filing_declined=True 表示用户已拒绝本次建档（取消的是数据录入，
    # 不是自己的问题）——跳过同一次建档 gate，把原问题直接投入正常回答路径（防死循环）。
    if (advisor_ctx.request.source not in QUESTION_SOURCES
            and not advisor_ctx.request.filing_declined):
        actions = extract_actions(message, llm=llm)
        if actions:
            db.record_event(family_id, "intent_asked", intent="filing")
            return create_confirm(family_id, actions, original_query=message,
                                  advisor_context=advisor_ctx)
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
                    memory_context=memory_context, advisor_ctx=advisor_ctx)
    if isinstance(result, AgentResponse):
        result = attach_layers(result, family_id, invalidation)
        db.record_event(family_id, "intent_asked", intent=result.intent,
                        meta={"status": result.status})
    record_turn(family_id, message, result)
    return result


def cancel_and_reanswer(user: dict, pending_id: str,
                        llm: LLMProvider | None = None) -> AgentResponse | ConfirmCard:
    """取消建档后继续回答（Step 4，G3 闭环）：**拒绝本次建档 ≠ 拒绝回答**。

    消费 pending（cancel_confirmation 弹出，返回 discarded 响应 + 原问题 + 解析后 ctx），
    以 filing_declined 语义把原问题重新投入正常回答路径：

    1. 原问题完整保留：用 original_query（用户字面原话）重新回答，绝不从 canned 文案猜。
    2. 不二次弹卡：filing_declined=True 跳过同一次建档 gate（防死循环）。
    3. 走正常 Advisor 路径：重新进 converse → handle → route_intent/advisor，
       不降级成模板/fallback——用户取消的是数据录入动作，不是自己的问题。

    pending 失效/跨家庭 → 返回 error（与 apply_confirmation 同口径，不重复回答）。
    """
    disc, original_query, pending_ctx = cancel_confirmation(user["family_id"], pending_id)
    if disc.type == "error":
        return disc
    if not original_query:
        return disc  # 防御：无原问题可答（正常不会发生）
    re_ctx = _reanswer_context(pending_ctx, original_query)
    return converse(original_query, user, llm=llm, context=re_ctx)


def _reanswer_context(pending_ctx, original_query: str) -> dict:
    """把已拒绝建档的上下文重建成「正常回答路径」的请求 dict（Step 4）。

    - source 保留（建档来自 chat，source 即 chat；保留语义完整性）
    - query = 用户原问题（G3 恢复物，独立于建档流程跨取消存活）
    - filing_declined=True：本次回答明确「已拒绝本次建档」，converse 跳过建档 gate
    """
    src = "chat"
    if pending_ctx is not None and getattr(pending_ctx, "request", None) is not None:
        src = pending_ctx.request.source or "chat"
    return {"source": src, "query": original_query, "filing_declined": True}


def _wealth_context_text(user: dict) -> str | None:
    """预取 Wealth Context 文本（组装器纯函数，数字带 source）。"""
    data = db.dump_family(user["family_id"])
    return context_to_text(build_wealth_context(data))
