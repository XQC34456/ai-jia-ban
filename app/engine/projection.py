"""Wealth Engine · 长期财富投影：资产层确定性年度模型（非 Monte Carlo）。

核心原则：绝不把「净资产整体」当作单一收益率基数。家庭净资产里房产 / 股票 /
基金 / 存款 / 负债的经济含义完全不同，必须分大类各自投影——

- cash / fixed_income / equity / alternative / other 按各自收益率复利
- real_estate 按 house_growth 复利
- 负债（房贷等）按等额本息逐年摊销（本金递减）
- 年度结余按目标配置投入金融资产（结余为负则消耗现金）

退休资金评估区分「可投资资产」与「净资产」，默认不把自住房产计入可投资资产。
"""
from __future__ import annotations

__all__ = [
    "future_value", "project_net_worth", "project_family",
    "retirement_funding_ratio", "RETURN_DEFAULTS", "DEFAULT_ASSUMPTIONS",
    "FINANCIAL_CLASSES",
]

# 各资产大类默认年化收益率（确定性假设，可被 assumptions 按 `{cls}_return` 覆盖）
RETURN_DEFAULTS = {
    "cash": 0.015,
    "fixed_income": 0.030,
    "equity": 0.080,
    "real_estate": 0.030,
    "alternative": 0.070,
    "other": 0.0,
}

# 可视为「退休可投资资产」的金融大类（房产默认不计入，除非设置 real_estate_to_cash）
FINANCIAL_CLASSES = ("cash", "fixed_income", "equity", "alternative", "other")

DEFAULT_ASSUMPTIONS = {
    "inflation": 0.03,
    "income_growth": 0.03,
    "expense_growth": 0.02,
    "retirement_age": 60,
    "retirement_expense_ratio": 0.7,
    "pension_income": 0.0,          # 退休后每月养老金
    "life_expectancy": 90,
    "real_estate_to_cash": 0.0,     # 退休时房产可变现比例（默认自住房不计入可投资资产）
    "discount_rate": 0.03,          # 退休需求现值折现率（保守，取固定收益）
}


def future_value(amount: float, annual_return: float, years: int) -> float:
    """一笔金额按年化收益率复利 years 年后的终值。"""
    return amount * (1 + annual_return) ** years


def project_net_worth(net_worth: float, monthly_surplus: float, annual_return: float, years: int) -> list[float]:
    """简化的恒定复利工具（快速估算用，非主模型；主模型见 project_family）。"""
    seq = [net_worth]
    for _ in range(years):
        net_worth = net_worth * (1 + annual_return) + monthly_surplus * 12
        seq.append(round(net_worth, 2))
    return seq


def _rate(v) -> float:
    if not v:
        return 0.0
    r = float(v)
    return r / 100.0 if r > 1 else r


def _amortize_year(principal: float, annual_rate: float, remaining_months: int):
    """等额本息还 12 个月：返回 (剩余本金, 已还本金, 已付利息)。"""
    r = annual_rate / 12.0
    n = int(remaining_months or 0)
    if principal <= 0 or n <= 0:
        return 0.0, 0.0, 0.0
    if r <= 0:
        m = principal / n
    else:
        m = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    months = min(12, n)
    if r <= 0:
        remaining = principal * (1 - months / n)
    else:
        remaining = principal * (1 + r) ** months - m * ((1 + r) ** months - 1) / r
    remaining = max(remaining, 0.0)
    principal_repaid = principal - remaining
    interest = m * months - principal_repaid
    return remaining, principal_repaid, interest


def _flow(start_age: int, annual_income: float, annual_living_expense: float, a: dict, t: int):
    """第 t 年的收入 / 生活支出 / 养老金（确定性单一路径）。

    start_age 为「该年起始年龄」：start_age < retirement_age 仍属工作年（有工资），
    否则进入退休年（无工资、按退休支出比例 + 养老金）。
    """
    if start_age < a["retirement_age"]:
        income = annual_income * (1 + a["income_growth"]) ** t
        living = annual_living_expense * (1 + a["expense_growth"]) ** t
        pension = 0.0
    else:
        income = 0.0
        living = annual_living_expense * a["retirement_expense_ratio"] * (1 + a["inflation"]) ** t
        pension = a["pension_income"] * 12
    return income, living, pension


def project_family(assets: dict, debts: list, annual_income: float, annual_living_expense: float,
                   current_age: int, assumptions: dict | None = None,
                   allocation: dict | None = None) -> list[dict]:
    """资产层确定性投影，返回逐年记录（长度 = 预期寿命 - 当前年龄 + 1）。

    assets: {cash, fixed_income, equity, real_estate, alternative, other} → 金额
    debts:  [{principal, annual_rate, remaining_months}] 等额本息摊销型负债
    annual_living_expense: 年生活支出（不含债务月供，债务单独摊销）
    allocation: 年度结余投入金融资产的目标配置 {cash, fixed_income, equity}（Σ=1）

    第 0 年为现状快照（不滚动资产、不实际摊销债务）；t≥1 逐层滚动：
    资产按各自收益率复利 → 债务摊销 → 结余按目标配置分配。
    """
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    alloc = allocation or {"cash": 0.15, "fixed_income": 0.45, "equity": 0.40}
    ret = {cls: float(a.get(f"{cls}_return", RETURN_DEFAULTS[cls])) for cls in RETURN_DEFAULTS}
    debt_state = [dict(d) for d in (debts or []) if float(d.get("principal") or 0) > 0]
    years = max(int(a["life_expectancy"]) - current_age, 0)
    bal = {cls: float(assets.get(cls, 0.0)) for cls in RETURN_DEFAULTS}
    seq: list[dict] = []

    for t in range(years + 1):
        age = current_age + t
        start_age = current_age + t - 1 if t > 0 else current_age
        income, living, pension = _flow(start_age, annual_income, annual_living_expense, a, t)

        if t == 0:
            # 现状快照：仅报告本年度债务服务，不实际摊销、不滚动资产
            debt_service = 0.0
            for d in debt_state:
                _, repaid, interest = _amortize_year(
                    d["principal"], _rate(d.get("annual_rate")), d.get("remaining_months", 0))
                debt_service += repaid + interest
            surplus = income + pension - living - debt_service
        else:
            # 真实滚动：债务摊销 → 资产各自复利 → 结余分配
            debt_principal = debt_interest = 0.0
            for d in debt_state:
                rem, repaid, interest = _amortize_year(
                    d["principal"], _rate(d.get("annual_rate")), d.get("remaining_months", 0))
                d["principal"] = rem
                d["remaining_months"] = max(int(d.get("remaining_months", 0)) - 12, 0)
                debt_principal += repaid
                debt_interest += interest
            debt_service = debt_principal + debt_interest
            surplus = income + pension - living - debt_service
            for cls in bal:
                bal[cls] *= (1 + ret[cls])
            if surplus > 0:
                bal["cash"] += surplus * alloc.get("cash", 0.0)
                bal["fixed_income"] += surplus * alloc.get("fixed_income", 0.0)
                bal["equity"] += surplus * alloc.get("equity", 0.0)
            else:
                bal["cash"] += surplus  # 结余为负：先消耗现金

        total_assets = sum(bal.values())
        total_debt = sum(d["principal"] for d in debt_state)
        investable = (sum(bal[cls] for cls in FINANCIAL_CLASSES)
                      + bal["real_estate"] * a["real_estate_to_cash"])
        seq.append({
            "year": t, "age": age,
            "income": round(income, 2),
            "living_expense": round(living, 2),
            "debt_service": round(debt_service, 2),
            "pension": round(pension, 2),
            "surplus": round(surplus, 2),
            "assets": {cls: round(bal[cls], 2) for cls in bal},
            "total_assets": round(total_assets, 2),
            "total_debt": round(total_debt, 2),
            "net_worth": round(total_assets - total_debt, 2),
            "investable": round(investable, 2),
        })
    return seq


def retirement_funding_ratio(assets: dict, debts: list, annual_income: float,
                             annual_living_expense: float, current_age: int,
                             assumptions: dict | None = None,
                             allocation: dict | None = None) -> dict:
    """Retirement Funding Ratio（可投资资产口径）+ Net Worth Coverage（净资产口径）。

    RFR = 退休可投资资产 / 退休资金需求现值（默认不含自住房产，除非设置 real_estate_to_cash）
    NWC = 退休净资产 / 退休资金需求现值

    Wealth Score 的 retirement 维度优先使用 RFR，而非 NWC——用于识别
    「净资产充足但退休流动资金不足」的家庭。
    """
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    seq = project_family(assets, debts, annual_income, annual_living_expense, current_age, a, allocation)
    retire_year = int(a["retirement_age"]) - current_age          # 退休相对年数（≤0 表示已退休）
    # 退休时点 = 最后一个工作年末（退休前一刻）：seq[retire_year] 的起始年龄仍是工作年；
    # 已退休（retire_year≤0）则取当前快照 seq[0]。
    at = seq[min(max(retire_year, 0), len(seq) - 1)]
    investable = at["investable"]
    net_worth = at["net_worth"]

    n = max(int(a["life_expectancy"]) - int(a["retirement_age"]), 0)
    disc = float(a["discount_rate"])
    need_pv = 0.0
    for k in range(n):
        year_index = max(retire_year, 0) + k                       # 退休后第 k 年距现在的年数（通胀放大用）
        expense = annual_living_expense * a["retirement_expense_ratio"] * (1 + a["inflation"]) ** year_index
        shortfall = max(expense - a["pension_income"] * 12, 0.0)
        need_pv += shortfall / (1 + disc) ** k

    rfr = investable / need_pv if need_pv > 0 else None
    nwc = net_worth / need_pv if need_pv > 0 else None
    score = max(0.0, min(100.0, (rfr or 0.0) * 100)) if rfr is not None else 40
    return {
        "retirement_age": int(a["retirement_age"]),
        "investable_at_retirement": round(investable, 2),
        "net_worth_at_retirement": round(net_worth, 2),
        "retirement_need_pv": round(need_pv, 2),
        "funding_ratio": round(rfr, 2) if rfr is not None else None,
        "net_worth_coverage": round(nwc, 2) if nwc is not None else None,
        "score": round(score),
    }
