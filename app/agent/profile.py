"""建档吸收层：V1 的「抽取 → 确认卡片 → 落地」能力迁入 Agent 包。

铁律：
- 抽取到动作只进 pending，确认后才写库；落地不计算财富，只写数据。
- 落地前绝不写数据库（防 LLM 幻觉污染数据）。
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
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


@dataclass
class ReconciledAction:
    """一个建档动作对照档案后的三态结果（Phase 2 第一刀「档案对照」）。

    status ∈ new / exists / conflict：
    - new：档案无同身份记录 → 确认后正常插入。
    - exists：同身份且值全同 → 复用不写（重复建档不产生重复实体）。
    - conflict：同身份但值不同 → 恰一条可覆盖（matched_id 命中）；多条歧义
      （matched_id=None）→ 宁可让用户确认，也绝不替用户猜哪一笔该覆盖。
    table 供 conflict 覆盖用（cashflow/asset/liability/goal/person）。
    """
    action: dict[str, Any]
    status: str
    table: str | None = None
    matched_id: int | None = None
    archive_value: str | None = None


# 档案对照身份/值字段。身份字段用**粗粒度稳定字段**——name 跨抽取路径不稳定
# （RuleExtractor「存款」→ name=存款，档案手工录入 → name=现金），不可作身份。
_RECONCILE_SPEC = {
    "income":    {"table": "cashflow", "identity": ("category", "period"), "value": ("amount",)},
    "expense":   {"table": "cashflow", "identity": ("category", "period"), "value": ("amount",)},
    "asset":     {"table": "asset", "identity": ("type",), "value": ("value",)},
    "liability": {"table": "liability", "identity": ("type",), "value": ("principal", "monthly_payment")},
    "goal":      {"table": "goal", "identity": ("type",), "value": ("target_amount", "current_saved")},
    "person":    {"table": "person", "identity": ("name",), "value": ("birth_year", "monthly_income")},
}


def _archive_value(kind: str, row: dict[str, Any]) -> str:
    """档案行的人类可读现值（确认卡冲突差异标注用）。"""
    if kind in ("income", "expense"):
        return f"{row.get('amount', 0):,.0f} 元"
    if kind == "asset":
        return f"{row.get('value', 0):,.0f} 元"
    if kind == "liability":
        return f"月供 {row.get('monthly_payment', 0):,.0f} 元"
    if kind == "goal":
        return f"目标 {row.get('target_amount', 0):,.0f} 元"
    if kind == "person":
        by = row.get("birth_year")
        return f"{by} 年生" if by else "—"
    return "—"


def reconcile_actions(family_id: int, actions: list[dict[str, Any]]) -> list[ReconciledAction]:
    """把抽取动作对照当前档案（dump_family），逐动作返回三态对照结果。

    对照规则（每类独立）：
    cand = 档案中身份字段全同的行
      → cand 空                                ⇒ new
      → cand 里有值字段全同的行                 ⇒ exists（复用不写）
      → cand 恰 1 行且值不同                    ⇒ conflict（matched_id 命中，可覆盖）
      → cand > 1 行且值不同                     ⇒ conflict（歧义，不自动覆盖）
    未知 kind（如 insurance 兜底）→ 不对照，直接 new。
    """
    fam = db.dump_family(family_id)
    rows: dict[str, list[dict[str, Any]]] = {
        "cashflow": fam.get("cashflows") or [],
        "asset": fam.get("assets") or [],
        "liability": fam.get("liabilities") or [],
        "goal": fam.get("goals") or [],
        "person": fam.get("persons") or [],
    }
    out: list[ReconciledAction] = []
    for action in actions:
        kind = action["kind"]
        spec = _RECONCILE_SPEC.get(kind)
        if spec is None:
            out.append(ReconciledAction(action=action, status="new"))
            continue
        f = action["fields"]
        table = spec["table"]
        if table == "cashflow":
            cand = [r for r in rows["cashflow"]
                    if r.get("flow_type") == ("income" if kind == "income" else "expense")
                    and r.get("category") == f.get("category",
                                                   "工资" if kind == "income" else "其他")
                    and r.get("period") == f.get("period", "月")]
        else:
            identity = {c: f.get(c) for c in spec["identity"]}
            cand = [r for r in rows[table]
                    if all(r.get(c) == v for c, v in identity.items())]
        if not cand:
            out.append(ReconciledAction(action=action, status="new"))
            continue
        if any(all(r.get(c) == f.get(c) for c in spec["value"]) for r in cand):
            out.append(ReconciledAction(action=action, status="exists"))
            continue
        if len(cand) == 1:
            out.append(ReconciledAction(action=action, status="conflict", table=table,
                                        matched_id=cand[0]["id"],
                                        archive_value=_archive_value(kind, cand[0])))
        else:
            out.append(ReconciledAction(action=action, status="conflict", table=table,
                                        matched_id=None, archive_value=None))
    return out


def _item_text(rc: ReconciledAction) -> str:
    """确认卡单项文案：new 用 summary；conflict 追加差异标注（单匹配/歧义）。"""
    s = rc.action["summary"]
    if rc.status != "conflict":
        return s
    if rc.archive_value:
        return f"{s}（档案现在是 {rc.archive_value}）"
    return f"{s}（档案有多笔记录，未自动改动）"


def _build_groups(write: list[ReconciledAction]) -> list[dict[str, Any]]:
    """确认卡分组：按 kind 分组成 write（new + conflict）项。未知 kind 归「其他」。"""
    groups: list[dict[str, Any]] = []
    for rc in write:
        label, icon = _KIND_META.get(rc.action["kind"], ("其他", "⚪"))
        g = next((g for g in groups if g["label"] == label), None)
        if g is None:
            g = {"label": label, "icon": icon, "items": []}
            groups.append(g)
        g["items"].append(_item_text(rc))
    return groups


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
    Phase 2 第一刀：弹卡前对照档案（reconcile_actions），对照结果存进 pending——
    exists 复用不写（不进待写项）、conflict 标注差异（单匹配可覆盖 / 多匹配歧义不自动改）。
    """
    pending_id = uuid.uuid4().hex
    reconciled = reconcile_actions(family_id, actions)
    _PENDING[pending_id] = {
        "family_id": family_id,
        "actions": actions,
        "reconciled": reconciled,
        "original_query": original_query,
        "advisor_context": advisor_context,
    }
    write = [rc for rc in reconciled if rc.status != "exists"]
    exists_note = [rc.action["summary"] for rc in reconciled if rc.status == "exists"]
    items = [_item_text(rc) for rc in write]
    if write:
        message = "我理解到以下信息，确认后我就为你建档："
        if exists_note:
            message += "（" + "、".join(exists_note) + " 已在档案，无需重复建档）"
    else:
        message = "以下信息已在档案中，无需重复建档：" + "、".join(
            rc.action["summary"] for rc in reconciled)
    return ConfirmCard(
        pending_id=pending_id,
        message=message,
        items=items,
        groups=_build_groups(write),
    )


def _record_goal_fact(family_id: int, action: dict[str, Any]) -> None:
    """顾问知识类事实（目标）写记忆层：版本化记录目标历史，检测目标变化。

    净值事实（income/expense/asset/liability）只写 db 主表，不进 memory_fact。
    goal 冲突覆盖也走此路径——覆盖写入是完整写入（表 + 记忆历史），保持
    V2.4 goal 变更版本化契约。"""
    if action["kind"] == "goal":
        gtype = action.get("fields", {}).get("type", "其他")
        record_fact(family_id, f"goal:{gtype}", action["summary"],
                    source="chat_confirmed", confidence="confirmed")


def _record_provenance(family_id: int, rc: ReconciledAction, status: str,
                       **extra) -> None:
    """来源追踪（第三刀）：确认后把本条动作的来源记成 product_event。

    只做「这条事实从哪里来」的可查询事件：new（新声明）/ exists（既有复用）/
    conflict_overwrite（覆盖，带 matched_id=被改行 + prev_value=改前值）/
    conflict_ambiguous（多匹配歧义，不定位）。不碰档案表、不注入 LLM。
    """
    meta = {"status": status, "kind": rc.action["kind"],
            "summary": rc.action["summary"]}
    meta.update(extra)
    db.record_event(family_id, "filing_provenance", intent="filing", meta=meta)


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
    reconciled = pending.get("reconciled")
    if reconciled is None:  # 防御：旧 pending 无对照结果 → 退化为逐条新增
        reconciled = [ReconciledAction(action=a, status="new")
                      for a in pending["actions"]]
    applied_summaries: list[str] = []
    skip_notes: list[str] = []
    for rc in reconciled:
        a = rc.action
        if rc.status == "exists":
            skip_notes.append(f"{a['summary']} 已在档案")
            _record_provenance(family_id, rc, "exists")
            continue
        if rc.status == "conflict":
            if rc.matched_id is not None and rc.table:
                # 单匹配冲突：确认后覆盖更新，但**只更新允许的 value 字段**——
                # identity 与 name 等身份锚字段永不被覆盖（第二刀硬契约，
                # 修掉「现金」被改写成「存款」这类整行替换残余）。
                spec = _RECONCILE_SPEC.get(a["kind"])
                value_fields = {c: a["fields"][c] for c in (spec["value"] if spec else ())
                                if c in a["fields"]}
                db.update_entity(rc.table, rc.matched_id, value_fields)
                applied_summaries.append(a["summary"])
                _record_goal_fact(family_id, a)
                _record_provenance(family_id, rc, "conflict_overwrite",
                                   matched_id=rc.matched_id, prev_value=rc.archive_value)
            else:
                # 多匹配歧义：宁可让用户确认，也不替用户猜哪一笔该覆盖 → 不动
                skip_notes.append(f"{a['summary']} 档案有多笔记录，未自动改动")
                _record_provenance(family_id, rc, "conflict_ambiguous")
            continue
        db.apply_action(family_id, a)
        applied_summaries.append(a["summary"])
        _record_goal_fact(family_id, a)
        _record_provenance(family_id, rc, "new")
    if applied_summaries:
        message = f"已记录：{'、'.join(applied_summaries)}。"
    else:
        message = "没有新的信息需要记录。"
    if skip_notes:
        message += "（" + "；".join(skip_notes) + "）"
    return AppliedResponse(type="applied", message=message)
