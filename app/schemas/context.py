"""AdvisorContext 契约层（Phase 1b · Step 2）：页面提交层 + 解析层双层 schema。

依据：docs/design-advisor-context.md（用户 2026-08-15 锁定）。
铁律（设计 §0，冻结）：
1. Context 是「用户为什么来问」的结构化输入，不是额外提示词。
2. Context 不是新的计算来源：payload 只放「标识」+「用户新声明的事实」，绝不放
   聚合数字（gap/score/dti/rfr/monthly_need…）。所有金额、评分、缺口、比率只能来自
   Engine/Decision 的确定性结果（T4 硬红线）。
3. 判定口诀：payload 里的值如果「删掉它 Advisor 也能从家庭数据里拿到」，就不该传。

生命周期（设计 §1）：
- 页面提交层 AdvisorContextRequest：前端 → 后端（AgentRequest.context 原为空转，论断 #8）。
- 解析层 AdvisorContext：converse() 入口一次性构建，随六阶段循环传递、逐阶段积累。
  family_state = Engine 已确认数据（db.dump_family 原始明细，唯一事实源）；
  missing = 缺数检测产出；evidence = Evidence 阶段产出（预留 P1.3）。
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .. import db

logger = logging.getLogger(__name__)

__all__ = [
    "SOURCE_KINDS", "QUESTION_SOURCES", "SOURCE_PAYLOAD_WHITELIST",
    "AdvisorContextRequest", "AdvisorContext",
    "build_advisor_context", "detect_missing",
]

# 提问面来源（G1 解法，设计 §3）：这些页面天然是「提问」，建档判定不参与意图。
# 页面入口是构造事实（用户在看什么 → 在提问），而非启发式猜测。
QUESTION_SOURCES = ("goals", "retirement", "allocation", "sandbox", "overview")

SOURCE_KINDS = Literal["goals", "retirement", "allocation", "sandbox", "overview", "chat"]

# 各来源 payload 白名单（设计 §2 最小化原则，T6）：
# 只允许「标识」（指向 Engine 已有数据）+「用户新声明的事实」（用户刚说出口的信息）。
# 空白名单（overview/chat）→ payload 一律清空。
SOURCE_PAYLOAD_WHITELIST: dict[str, set[str]] = {
    "goals": {"goal_id", "goal_type"},
    "retirement": {"retire_age"},
    "allocation": {"target_alloc"},
    "sandbox": {"scenario_id", "scenario_name"},
    "overview": set(),
    "chat": set(),
}


class AdvisorContextRequest(BaseModel):
    """前端 → 后端：页面告诉顾问「用户在看什么、想解决什么」。

    对应 AgentRequest.context（原为空转字段，论断 #8，现已进入决策链）。
    payload 经白名单剥离禁止字段（T6）：聚合数字要么丢弃、要么留待 Engine 重算。
    """
    source: SOURCE_KINDS = "chat"
    intent_hint: str | None = None      # 页面建议的第一轮意图（SEED，非 OVERRIDE，见设计 §3）
    query: str | None = None            # 用户真正想解决的问题（缺省 = 本次 message）
    payload: dict[str, Any] = Field(default_factory=dict)  # 标识 + 用户新声明事实
    first_turn_action: str | None = None  # 顾问第一轮应该做什么（暂只记录，不消费）

    @model_validator(mode="after")
    def _strip_forbidden_payload(self) -> "AdvisorContextRequest":
        """白名单剥离（T6）：禁止字段绝不静默接受，记日志供审计。"""
        allowed = SOURCE_PAYLOAD_WHITELIST.get(self.source, set())
        stripped = [k for k in self.payload if k not in allowed]
        if stripped:
            logger.info("AdvisorContext: source=%s payload 剥离禁止字段 %s",
                        self.source, sorted(stripped))
        self.payload = {k: v for k, v in self.payload.items() if k in allowed}
        return self


class AdvisorContext(BaseModel):
    """解析层：converse() 入口一次性构建，随六阶段循环传递、逐阶段积累。

    数字字段只由系统确定性写入——request.payload 永不进入 evidence/metrics（T4 硬红线）。
    """
    request: AdvisorContextRequest
    family_state: dict[str, Any] | None = None   # Engine 已确认家庭数据（db.dump_family）
    missing: list[str] = Field(default_factory=list)   # 缺数检测产出（P1.3 底座）
    evidence: list[dict] = Field(default_factory=list)  # Evidence 阶段产出（预留）

    @property
    def query(self) -> str:
        """归一后的用户问题：request.query 缺省回退 message（G3「原问题不丢」底座）。"""
        return self.request.query or ""


def build_advisor_context(message: str, user: dict,
                          raw: dict | None = None) -> AdvisorContext:
    """converse() 入口一次性构建解析层 Context。

    1) 解析 + 白名单剥离请求（T6）；
    2) query 归一：request.query or message（跨取消存活的原问题，G3）；
    3) family_state = Engine 已确认数据（db.dump_family 原始明细，唯一事实源）。

    本模块位于 schemas/ 但承担「解析层构建」，故需读 db —— 这是 Context 阶段的
    Context 职责（读档案先于 intent），不是输出契约职责。
    """
    req = AdvisorContextRequest(**(raw or {}))
    if not req.query:
        req = req.model_copy(update={"query": message})
    family_state = db.dump_family(user["family_id"])
    return AdvisorContext(request=req, family_state=family_state)


def detect_missing(ctx: AdvisorContext, intent: str) -> list[str]:
    """缺数检测底座（P1.3）：只返回影响答案的最小缺失项，绝不含已确认事实（#4）。

    当前覆盖现金流两维（收入/支出）：family_state 已有 → 不追问。
    intent 维度留 P1.3 扩展（按意图圈定「影响该答案」的缺失项）；返回空 = 无缺数。
    """
    fs = ctx.family_state or {}
    cashflows = fs.get("cashflows") or []
    has_income = any(c.get("flow_type") == "income" for c in cashflows)
    has_expense = any(c.get("flow_type") == "expense" for c in cashflows)
    missing: list[str] = []
    if not has_income:
        missing.append("月收入")
    if not has_expense:
        missing.append("月支出")
    return missing
