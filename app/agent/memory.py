"""V2.4 Advisor Memory：记忆层组装（写入 + 限量读取）。

铁律：
- 纯函数 + db 读写，零 LLM、零财富计算——只「搬运」已落库的记忆。
- 只读写记忆表（conversation_message / memory_fact / advisor_judgment），
  绝不碰财富主表，绝不参与财富计算。
- 限量注入：短期对话固定最近 n 轮，绝不全文堆塞。
"""
from __future__ import annotations

from .. import db
from ..services import build_overview
from .response import build_validity_conditions

__all__ = ["record_turn", "build_conversation_summary", "record_fact",
           "is_safe_fact_value", "record_judgment", "detect_invalidation",
           "build_memory_context"]

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


def is_safe_fact_value(value: str, source: str) -> bool:
    """数字防编造闸：inferred 事实的 value 含数字 → False。

    推断（LLM 猜测）不产生财富数字；数字必须溯源（确认建档的确定性抽取），
    否则拒绝写入。source='chat_confirmed'（确定性来源）允许数字。
    """
    if source == "inferred" and any(ch.isdigit() for ch in str(value)):
        return False
    return True


def record_fact(family_id: int, key: str, value: str, source: str, confidence: str) -> int | None:
    """写一条家庭事实（带数字防编造闸）。不安全 → 不写入，返回 None。"""
    if not is_safe_fact_value(value, source):
        return None
    return db.upsert_fact(family_id, key, value, source, confidence)


def record_judgment(user: dict, resp) -> int | None:
    """把顾问判断（主要矛盾 + 依据 + 有效条件快照）写入判断记忆。

    - 只有 status=ok 且产出 priorities 才是「完整判断」，refuse/need_clarification 不写。
    - validity_conditions 主动 build_overview 提取当前关键值快照（不依赖 LLM 调了啥）。
    - 数字/依据直接序列化 V2.3 的 PriorityRef/EvidenceRef，不经过 LLM 二次加工。
    """
    if resp.status != "ok" or not resp.priorities:
        return None
    data = db.dump_family(user["family_id"])
    overview = build_overview(data)
    conditions = build_validity_conditions(overview)
    return db.save_judgment(
        user["family_id"],
        priorities=[p.model_dump() for p in resp.priorities],
        evidence=[e.model_dump() for e in resp.evidence],
        recommendation=resp.summary,
        validity_conditions=conditions,
    )


def detect_invalidation(family_id: int) -> list[dict]:
    """确定性检测最近 active 判断是否失效（当前状态 vs validity_conditions 逐 key 对比）。

    任一依赖值变化 → 标记 stale，返回变化清单 [{key, before, after}]。
    无 active 判断 / 无变化 → 空列表。失效检测由确定性代码完成，绝不由 LLM 判断。
    """
    j = db.latest_judgment(family_id)
    if j is None or j["status"] != "active":
        return []
    data = db.dump_family(family_id)
    current = build_validity_conditions(build_overview(data))
    conds = j["validity_conditions"] or {}
    changed = []
    for k, before in conds.items():
        after = current.get(k)
        if after is not None and after != before:
            changed.append({"key": k, "before": before, "after": after})
    if changed:
        db.invalidate_judgment(j["id"])
    return changed


# 失效维度 → 人话标签（detect_invalidation 的 changed 清单 key 翻译，供 advisor 读懂）。
_INVALIDATION_LABELS = {
    "cashflow_surplus": "月度结余",
    "dti": "负债率",
    "liquidity_months": "应急资金月数",
    "rfr": "养老覆盖",
    "real_estate_pct": "房产占比",
    "insurance_count": "保险份数",
    "total_coverage": "保险总保额",
}


def build_memory_context(family_id: int,
                         conversation_turns: int = CONVERSATION_WINDOW,
                         invalidation: list[dict] | None = None) -> str:
    """合成三层记忆摘要（L1 近期对话 + L2 家庭事实 + L3 最近判断），注入 advisor。

    纯函数、零 LLM、零财富计算——只「搬运」已落库的记忆，绝不编数字、绝不参与计算。
    限量：L1 固定最近 N 轮、L2 只当前有效、L3 只最近 1 次判断。空记忆 → 空串。
    失效判断（status=stale）附「已失效」提示（由 detect_invalidation 确定性标记）；
    invalidation（本次失效的 changed 清单）非空时，附具体维度 + before→after（数字
    来自确定性 diff，非 LLM 计算），供 advisor 先比较变化再重新评估。
    """
    parts: list[str] = []

    conv = build_conversation_summary(family_id, conversation_turns)
    if conv:
        parts.append(f"【近期对话】\n{conv}")

    facts = db.current_facts(family_id)
    if facts:
        lines = [f"· {f['key']} = {f['value']}（source={f['source']}, v{f['version']}）"
                 for f in facts]
        parts.append("【已确认的家庭事实】\n" + "\n".join(lines))

    j = db.latest_judgment(family_id)
    if j is not None:
        lines = ["· 主要矛盾：" + "、".join(
            p.get("title") or p.get("issue_id", "") for p in j["priorities"])]
        if j["recommendation"]:
            lines.append(f"· 上次建议：{j['recommendation']}")
        if invalidation:
            dims = [f"{_INVALIDATION_LABELS.get(c.get('key'), c.get('key'))}："
                    f"{c.get('before')} → {c.get('after')}" for c in invalidation]
            lines.append("⚠️ 上次判断已失效，以下关键数据已变化，请先比较变化再重新评估：")
            lines.extend(f"  - {d}" for d in dims)
        elif j["status"] == "stale":
            lines.append("⚠️ 上次判断已失效：判断依赖的关键数据已变化，请重新评估")
        parts.append("【上次判断】\n" + "\n".join(lines))

    return "\n\n".join(parts)
