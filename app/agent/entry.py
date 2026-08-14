"""AI 顾问统一入口：抽取（建档）优先，否则走七意图 Agent。

V2.1 新增：进入 handle 前预取 Wealth Context 文本（V2.1 只在 LLM 兜底消费，
V2.2/V2.3 将全量消费）。A3 handle() 编排逻辑零改动，仅扩展可选参数。
"""
from __future__ import annotations

from .. import db
from ..schemas.agent import AgentResponse, ConfirmCard
from .context import build_wealth_context, context_to_text
from .memory import build_memory_context, detect_invalidation, record_turn
from .profile import create_confirm, extract_actions
from .provider import LLMProvider
from .runtime import handle

__all__ = ["converse"]


def converse(message: str, user: dict, llm: LLMProvider | None = None,
             context: dict | None = None) -> ConfirmCard | AgentResponse:
    """先抽取建档动作：命中则返回确认卡片；否则交给七意图 Agent。

    user 需含 family_id（tier 供 SCENARIO_COMPARE 的 VIP 门）。
    """
    actions = extract_actions(message)
    if actions:
        return create_confirm(user["family_id"], actions)
    wealth_context = _wealth_context_text(user)
    detect_invalidation(user["family_id"])          # 先确定性失效检测（标记 stale）
    memory_context = build_memory_context(user["family_id"])
    result = handle(message, user, llm=llm, context=context, wealth_context=wealth_context,
                    memory_context=memory_context)
    record_turn(user["family_id"], message, result)
    return result


def _wealth_context_text(user: dict) -> str | None:
    """预取 Wealth Context 文本（组装器纯函数，数字带 source）。"""
    data = db.dump_family(user["family_id"])
    return context_to_text(build_wealth_context(data))
