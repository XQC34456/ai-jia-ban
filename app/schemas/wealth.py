"""Wealth Overview Schema：家庭财富驾驶舱的完整 JSON Contract。

这是 /api/wealth/overview 的响应结构——前端只消费这一个对象，不自行计算财富逻辑。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .goal import GoalOut
from .issue import Issue, Recommendation

__all__ = [
    "CashflowBlock", "LiquidityBlock", "DebtBlock", "ProtectionBlock",
    "RetirementBlock", "Overview",
]


class CashflowBlock(BaseModel):
    income: float = 0.0          # 月收入
    expense: float = 0.0         # 月支出（含月供）
    surplus: float = 0.0         # 月结余
    savings_rate: float | None = None
    breakdown: dict = Field(default_factory=dict)   # {incomes:[{category,amount}], expenses:[{category,amount,kind}]}


class LiquidityBlock(BaseModel):
    liquid_assets: float = 0.0   # 流动现金总额
    emergency_months: float | None = None


class DebtBlock(BaseModel):
    total_debt: float = 0.0
    monthly_payment: float = 0.0
    dti: float | None = None     # 月供 / 月收入
    items: list[dict] = Field(default_factory=list)   # 逐笔负债明细（利率/剩余期限/月供/本金）


class ProtectionBlock(BaseModel):
    insurance_count: int = 0
    total_coverage: float = 0.0
    total_premium: float = 0.0
    coverage_ratio: float | None = None   # 保额 / 年收入
    members: list[dict] = Field(default_factory=list)   # 按成员归组 {name,relation,coverage,premium,policy_count}


class RetirementBlock(BaseModel):
    rfr: float | None = None                    # Retirement Funding Ratio（可投资资产口径）
    nwc: float | None = None                    # Net Worth Coverage（净资产口径）
    quadrant: str = "未知"                      # 四象限结论：养老健康/资产充足但流动性不足/高杠杆资产结构问题/养老资金不足
    investable_at_retirement: float = 0.0
    net_worth_at_retirement: float = 0.0
    retirement_need_pv: float = 0.0
    known_limitations: list[str] = Field(default_factory=list)


class Overview(BaseModel):
    """家庭财富总览：一次返回驾驶舱所需核心状态。"""
    currency: str = "CNY"             # 货币单位：所有金额字段均为人民币（元）
    wealth_score: int = 0
    wealth_level: str = "脆弱"
    dimensions: list[dict] = Field(default_factory=list)   # 7 维健康评分（含 protection），Task 1.1 暴露
    net_worth: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    liquid_assets: float = 0.0

    asset_allocation: dict = Field(default_factory=dict)    # 六大类占比 + 集中度 + 金融口径
    allocation_fitness: int | None = None
    allocation_target: dict = Field(default_factory=dict)   # Σ=100% 点目标

    cashflow: CashflowBlock = Field(default_factory=CashflowBlock)
    liquidity: LiquidityBlock = Field(default_factory=LiquidityBlock)
    debt: DebtBlock = Field(default_factory=DebtBlock)
    protection: ProtectionBlock = Field(default_factory=ProtectionBlock)

    goals: list[GoalOut] = Field(default_factory=list)
    retirement: RetirementBlock | None = None

    issues: list[Issue] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    priorities: list[dict] = Field(default_factory=list)     # 按 P0→P2 排序的问题摘要
    recommendations: list[Recommendation] = Field(default_factory=list)
