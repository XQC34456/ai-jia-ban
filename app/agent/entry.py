"""AI 顾问统一入口：抽取（建档）优先，否则走七意图 Agent。A3 handle() 零改动。"""
from __future__ import annotations

from ..schemas.agent import AgentResponse, ConfirmCard
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
    return handle(message, user, llm=llm, context=context)
