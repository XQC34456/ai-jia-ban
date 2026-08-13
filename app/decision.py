"""决策模拟器：把「要不要买房 / 提前还贷」量化成两方案财务对比。

纯确定性计算（与 calc_engine 同风格），不调用 LLM。所有公式可审计、可单测。
"""
from __future__ import annotations

import math
from typing import Any

from . import calc_engine as ce
from . import db

_LIQUID = ce.LIQUID_ASSET_TYPES


# ---------- 等额本息公式 ----------

def _payment_months(principal: float, annual_rate: float, months: int) -> float:
    """等额本息月供（给定期数）。"""
    r = annual_rate / 12.0
    if months <= 0:
        return 0.0
    if r <= 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    return _payment_months(principal, annual_rate, int(years * 12))


def remaining_principal(principal: float, annual_rate: float, years: int, months_paid: int) -> float:
    """等额本息还款 months_paid 期后的剩余本金。"""
    r = annual_rate / 12.0
    n = years * 12
    if r <= 0:
        return principal * (1 - months_paid / n) if n else 0.0
    m = monthly_payment(principal, annual_rate, years)
    return principal * (1 + r) ** months_paid - m * ((1 + r) ** months_paid - 1) / r


def months_to_clear(principal: float, annual_rate: float, payment: float) -> int:
    """月供不变时，还清所需月数。"""
    r = annual_rate / 12.0
    if r <= 0:
        return int(math.ceil(principal / payment)) if payment > 0 else 10 ** 9
    if payment <= principal * r:
        return 10 ** 9  # 月供不够覆盖利息，永远还不清
    return int(math.ceil(-math.log(1 - principal * r / payment) / math.log(1 + r)))


def _rate(v: Any) -> float:
    """利率归一化：>1 视为百分数（3.5 → 0.035），否则视为小数。"""
    if not v:
        return 0.0
    r = float(v)
    return r / 100.0 if r > 1 else r


# ---------- 场景：买房 ----------

def simulate_buy_house(data: dict[str, Any], snap: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    price = float(p.get("price") or 0)
    down_ratio = float(p.get("down_payment_ratio") or 0.3)
    loan_rate = _rate(p.get("loan_rate"))
    loan_years = int(p.get("loan_years") or 30)
    house_growth = _rate(p.get("house_growth"))
    current_rent = float(p.get("current_rent") or 0)
    horizon = int(p.get("horizon_years") or 10)

    if price <= 0:
        return {"scenario": "buy_house", "title": "买房决策", "error": "请填写房价"}

    down = price * down_ratio
    loan = price - down
    payment = monthly_payment(loan, loan_rate, loan_years)

    liquid = sum(float(a.get("value") or 0) for a in data.get("assets", []) if a.get("type") in _LIQUID)

    surplus_a = float(snap["monthly_surplus"] or 0)
    net_a = float(snap["net_worth"] or 0) + surplus_a * 12 * horizon

    surplus_b = surplus_a + current_rent - payment
    house_final = price * (1 + house_growth) ** horizon
    rem_loan = remaining_principal(loan, loan_rate, loan_years, horizon * 12)
    net_b = float(snap["net_worth"] or 0) + (house_final - price) + (loan - rem_loan) + surplus_b * 12 * horizon

    exp_a = float(snap["monthly_expense"] or 0)
    exp_b = exp_a - current_rent + payment
    em_a = snap["emergency_months"]
    em_b = round((liquid - down) / exp_b, 1) if (exp_b > 0 and liquid - down > 0) else None

    net_diff = net_b - net_a
    return {
        "scenario": "buy_house",
        "title": "买房决策",
        "plan_a_label": "不买房（继续现状）",
        "plan_b_label": "买房",
        "summary": [
            {"label": "首付", "value": round(down, 2), "money": True},
            {"label": "月供", "value": round(payment, 2), "money": True},
            {"label": "当前租金", "value": round(current_rent, 2), "money": True},
        ],
        "rows": [
            {"label": f"{horizon} 年后净资产", "a": round(net_a, 2), "b": round(net_b, 2), "money": True, "highlight": True},
            {"label": "每月结余", "a": round(surplus_a, 2), "b": round(surplus_b, 2), "money": True},
            {"label": "应急资金（月）", "a": em_a, "b": em_b, "months": True},
        ],
        "conclusion": _buy_conclusion(horizon, net_diff, surplus_b),
    }


def _buy_conclusion(horizon: int, net_diff: float, surplus_b: float) -> str:
    if net_diff > 0:
        main = f"从 {horizon} 年后的净资产看，买房方案预计比不买房多 {net_diff:,.0f} 元"
    else:
        main = f"按设定的房价涨幅，{horizon} 年后买房方案的净资产反而比不买房少 {abs(net_diff):,.0f} 元"
    if surplus_b < 0:
        cash = "；但买房后月结余为负，现金流压力较大，需谨慎"
    else:
        cash = f"；买房后每月仍结余 {surplus_b:,.0f} 元，现金流可承受"
    return main + cash + "。以上为简化测算，未计入税费、装修及交易成本，仅供参考。"


# ---------- 场景：提前还贷 ----------

def simulate_prepay(data: dict[str, Any], snap: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    prepay = float(p.get("prepay_amount") or 0)
    method = p.get("method") or "shorten"

    mort = next((l for l in data.get("liabilities", []) if l.get("type") == "房贷"), None)
    if mort is None:
        return {"scenario": "prepay", "title": "提前还贷",
                "error": "还没有房贷记录，请先在「负债」页添加一条房贷（含剩余本金、月供、利率、剩余期数）"}

    principal = float(mort.get("principal") or 0)
    rate = _rate(mort.get("interest_rate"))
    months = int(mort.get("remaining_months") or 0)
    payment_given = float(mort.get("monthly_payment") or 0)

    if principal <= 0:
        return {"scenario": "prepay", "title": "提前还贷",
                "error": "房贷缺「剩余本金」，请先在「负债」页补全"}
    if prepay <= 0:
        return {"scenario": "prepay", "title": "提前还贷", "error": "请填写提前还款金额"}
    if months <= 0:
        if payment_given <= 0:
            return {"scenario": "prepay", "title": "提前还贷",
                    "error": "房贷缺「剩余期数」或「月供」，请先在「负债」页补全"}
        months = months_to_clear(principal, rate, payment_given)

    # 用本金 + 利率 + 期数重算基准月供，保证内部自洽（不直接信用户手填的月供）
    payment = _payment_months(principal, rate, months)

    new_principal = max(principal - prepay, 0.0)
    interest_a = payment * months - principal

    if new_principal <= 0:
        # 直接还清
        new_payment, new_months, interest_b = 0.0, 0, 0.0
    elif method == "shorten":
        # 月供不变，缩短年限
        new_payment = payment
        new_months = months_to_clear(new_principal, rate, payment)
        interest_b = new_payment * new_months - new_principal
    else:
        # 减少月供，年限不变
        new_payment = _payment_months(new_principal, rate, months)
        new_months = months
        interest_b = new_payment * new_months - new_principal

    saved = max(interest_a - interest_b, 0.0)
    months_saved = months - new_months

    if new_principal <= 0:
        concl = f"提前还 {prepay:,.0f} 元即可全部还清，省下剩余利息约 {saved:,.0f} 元。"
    elif method == "shorten":
        concl = (f"提前还 {prepay:,.0f} 元，预计省下利息约 {saved:,.0f} 元，"
                 f"还清时间提前约 {months_saved} 个月。")
    else:
        concl = (f"提前还 {prepay:,.0f} 元，预计省下利息约 {saved:,.0f} 元，"
                 f"月供从 {payment:,.0f} 元降到 {new_payment:,.0f} 元。")

    return {
        "scenario": "prepay",
        "title": "提前还贷",
        "plan_a_label": "不提前还",
        "plan_b_label": "提前还",
        "summary": [
            {"label": "提前还款", "value": round(prepay, 2), "money": True},
            {"label": "省下利息", "value": round(saved, 2), "money": True},
        ],
        "rows": [
            {"label": "每月月供", "a": round(payment, 2), "b": round(new_payment, 2), "money": True},
            {"label": "总利息支出", "a": round(interest_a, 2), "b": round(interest_b, 2), "money": True, "highlight": True},
            {"label": "还清所需（月）", "a": months, "b": new_months, "months": True},
        ],
        "conclusion": concl,
    }


# ---------- 编排入口 ----------

def simulate(family_id: int, scenario: str, params: dict[str, Any]) -> dict[str, Any]:
    data = db.dump_family(family_id)
    snap = ce.snapshot(data)
    if scenario == "buy_house":
        return simulate_buy_house(data, snap, params)
    if scenario == "prepay":
        return simulate_prepay(data, snap, params)
    return {"scenario": scenario, "title": "决策模拟", "error": f"未知场景: {scenario}"}
