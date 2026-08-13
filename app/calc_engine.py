"""确定性计算引擎：所有财务数字在这里用纯函数计算，绝不交给 LLM。

输入是一份家庭数据快照（dict 列表），输出是结构化的财务指标。
这个模块无任何外部依赖，可独立单测、可审计。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

# 视为"流动现金"的资产类型，用于应急资金覆盖月数
LIQUID_ASSET_TYPES = {"存款", "货币基金", "现金", "活期", "理财"}


def _monthly(amount: float, period: str) -> float:
    """把金额归一化为月。period 为 '年' 时除以 12。"""
    return amount / 12.0 if period == "年" else amount


# ---------- 基础指标 ----------

def total_assets(assets: list[dict[str, Any]]) -> float:
    return sum(float(a.get("value") or 0) for a in assets)


def total_liabilities(liabilities: list[dict[str, Any]]) -> float:
    return sum(float(l.get("principal") or 0) for l in liabilities)


def net_worth(assets: list[dict[str, Any]], liabilities: list[dict[str, Any]]) -> float:
    return total_assets(assets) - total_liabilities(liabilities)


def monthly_income(cashflows: list[dict[str, Any]]) -> float:
    return sum(_monthly(float(c["amount"]), c.get("period", "月"))
               for c in cashflows if c["flow_type"] == "income")


def monthly_expense(cashflows: list[dict[str, Any]],
                    liabilities: list[dict[str, Any]] | None = None) -> float:
    """月支出 = 日常支出现金流 + 负债月供（月供是刚性现金流流出，必须计入）。"""
    exp = sum(_monthly(float(c["amount"]), c.get("period", "月"))
              for c in cashflows if c["flow_type"] == "expense")
    for l in (liabilities or []):
        exp += _monthly(float(l.get("monthly_payment") or 0), "月")
    return exp


def monthly_surplus(cashflows: list[dict[str, Any]],
                    liabilities: list[dict[str, Any]] | None = None) -> float:
    return monthly_income(cashflows) - monthly_expense(cashflows, liabilities)


def savings_rate(cashflows: list[dict[str, Any]],
                 liabilities: list[dict[str, Any]] | None = None) -> float | None:
    inc = monthly_income(cashflows)
    if inc <= 0:
        return None
    return monthly_surplus(cashflows, liabilities) / inc


def liquid_assets(assets: list[dict[str, Any]]) -> float:
    return sum(float(a.get("value") or 0)
               for a in assets if a.get("type") in LIQUID_ASSET_TYPES)


def emergency_months(assets: list[dict[str, Any]],
                     cashflows: list[dict[str, Any]],
                     liabilities: list[dict[str, Any]] | None = None) -> float | None:
    exp = monthly_expense(cashflows, liabilities)
    if exp <= 0:
        return None
    return liquid_assets(assets) / exp


def debt_to_income(liabilities: list[dict[str, Any]], cashflows: list[dict[str, Any]]) -> float | None:
    """月供 / 月收入。"""
    inc = monthly_income(cashflows)
    if inc <= 0:
        return None
    monthly_debt = sum(_monthly(float(l.get("monthly_payment") or 0), "月")
                       for l in liabilities)
    return monthly_debt / inc


# ---------- 目标 ----------

def _months_until(target_date: str | None, today: date | None = None) -> int | None:
    """目标日期距今天还有多少个月（向下取整）。无日期或已过期返回 None/0。"""
    if not target_date:
        return None
    try:
        d = datetime.fromisoformat(str(target_date)).date()
    except ValueError:
        return None
    today = today or date.today()
    return max((d.year - today.year) * 12 + (d.month - today.month), 0)


def goal_gap(goal: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    target = float(goal.get("target_amount") or 0)
    saved = float(goal.get("current_saved") or 0)
    gap = max(target - saved, 0.0)
    months = _months_until(goal.get("target_date"), today)
    monthly_needed = round(gap / months, 2) if months else None
    return {
        "goal_id": goal.get("id"),
        "name": goal.get("name") or goal.get("type"),
        "target_amount": target,
        "current_saved": saved,
        "gap": gap,
        "progress": (saved / target) if target > 0 else 0.0,
        "months_remaining": months,
        "monthly_needed": monthly_needed,
    }


def goals_summary(goals: list[dict[str, Any]], today: date | None = None) -> list[dict[str, Any]]:
    return [goal_gap(g, today) for g in goals]


def goals_funding(
    goals: list[dict[str, Any]],
    monthly_surplus_value: float,
    today: date | None = None,
) -> dict[str, Any]:
    """目标资金竞争：各目标每月需存总额 vs 月结余，判断是否可行。"""
    summaries = goals_summary(goals, today)
    total_needed = sum(g["monthly_needed"] for g in summaries if g["monthly_needed"])
    return {
        "total_monthly_needed": round(total_needed, 2),
        "monthly_surplus": round(monthly_surplus_value, 2),
        "feasible": total_needed <= monthly_surplus_value,
        "shortfall": round(max(total_needed - monthly_surplus_value, 0), 2),
    }


# ---------- 家庭安全边际（核心指标） ----------

def safety_margin(
    assets: list[dict[str, Any]],
    liabilities: list[dict[str, Any]],
    cashflows: list[dict[str, Any]],
) -> dict[str, Any]:
    """家庭安全边际：应急月数 + 负债压力 + 结余能力的综合评分（0-100）。

    这是产品的核心指标，评分逻辑完全确定、可解释。
    """
    inc = monthly_income(cashflows)
    exp = monthly_expense(cashflows, liabilities)
    em = emergency_months(assets, cashflows, liabilities) or 0
    dti = debt_to_income(liabilities, cashflows) or 0

    score = 50.0
    reasons: list[str] = []

    # 应急资金：>=6 个月满分 +25，0 个月 -25
    if em >= 6:
        score += 25
    elif em >= 3:
        score += 10
        reasons.append(f"应急资金约 {em:.1f} 个月，建议补到 6 个月")
    else:
        score -= 25
        reasons.append(f"应急资金仅 {em:.1f} 个月，失业或突发开支风险高")

    # 负债压力：月供/收入 <=30% 满分 +25，>50% -25
    if inc > 0 and dti <= 0.3:
        score += 25
    elif inc > 0 and dti <= 0.5:
        score += 5
        reasons.append(f"月供占收入 {dti*100:.0f}%，负债压力偏高")
    elif inc > 0:
        score -= 25
        reasons.append(f"月供占收入 {dti*100:.0f}%，负债压力过大")
    else:
        reasons.append("尚未记录收入，无法评估负债压力")

    # 结余能力：储蓄率 >=20% 满分 +25，<0 -25
    sr = savings_rate(cashflows, liabilities)
    if sr is None:
        reasons.append("尚未记录收入，无法评估储蓄率")
    elif sr >= 0.2:
        score += 25
    elif sr >= 0:
        score += 0
        reasons.append(f"储蓄率 {sr*100:.0f}%，结余偏薄")
    else:
        score -= 25
        reasons.append("月支出超过月收入，家庭现金流为负")

    score = max(0.0, min(100.0, score))
    if score >= 75:
        level = "稳健"
    elif score >= 50:
        level = "需关注"
    else:
        level = "脆弱"

    return {
        "score": round(score),
        "level": level,
        "emergency_months": round(em, 1) if em else None,
        "debt_to_income": round(dti, 3) if inc > 0 else None,
        "savings_rate": round(sr, 3) if sr is not None else None,
        "reasons": reasons,
    }


# ---------- 汇总快照 ----------

def snapshot(family_data: dict[str, Any]) -> dict[str, Any]:
    assets = family_data.get("assets", [])
    liabilities = family_data.get("liabilities", [])
    cashflows = family_data.get("cashflows", [])
    goals = family_data.get("goals", [])
    persons = family_data.get("persons", [])

    return {
        "persons": len(persons),
        "total_assets": round(total_assets(assets), 2),
        "total_liabilities": round(total_liabilities(liabilities), 2),
        "net_worth": round(net_worth(assets, liabilities), 2),
        "monthly_income": round(monthly_income(cashflows), 2),
        "monthly_expense": round(monthly_expense(cashflows, liabilities), 2),
        "monthly_surplus": round(monthly_surplus(cashflows, liabilities), 2),
        "savings_rate": (round(savings_rate(cashflows, liabilities), 3)
                         if savings_rate(cashflows, liabilities) is not None else None),
        "emergency_months": (round(emergency_months(assets, cashflows, liabilities), 1)
                             if emergency_months(assets, cashflows, liabilities) is not None else None),
        "goals": goals_summary(goals),
        "goals_funding": goals_funding(goals, monthly_surplus(cashflows, liabilities)),
        "safety_margin": safety_margin(assets, liabilities, cashflows),
    }
