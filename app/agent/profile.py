"""建档吸收层：V1 的「抽取 → 确认卡片 → 落地」能力迁入 Agent 包。

铁律：
- 抽取到动作只进 pending，确认后才写库；落地不计算财富，只写数据。
- 落地前绝不写数据库（防 LLM 幻觉污染数据）。
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from .. import db
from ..extraction import RuleExtractor, extract_with_llm, validate_actions
from ..schemas.agent import AppliedResponse, ConfirmCard
from .memory import record_fact
from .provider import LLMProvider

_PENDING: dict[str, dict[str, Any]] = {}

logger = logging.getLogger(__name__)

# 确认卡分组元信息：kind → (组名, 图标)。未知 kind 归「其他」。
_KIND_META = {
    "income": ("收入", "🟢"), "expense": ("支出", "🔵"),
    "asset": ("资产", "🟢"), "liability": ("负债", "🟠"),
    "goal": ("目标", "🟣"), "person": ("成员", "⚪"),
}


def extract_actions(message: str, llm: LLMProvider | None = None) -> list[dict[str, Any]]:
    """从自然语言抽取建档动作；空列表 = 非建档表述（交给 Agent 走七意图）。

    V27.1 三级：
    1) LLM 主抽取（function-calling，一次抽全）→ validate；
    2) LLM 不可用/抽空 → RuleExtractor 兜底 → validate；
    3) 两者都空 → 由 converse 用 looks_like_filing 决定「明确追问」还是「七意图」。
    落地仍只在确认卡确认后，防 LLM 幻觉污染数据。

    先 looks_like_filing 廉价预判：非建档表述（提问/情景）不浪费 LLM 抽取调用，
    直接走规则 → 空 → 七意图。
    """
    if llm is not None and looks_like_filing(message):
        try:
            actions = extract_with_llm(message, llm)
        except Exception as e:  # LLM 异常不静默吞：记日志后降级规则
            logger.warning("LLM 抽取失败，降级规则抽取：%s", e)
            actions = []
        if actions:
            return validate_actions(actions)
    return validate_actions(RuleExtractor().extract(message))


_FILING_HINT_RE = re.compile(
    r"月薪|一个月|每月|工资|月入|收入|支出|开销|花销|房贷|车贷|消费贷|信用卡|"
    r"房租|学费|生活费|月供|存款|现金|活期|基金|股票|房产|资产|负债|保险|应急金|净资产"
)
# 情景动词（投资/买房等）→ 不是建档陈述，交给 SCENARIO/七意图
# 「下降/减少」覆盖「收入下降/收入减少」这类变化情景：带金额但绝不能被当作建档金额拦截
_SCENARIO_RE = re.compile(r"投资|买房|买股票|提前还|理财|贷款|借钱|投点|下降|减少")
_QUESTION_RE = re.compile(r"[?？]|吗|呢|怎么|如何|怎样|帮我|建议|分析|问题|风险|最大")


def looks_like_filing(message: str) -> bool:
    """粗略判定「介绍家庭财务」：财务关键词 + 金额；或财务关键词无金额但非疑问非情景。

    用途：1) extract_actions 里廉价预判是否值得走 LLM 抽取；2) converse 第三层
    决定「明确追问」还是「交给七意图」。
    """
    if _SCENARIO_RE.search(message):
        return False
    if not _FILING_HINT_RE.search(message):
        return False
    if re.search(r"\d", message):
        return True
    return not _QUESTION_RE.search(message)


def create_confirm(family_id: int, actions: list[dict[str, Any]],
                   original_query: str | None = None,
                   advisor_context=None) -> ConfirmCard:
    """把抽取到的动作暂存为 pending，返回确认卡片；未确认前不写库。

    Phase 1b G3：随卡存 original_query（用户原话）与 advisor_context（解析后 ctx），
    取消后原问题不丢——可重新投入回答路径（「取消建档后继续回答」，Phase 1c 落地）。
    """
    pending_id = uuid.uuid4().hex
    _PENDING[pending_id] = {
        "family_id": family_id,
        "actions": actions,
        "original_query": original_query,
        "advisor_context": advisor_context,
    }
    groups: list[dict[str, Any]] = []
    for a in actions:
        label, icon = _KIND_META.get(a["kind"], ("其他", "⚪"))
        g = next((g for g in groups if g["label"] == label), None)
        if g is None:
            g = {"label": label, "icon": icon, "items": []}
            groups.append(g)
        g["items"].append(a["summary"])
    return ConfirmCard(
        pending_id=pending_id,
        message="我理解到以下信息，确认后我就为你建档：",
        items=[a["summary"] for a in actions],
        groups=groups,
    )


def cancel_confirmation(family_id: int, pending_id: str
                        ) -> tuple[AppliedResponse, str | None, object]:
    """弹出并消费 pending 的「取消」分支（Step 4，G3 底座）。

    返回 (discarded 响应, 原问题 original_query, 解析后 advisor_context)——
    原问题与 ctx 供 Step 4 的 cancel_and_reanswer 重新投入回答路径：
    **取消 = 拒绝本次建档 ≠ 拒绝回答**（用户取消的是数据录入动作，不是自己的问题）。
    pending 失效/跨家庭 → (error, None, None)。弹出即消费，不重复处理。
    """
    pending = _PENDING.pop(pending_id, None)
    if pending is None or pending["family_id"] != family_id:
        return (AppliedResponse(type="error", message="该确认已失效，请重新输入。"),
                None, None)
    return (AppliedResponse(type="discarded", message="好的，已忽略，没有改动你的档案。",
                            original_query=pending.get("original_query")),
            pending.get("original_query"), pending.get("advisor_context"))


def apply_confirmation(family_id: int, pending_id: str, confirmed: bool) -> AppliedResponse:
    """确认（写库）或忽略待定动作。pending 失效/跨家庭 → error。

    取消分支委托 cancel_confirmation（弹出 pending 并携带原问题 + ctx）；
    确认分支直接消费 pending 写库。两者共享同一 pending，互斥。
    """
    if not confirmed:
        resp, _, _ = cancel_confirmation(family_id, pending_id)
        return resp
    pending = _PENDING.pop(pending_id, None)
    if pending is None or pending["family_id"] != family_id:
        return AppliedResponse(type="error", message="该确认已失效，请重新输入。")
    for action in pending["actions"]:
        db.apply_action(family_id, action)
        # 顾问知识类事实（目标）写记忆层：版本化记录目标历史，检测目标变化。
        # 净值事实（income/expense/asset/liability）只写 db 主表，不进 memory_fact。
        if action["kind"] == "goal":
            gtype = action.get("fields", {}).get("type", "其他")
            record_fact(family_id, f"goal:{gtype}", action["summary"],
                        source="chat_confirmed", confidence="confirmed")
    joined = "、".join(a["summary"] for a in pending["actions"])
    return AppliedResponse(type="applied", message=f"已记录：{joined}。")
