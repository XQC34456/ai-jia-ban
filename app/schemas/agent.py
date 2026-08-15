"""AI Agent 契约层（A1）：冻结意图 → 端点映射与 Agent 输出 Schema。

本层只定义契约，不包含任何 LLM / 计算逻辑。AI Agent 是交互智能层，
不是财富计算层——它只读 API 返回，绝不自行计算财富数字。

场景别名受 SCENARIO_NAMES 约束：新增场景时先改 C3.5 场景契约，
再由 test_agent_contract 迫使本层同步，而非本层自行扩展。
"""
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "AGENT_INTENTS", "INTENT_TO_ENDPOINT", "INTENT_SUBFIELD", "SCENARIO_ALIASES",
    "MetricRef", "PriorityRef", "EvidenceRef", "TradeoffRef", "UncertaintyRef",
    "FollowUpRef", "ActionPlanRef", "ChartBlock", "AdvisorLayers",
    "AgentResponse", "AgentRequest",
]

# ---------- ① 七意图冻结（A0） ----------

AGENT_INTENTS = (
    "VIEW_OVERVIEW",
    "CHECK_ISSUES",
    "CHECK_RETIREMENT",
    "CHECK_ALLOCATION",
    "CHECK_GOALS",
    "SCENARIO_COMPARE",
    "EXPLAIN_RESULT",
)

# ---------- ② 意图 → 唯一端点（LLM 永不自由拼 endpoint） ----------
# 每个意图唯一映射到已存在路由；EXPLAIN_RESULT 纯解释、复用上下文、无端点。
INTENT_TO_ENDPOINT = {
    "VIEW_OVERVIEW": ("GET", "/api/wealth/overview"),
    "CHECK_ISSUES": ("GET", "/api/wealth/issues"),
    "CHECK_RETIREMENT": ("GET", "/api/wealth/overview"),   # 读 .retirement 子区块
    "CHECK_ALLOCATION": ("GET", "/api/wealth/overview"),    # 读 .asset_allocation 子区块
    "CHECK_GOALS": ("GET", "/api/wealth/goals"),
    "SCENARIO_COMPARE": ("POST", "/api/wealth/scenario/{name}/compare"),
    "EXPLAIN_RESULT": None,
}

# 读 /overview 子区块的意图 → 对应字段路径（不新增端点，只读已存在字段）
INTENT_SUBFIELD = {
    "CHECK_RETIREMENT": "retirement",
    "CHECK_ALLOCATION": "asset_allocation",
}

# ---------- 场景别名 → 冻结场景名（值严格受 SCENARIO_NAMES 约束） ----------
SCENARIO_ALIASES = {
    "买房": "buy_house",
    "提前还贷": "prepay",
    "投股票": "invest",
    "投资": "invest",
    "收入下降": "income_change",
}


# ---------- Agent 输出 Schema（防编造） ----------

class MetricRef(BaseModel):
    """一个被引用的指标数值。value 非空时 source 必填，杜绝无出处数字。"""
    key: str
    label: str
    unit: str
    value: float | None = None
    source: str | None = None       # 数字出处：API 返回字段路径，如 "overview.retirement.rfr"

    @model_validator(mode="after")
    def _value_needs_source(self):
        """防编造硬闸：带数值的指标必须给出出处字段路径。"""
        if self.value is not None and not self.source:
            raise ValueError("带数值的指标必须提供 source 字段路径")
        return self


# ---------- V2.3 Advisor Brain 新增（只扩不减，全部 optional / default 空） ----------

class PriorityRef(BaseModel):
    """主要矛盾：来自 Decision build_issues 的 priorities（确定性，LLM 不判断）。"""
    issue_id: str
    severity: str            # P0/P1/P2
    title: str
    finding: str             # 为什么（来自 issue.finding，逐字透传）


class EvidenceRef(BaseModel):
    """证据→判断链：claim 是 LLM 的定性判断，metric 是系统注入的带 source 数字。"""
    claim: str
    metric: MetricRef


class TradeoffRef(BaseModel):
    """权衡：帮用户看清取舍，不制造最佳方案。"""
    option: str
    gain: str                # 得到什么
    loss: str                # 失去什么


class UncertaintyRef(BaseModel):
    """不确定性表达：信息不足 / 备选解释，绝不假装确定。"""
    confidence: Literal["high", "medium", "low"] = "medium"
    missing: list[str] = Field(default_factory=list)        # 信息缺口
    alternatives: list[str] = Field(default_factory=list)   # 备选解释


class FollowUpRef(BaseModel):
    """结构化追问：系统检测到的信息缺口（question 是要问用户的问题，reason 是为什么缺）。"""
    question: str
    reason: str


class ActionPlanRef(BaseModel):
    """⑤ 下一步里可采纳的建议：来自 Decision recommendations（确定性），供前端「＋采纳」落地 action_plan。"""
    recommendation_id: str
    issue_id: str
    action: str
    detail: str | None = None


# ---------- V2.6 五层结构化回答契约：系统层 vs LLM 叙事层分离 ----------

class ChartBlock(BaseModel):
    """③ 财务画像证据块：一张图回答一个明确财务问题，data 是确定性 overview 子块原样搬运。"""
    chart: str                 # 对应 charts.js 组件名（radar/cashflow/allocation/debt/protection/goals/retirement）
    question: str              # 该图回答的财务问题（人话）
    data: Any = None           # 确定性数据块（overview 对应子块，绝无计算）


class AdvisorLayers(BaseModel):
    """五层结构化回答。系统层（①结论②变化③画像⑤行动）全部来自确定性 overview/review-status；
    LLM 叙事层（④判断）复用 AgentResponse.finding（数字已剥离）。"""
    conclusion: str | None = None                       # ① 结论（wealth_level + 主要矛盾）
    changes: list[dict] = Field(default_factory=list)   # ② 关键变化（review-status stale_reasons）
    charts: list[ChartBlock] = Field(default_factory=list)  # ③ 财务画像（按用户问题触发）
    judgment: str | None = None                         # ④ 我的判断（LLM 叙事层）
    action_plan: list[str] = Field(default_factory=list)   # ⑤ 下一步行动（人话短句，向后兼容）
    action_plans: list[ActionPlanRef] = Field(default_factory=list)  # ⑤ 可采纳结构（P1.4，供「＋采纳」落地）


class AgentResponse(BaseModel):
    """Agent 结构化输出：所有数字来自 API 返回，禁止编造字段。"""
    intent: Literal[AGENT_INTENTS]
    status: Literal["ok", "need_clarification", "refused", "error"]
    summary: str
    finding: str | None = None
    metrics: list[MetricRef] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)   # 原样透传 known_limitations
    source: list[str] = Field(default_factory=list)
    # ---- V2.3 新增 ----
    priorities: list[PriorityRef] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    tradeoffs: list[TradeoffRef] = Field(default_factory=list)
    uncertainty: UncertaintyRef | None = None
    # ---- V2.6 新增（只扩不减，缺省 None → 前端走旧扁平渲染兜底） ----
    layers: AdvisorLayers | None = None
    # ---- P1.2 新增：情景对比原始 comparison（{"A": [9行 baseline/option/delta], ...}），
    #      供 layers 生成 scenario_compare 证据图；缺省 None（非情景意图 / 无对比）。 ----
    scenario_comparison: dict | None = None
    # ---- P1.3 新增：结构化追问（系统缺数检测，非 LLM 编造）。缺省空列表。 ----
    follow_up_questions: list[FollowUpRef] = Field(default_factory=list)


class AgentRequest(BaseModel):
    """Agent 自然语言请求体。message 必填（1~2000 字），context 供 EXPLAIN_RESULT 复用。"""
    message: str = Field(min_length=1, max_length=2000)
    context: dict | None = None


# ---------- 建档确认卡片（Phase 6C 吸收 V1 建档能力，非七意图、非 AgentResponse） ----------

class ConfirmCard(BaseModel):
    """建档确认卡片：抽取到动作后返回，等用户在 /api/confirm 确认落地。"""
    type: Literal["confirm"] = "confirm"
    pending_id: str
    message: str
    items: list[str] = Field(default_factory=list)
    groups: list[dict] = Field(default_factory=list)   # V27.1 分组展示（只扩不减）


class AppliedResponse(BaseModel):
    """建档确认落地结果。type ∈ applied / discarded / error。"""
    type: Literal["applied", "discarded", "error"]
    message: str
