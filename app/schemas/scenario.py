"""情景模拟 Schema：统一 Scenario API 的输入/输出契约（API v1 Contract Freeze）。

这里是 C3 财富沙盘参数与对比结果的唯一契约来源，供前端 / AI Agent / OpenAPI 共同读取：
- SCENARIO_NAMES / SCENARIO_METRICS / SCENARIO_PARAM_MODELS 为显式契约常量，
  与 engine 的枚举一一对应（有守门测试锁定，见 tests/test_scenario_contract.py）。
- 参数校验采用「Pydantic 强模型」：类型/范围错误 → 422；业务不可执行（如首付超现金）→ 400。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .wealth import Overview

__all__ = [
    "SCENARIO_NAMES", "SCENARIO_METRICS", "SCENARIO_METRIC_KEYS", "SCENARIO_PARAM_MODELS",
    "ScenarioRequest", "CompareOption", "CompareRequest",
    "ComparisonMetric", "CompareOptionOverview", "CompareResponse",
    "BuyHouseParams", "PrepayParams", "InvestParams", "IncomeChangeParams",
]

# ---------- 契约常量：与 engine 一一对应，禁止单方面修改 ----------

# 引擎支持的情景名（engine.scenario.SCENARIOS 的键），C3 沙盘唯一合法 Scenario。
SCENARIO_NAMES = ("buy_house", "prepay", "invest", "income_change")

# 九指标冻结：key / 中文名 / 单位。顺序即前端对比表行序，禁止增删改。
SCENARIO_METRICS = (
    ("net_worth", "净资产", "money"),
    ("wealth_score", "财富评分", "score"),
    ("rfr", "养老可投资覆盖 RFR", "ratio"),
    ("nwc", "养老净资产覆盖 NWC", "ratio"),
    ("cashflow", "月度现金流结余", "money"),
    ("liquidity", "应急资金（月）", "months"),
    ("dti", "负债率 DTI", "pct"),
    ("real_estate_pct", "房产占比", "pct"),
    ("goal_completion", "目标完成度", "pct"),
)
SCENARIO_METRIC_KEYS = tuple(k for k, _, _ in SCENARIO_METRICS)


# ---------- 情景参数强模型（Pydantic，422 层） ----------

class BuyHouseParams(BaseModel):
    """买房：冻结当前资产负债表口径的 apply 参数（不含投影参数）。"""
    price: float = Field(gt=0, description="房价（元）")
    down_payment_ratio: float = Field(default=0.3, gt=0, lt=1, description="首付比例（0~1）")
    loan_rate: float = Field(default=0.0, ge=0, description="贷款利率，>1 视为百分数（3.5→0.035）")
    loan_years: int = Field(default=30, ge=1, le=50, description="贷款年限（1~50）")


class PrepayParams(BaseModel):
    """提前还贷：缩短年限或减少月供。"""
    prepay_amount: float = Field(gt=0, description="提前还款金额（元）")
    method: Literal["shorten", "reduce_payment"] = "shorten"


class InvestParams(BaseModel):
    """投资：划出流动现金投入指定资产大类。"""
    amount: float = Field(gt=0, description="投资金额（元）")
    to_class: Literal["cash", "fixed_income", "equity", "real_estate", "alternative", "other"] = "equity"


class IncomeChangeParams(BaseModel):
    """收入变化：所有收入现金流 × (1 + pct_change)。"""
    pct_change: float = Field(gt=-1, description="收入变动幅度（如 0.1 = +10%）")


SCENARIO_PARAM_MODELS = {
    "buy_house": BuyHouseParams,
    "prepay": PrepayParams,
    "invest": InvestParams,
    "income_change": IncomeChangeParams,
}


# ---------- 请求体 ----------

class ScenarioRequest(BaseModel):
    """情景投影请求体（旧接口 /scenario/{name}，参数自由，暂不冻结）。"""
    params: dict = Field(default_factory=dict)


class CompareOption(BaseModel):
    """对比方案：同一场景下的不同参数组合。id 唯一标识，name 为展示名。

    params 在 Schema 层保持 dict（因为场景名在 URL path，不在 body），
    由 /compare 端点按 SCENARIO_PARAM_MODELS[name] 做强校验。
    """
    id: str
    name: str | None = None
    params: dict = Field(default_factory=dict)


class CompareRequest(BaseModel):
    """对比请求体：至少一个方案，每个方案独立 apply 自同一 baseline。"""
    options: list[CompareOption]


# ---------- 响应体（Compare 契约冻结） ----------

class ComparisonMetric(BaseModel):
    """单个对比维度的展示差值（非财富计算，仅字段选取 + 减法）。"""
    key: str
    label: str
    unit: str
    baseline: float | None = None
    option: float | None = None
    delta: float | None = None


class CompareOptionOverview(BaseModel):
    """一个方案：id / 展示名 / 完整 Overview（由 build_overview 重算）。"""
    id: str
    name: str | None = None
    overview: Overview


class CompareResponse(BaseModel):
    """对比结果：baseline + 多方案 + 每方案 9 指标差值。"""
    scenario: str
    baseline: Overview
    options: list[CompareOptionOverview]
    comparison: dict[str, list[ComparisonMetric]]
