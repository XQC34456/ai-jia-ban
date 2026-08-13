"""建档吸收层：V1 的「抽取 → 确认卡片 → 落地」能力迁入 Agent 包。

铁律：
- 抽取到动作只进 pending，确认后才写库；落地不计算财富，只写数据。
- 落地前绝不写数据库（防 LLM 幻觉污染数据）。
"""
from __future__ import annotations

import uuid
from typing import Any

from .. import db
from ..extraction import RuleExtractor
from ..schemas.agent import AppliedResponse, ConfirmCard

_PENDING: dict[str, dict[str, Any]] = {}


def extract_actions(message: str) -> list[dict[str, Any]]:
    """从自然语言抽取建档动作；空列表 = 非建档表述（交给 Agent 走七意图）。

    只用确定性规则抽取：AI 顾问主链路必须确定性、绝不 500，也不让 LLM 抽取
    抢先把「投资/买房」等情景表述误判成建档（LLM 抽取留待后续阶段）。
    """
    return RuleExtractor().extract(message)


def create_confirm(family_id: int, actions: list[dict[str, Any]]) -> ConfirmCard:
    """把抽取到的动作暂存为 pending，返回确认卡片；未确认前不写库。"""
    pending_id = uuid.uuid4().hex
    _PENDING[pending_id] = {"family_id": family_id, "actions": actions}
    return ConfirmCard(
        pending_id=pending_id,
        message="我理解到以下信息，确认后我就为你建档：",
        items=[a["summary"] for a in actions],
    )


def apply_confirmation(family_id: int, pending_id: str, confirmed: bool) -> AppliedResponse:
    """确认（写库）或忽略待定动作。pending 失效/跨家庭 → error。"""
    pending = _PENDING.pop(pending_id, None)
    if pending is None or pending["family_id"] != family_id:
        return AppliedResponse(type="error", message="该确认已失效，请重新输入。")
    if not confirmed:
        return AppliedResponse(type="discarded", message="好的，已忽略，没有改动你的档案。")
    for action in pending["actions"]:
        db.apply_action(family_id, action)
    joined = "、".join(a["summary"] for a in pending["actions"])
    return AppliedResponse(type="applied", message=f"已记录：{joined}。")
