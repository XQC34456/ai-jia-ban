"""Wealth Engine · 情景引擎：通用场景框架，每个场景返回两方案对比 + 完整参数快照。

纯确定性计算（与 metrics 同风格），不调用 LLM。每个场景的 params_snapshot
保存规范化后的输入参数，保证每次模拟可复现。
"""
from __future__ import annotations

import math
from typing import Any

from . import allocation, metrics

__all__ = [
    "SCENARIOS", "run_scenario",
    "monthly_payment", "remaining_principal", "months_to_clear",
    "simulate_buy_house", "simulate_prepay", "simulate_invest", "simulate_income_change",
]

_LIQUID = metrics.LIQUID_ASSET_TYPES


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
        "params_snapshot": {"price": price, "down_payment_ratio": down_ratio, "loan_rate": loan_rate,
                            "loan_years": loan_years, "house_growth": house_growth,
                            "current_rent": current_rent, "horizon_years": horizon},
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
        return {"scenario": "prepay", "title": "提前还贷", "error": "房贷缺「剩余本金」，请先在「负债」页补全"}
    if prepay <= 0:
        return {"scenario": "prepay", "title": "提前还贷", "error": "请填写提前还款金额"}
    if months <= 0:
        if payment_given <= 0:
            return {"scenario": "prepay", "title": "提前还贷",
                    "error": "房贷缺「剩余期数」或「月供」，请先在「负债」页补全"}
        months = months_to_clear(principal, rate, payment_given)

    payment = _payment_months(principal, rate, months)

    new_principal = max(principal - prepay, 0.0)
    interest_a = payment * months - principal

    if new_principal <= 0:
        new_payment, new_months, interest_b = 0.0, 0, 0.0
    elif method == "shorten":
        new_payment = payment
        new_months = months_to_clear(new_principal, rate, payment)
        interest_b = new_payment * new_months - new_principal
    else:
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
        "params_snapshot": {"prepay_amount": prepay, "method": method},
    }


# ---------- 场景：投资配置 ----------

def simulate_invest(data: dict[str, Any], snap: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    amount = float(p.get("amount") or 0)
    to_class = p.get("to_class") or "equity"
    if amount <= 0:
        return {"scenario": "invest", "title": "投资配置", "error": "请填写投资金额"}

    liquid = sum(float(a.get("value") or 0) for a in data.get("assets", []) if a.get("type") in _LIQUID)
    total = snap["total_assets"]
    current = allocation.asset_class_breakdown(data.get("assets", []))
    # 方案 B：流动现金减少 amount，目标大类增加 amount
    after = {k: dict(v) for k, v in current.items()}
    after["cash"]["value"] -= amount
    after[to_class]["value"] += amount
    for k in after:
        after[k]["pct"] = round(after[k]["value"] / total, 4) if total > 0 else 0.0

    liquid_after = max(liquid - amount, 0.0)
    exp = metrics.monthly_expense(data.get("cashflows", []), data.get("liabilities", []))
    em_after = round(liquid_after / exp, 1) if exp > 0 else None

    return {
        "scenario": "invest",
        "title": "投资配置",
        "plan_a_label": "维持现状",
        "plan_b_label": f"投资 {amount:,.0f} 元到 {to_class}",
        "summary": [
            {"label": "投资金额", "value": round(amount, 2), "money": True},
            {"label": "目标大类", "value": to_class},
        ],
        "rows": [
            {"label": "流动现金", "a": round(liquid, 2), "b": round(liquid_after, 2), "money": True},
            {"label": f"{to_class} 占比", "a": round(current[to_class]["pct"] * 100, 1),
             "b": round(after[to_class]["pct"] * 100, 1)},
            {"label": "应急资金（月）", "a": snap["emergency_months"], "b": em_after, "months": True},
        ],
        "conclusion": _invest_conclusion(amount, to_class, liquid_after, em_after),
        "params_snapshot": {"amount": amount, "to_class": to_class},
    }


def _invest_conclusion(amount: float, to_class: str, liquid_after: float, em_after: float | None) -> str:
    parts = [f"将 {amount:,.0f} 元投入 {to_class} 后，流动现金降至 {liquid_after:,.0f} 元"]
    if em_after is not None:
        parts.append(f"应急资金覆盖约 {em_after} 个月")
        if em_after < 3:
            parts.append("低于 3 个月安全线，建议保留足够应急金再投资")
    return "；".join(parts) + "。以上为简化测算，未计入交易费用及税费，仅供参考。"


# ---------- 场景：收入变化 ----------

def simulate_income_change(data: dict[str, Any], snap: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    pct_change = float(p.get("pct_change") or 0)
    income = float(snap["monthly_income"] or 0)
    new_income = income * (1 + pct_change)
    expense = float(snap["monthly_expense"] or 0)
    new_surplus = new_income - expense
    new_sr = new_surplus / new_income if new_income > 0 else None

    return {
        "scenario": "income_change",
        "title": "收入变化",
        "plan_a_label": "现状",
        "plan_b_label": f"收入变化 {pct_change*100:+.0f}%",
        "summary": [
            {"label": "收入变化", "value": round(pct_change * 100, 1)},
        ],
        "rows": [
            {"label": "月收入", "a": round(income, 2), "b": round(new_income, 2), "money": True},
            {"label": "月结余", "a": round(float(snap["monthly_surplus"] or 0), 2), "b": round(new_surplus, 2), "money": True},
            {"label": "储蓄率", "a": snap["savings_rate"],
             "b": round(new_sr, 3) if new_sr is not None else None},
        ],
        "conclusion": _income_conclusion(pct_change, new_surplus),
        "params_snapshot": {"pct_change": pct_change},
    }


def _income_conclusion(pct_change: float, new_surplus: float) -> str:
    if pct_change >= 0:
        main = f"收入增加 {pct_change*100:.0f}% 后，月结余增至 {new_surplus:,.0f} 元"
    else:
        main = f"收入减少 {abs(pct_change)*100:.0f}% 后，月结余变为 {new_surplus:,.0f} 元"
    if new_surplus < 0:
        main += "，现金流为负，需尽快削减支出或补充收入"
    return main + "。"


# ---------- 注册表 + 引擎入口 ----------

SCENARIOS = {
    "buy_house": simulate_buy_house,
    "prepay": simulate_prepay,
    "invest": simulate_invest,
    "income_change": simulate_income_change,
}


def run_scenario(data: dict[str, Any], snap: dict[str, Any], scenario: str, params: dict[str, Any]) -> dict[str, Any]:
    """引擎入口：接收家庭数据快照（不碰数据库），按场景名分发。"""
    fn = SCENARIOS.get(scenario)
    if fn is None:
        return {"scenario": scenario, "title": "决策模拟", "error": f"未知场景: {scenario}"}
    return fn(data, snap, params)
