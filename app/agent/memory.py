"""V2.4 Advisor Memory：记忆层组装（写入 + 限量读取）。

铁律：
- 纯函数 + db 读写，零 LLM、零财富计算——只「搬运」已落库的记忆。
- 只读写记忆表（conversation_message / memory_fact / advisor_judgment），
  绝不碰财富主表，绝不参与财富计算。
- 限量注入：短期对话固定最近 n 轮，绝不全文堆塞。
"""
from __future__ import annotations

from .. import db

__all__ = ["record_turn", "build_conversation_summary"]

# 短期对话记忆限量（轮数，一轮 = user + assistant 两条）
CONVERSATION_WINDOW = 5


def record_turn(family_id: int, message: str, result) -> None:
    """把一轮对话写入短期记忆：user 原文 + assistant 结论摘要（非全文）。"""
    db.append_conversation(family_id, "user", message)
    db.append_conversation(family_id, "assistant", result.summary, intent=result.intent)


def build_conversation_summary(family_id: int, n: int = CONVERSATION_WINDOW) -> str:
    """把最近 n 轮对话压成结构化摘要，每轮一行，供 LLM 读。

    n 是「轮数」，内部读最近 n*2 条消息（按 turn 正序）。空历史 → 空串。
    """
    rows = db.recent_conversations(family_id, n * 2)
    if not rows:
        return ""
    rows = list(reversed(rows))  # 倒序 → 正序（旧 → 新）
    lines = []
    for r in rows:
        if r["role"] == "user":
            lines.append(f"用户:「{r['message']}」")
        else:
            intent = r.get("intent") or "?"
            lines.append(f"AI({intent}):「{r['message']}」")
    return "\n".join(lines)
