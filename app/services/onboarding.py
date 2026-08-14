"""冷启动典型值构造：把粗画像档位映射成 build_overview 可消费的 family_data。

铁律：
  - 纯函数、零数据库依赖、绝不写库。
  - 只生成「演示用典型家庭」的假设输入，结论（wealth_score/net_worth/issues）由 build_overview 实算。
  - 典型值不是用户真实财务数据，UI 必须明确声明「仅用于体验和演示」。
"""
from __future__ import annotations

# 档位 → (总资产, 月收入, 负债本金, 储蓄率)
TYPICAL = {
    "high":    (5_000_000, 80_000, 2_000_000, 0.5),
    "mid":     (2_000_000, 30_000, 500_000, 0.3),
    "low":     (500_000, 10_000, 0, 0.1),
    "unknown": (2_000_000, 30_000, 500_000, 0.3),  # 不知道 = mid 中性
}


def typical_family(profile: dict | None = None) -> dict:
    """把粗画像档位映射成 family_data（persons/assets/liabilities/cashflows/...）。"""
    profile = profile or {}
    assets = TYPICAL.get(profile.get("assets", "unknown"), TYPICAL["unknown"])
    income = TYPICAL.get(profile.get("income", "unknown"), TYPICAL["unknown"])
    debt = TYPICAL.get(profile.get("debt", "unknown"), TYPICAL["unknown"])
    savings = TYPICAL.get(profile.get("savings", "unknown"), TYPICAL["unknown"])

    total_assets, monthly_income, debt_principal, savings_rate = (
        assets[0], income[1], debt[2], savings[3],
    )
    deposit = total_assets * 0.4
    house = total_assets * 0.6
    expense = monthly_income * (1 - savings_rate)

    return {
        "family": {"name": "示例家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1990, "monthly_income": monthly_income}],
        "assets": [
            {"type": "存款", "name": "现金", "value": deposit},
            {"type": "房产", "name": "自住房", "value": house},
        ],
        "liabilities": (
            [{"type": "房贷", "name": "房贷", "principal": debt_principal,
              "monthly_payment": round(debt_principal * 0.005, 2), "interest_rate": 3.5, "remaining_months": 300}]
            if debt_principal > 0 else []
        ),
        "cashflows": [
            {"flow_type": "income", "category": "工资", "amount": monthly_income, "period": "月"},
            {"flow_type": "expense", "category": "日常", "amount": round(expense, 2), "period": "月"},
        ],
        "goals": [], "reminders": [], "insurance": [], "family_profile": None,
    }
