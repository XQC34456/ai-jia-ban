"""AI Agent 契约层（A1）：冻结意图 → 端点映射与 Agent 输出 Schema。

本层只定义契约，不包含任何 LLM / 计算逻辑。AI Agent 是交互智能层，
不是财富计算层——它只读 API 返回，绝不自行计算财富数字。

场景别名受 SCENARIO_NAMES 约束：新增场景时先改 C3.5 场景契约，
再由 test_agent_contract 迫使本层同步，而非本层自行扩展。
"""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "AGENT_INTENTS", "INTENT_TO_ENDPOINT", "INTENT_SUBFIELD", "SCENARIO_ALIASES",
    "MetricRef", "AgentResponse",
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
