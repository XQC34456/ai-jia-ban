"""Wealth Engine · 长期财富投影：明确假设参数的确定性复利模型。

假设参数（全部显式传入，绝不由 LLM 生成或计算）：
- annual_return：年化收益率（小数，0.03 = 3%），简化为恒定复利；
- monthly_surplus：每月结余（恒定，按年累加计入年末净资产）；
- years：投影年数。
"""
from __future__ import annotations

__all__ = ["future_value", "project_net_worth"]


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
