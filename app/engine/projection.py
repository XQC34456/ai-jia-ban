"""Wealth Engine · 长期财富投影：确定性年度现金流模型（非 Monte Carlo）。

假设参数全部显式传入，绝不由 LLM 生成或计算。旧函数（future_value /
project_net_worth）保留作简化的恒定复利工具；project_wealth 是完整年度模型，
retirement_funding_ratio 是其上的养老资金覆盖比。
"""
from __future__ import annotations

__all__ = ["future_value", "project_net_worth", "project_wealth",
           "retirement_funding_ratio", "DEFAULT_ASSUMPTIONS"]

# 完整年度模型的默认假设（可被调用方覆盖）
DEFAULT_ASSUMPTIONS = {
    "inflation": 0.03,              # 年通胀率
    "return_rate": 0.05,            # 年化收益率（恒定）
    "income_growth": 0.03,          # 收入年增长率（退休前）
    "expense_growth": 0.02,         # 支出年增长率（退休前）
    "retirement_age": 60,           # 退休年龄
    "retirement_expense_ratio": 0.7,  # 退休后支出占当前年支出的比例
    "pension_income": 0.0,          # 退休后每月养老金
    "life_expectancy": 90,          # 预期寿命（投影终点）
}


def future_value(amount: float, annual_return: float, years: int) -> float:
    """一笔金额按年化收益率复利 years 年后的终值。"""
    return amount * (1 + annual_return) ** years


def project_net_worth(net_worth: float, monthly_surplus: float, annual_return: float, years: int) -> list[float]:
    """年末净资产序列（长度 years+1，首项为当前净资产）。

    每年：先按收益率增长，再加当年结余（monthly_surplus * 12）。
    """
    seq = [net_worth]
    for _ in range(years):
        net_worth = net_worth * (1 + annual_return) + monthly_surplus * 12
        seq.append(round(net_worth, 2))
    return seq


def project_wealth(net_worth: float, annual_income: float, annual_expense: float,
                   current_age: int, assumptions: dict | None = None) -> list[dict]:
    """完整年度确定性财富投影，返回逐年记录（长度 = 预期寿命 - 当前年龄 + 1）。

    逐年规则（确定性、单一路径，明确不是 Monte Carlo）：
    - 退休前（age < retirement_age）：
        收入 = annual_income × (1 + income_growth)^t
        支出 = annual_expense × (1 + expense_growth)^t
        养老金 = 0
    - 退休后（age >= retirement_age）：
        工资收入 = 0
        支出 = annual_expense × retirement_expense_ratio × (1 + inflation)^t
        养老金 = pension_income × 12
    - 结余 = 收入 + 养老金 - 支出
    - 净资产(t) = 净资产(t-1) × (1 + return_rate) + 结余(t)  （第 0 年不滚动）

    每年返回 {year, age, income, expense, pension, surplus, net_worth}。
    """
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    years = max(int(a["life_expectancy"]) - current_age, 0)
    seq: list[dict] = []
    nw = float(net_worth)
    for t in range(years + 1):
        age = current_age + t
        if age < a["retirement_age"]:
            income = annual_income * (1 + a["income_growth"]) ** t
            expense = annual_expense * (1 + a["expense_growth"]) ** t
            pension = 0.0
        else:
            income = 0.0
            expense = annual_expense * a["retirement_expense_ratio"] * (1 + a["inflation"]) ** t
            pension = a["pension_income"] * 12
        surplus = income + pension - expense
        if t > 0:
            nw = nw * (1 + a["return_rate"]) + surplus
        seq.append({
            "year": t,
            "age": age,
            "income": round(income, 2),
            "expense": round(expense, 2),
            "pension": round(pension, 2),
            "surplus": round(surplus, 2),
            "net_worth": round(nw, 2),
        })
    return seq


def retirement_funding_ratio(net_worth: float, annual_income: float, annual_expense: float,
                             current_age: int, assumptions: dict | None = None) -> dict:
    """Retirement Funding Ratio = 退休时点预计净资产 / 退休后资金需求现值。

    基于确定性投影（非 Monte Carlo）：
    - 退休时点净资产：project_wealth 到退休那年的 net_worth
    - 退休后需求：退休→预期寿命期间，每年现金流缺口（支出 - 养老金）按
      return_rate 折现到退休时点求和
    - RFR ≥ 1 视为养老资金充足（满分 100）
    """
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    retirement_age = int(a["retirement_age"])
    life_expectancy = int(a["life_expectancy"])
    seq = project_wealth(net_worth, annual_income, annual_expense, current_age, a)
    retire_year = max(retirement_age - current_age, 0)
    nw_at_retirement = seq[min(retire_year, len(seq) - 1)]["net_worth"]

    need_pv = 0.0
    n = max(life_expectancy - retirement_age, 0)
    for k in range(n):
        expense = annual_expense * a["retirement_expense_ratio"] * (1 + a["inflation"]) ** (retire_year + k)
        pension = a["pension_income"] * 12
        shortfall = max(expense - pension, 0.0)
        need_pv += shortfall / (1 + a["return_rate"]) ** k

    rfr = nw_at_retirement / need_pv if need_pv > 0 else None
    return {
        "retirement_age": retirement_age,
        "net_worth_at_retirement": round(nw_at_retirement, 2),
        "retirement_need_pv": round(need_pv, 2),
        "funding_ratio": round(rfr, 2) if rfr is not None else None,
        "score": round(max(0.0, min(100.0, (rfr or 0.0) * 100))) if rfr is not None else 40,
    }
