"""养老四象限：RFR × NWC 交叉定位，回答「我到底有没有钱养老」。

        NWC < 1          NWC ≥ 1
RFR<1   养老资金不足     资产充足但流动性不足
RFR≥1   高杠杆/结构问题  养老健康
"""
from __future__ import annotations

__all__ = ["retirement_quadrant"]


def retirement_quadrant(rfr: float | None, nwc: float | None) -> str:
    """由 RFR（可投资资产口径）与 NWC（净资产口径）判定养老四象限。"""
    if rfr is None or nwc is None:
        return "未知"
    if rfr >= 1 and nwc >= 1:
        return "养老健康"
    if rfr < 1 and nwc >= 1:
        return "资产充足但流动性不足"
    if rfr < 1 and nwc < 1:
        return "养老资金不足"
    return "高杠杆/资产结构问题"
