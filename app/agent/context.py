"""V2.1 Context Engine：把家庭数据组装成 LLM 可读的 Wealth Context。

铁律：
- 纯函数、零 LLM、零 I/O、零财富计算——只「搬运」build_overview 已算好的数字。
- 每个带 value 的数字必带 source 字段路径（沿用 MetricRef.source 语义），防编造。
- 只调一次 build_overview（内部已含 build_issues + build_goals），再补 family_data 原始明细。

四块 Context（Conversation 第五块留 V2.4）：
- Family Context：成员/资产/负债/保险原始明细
- Financial Context：财富评分/净资产/现金流/DTI/应急/房产占比/养老 RFR-NWC（数字带 source）
- Decision Context：P0/P1/P2 问题 + 去重建议
- Goal Context：目标 + 缺口 + 每月需存
"""
from __future__ import annotations

from ..services import build_overview

__all__ = ["build_wealth_context", "context_to_text"]


def _num(value, source: str) -> dict:
    """包装数字指标：value 为 None 时 source 也置空（无数字则无出处）。"""
    return {"value": value, "source": source if value is not None else None}


def _pick(row: dict, keys: tuple[str, ...]) -> dict:
    """只取指定键、且值非 None 的字段（去掉空值，保持紧凑）。"""
    return {k: row.get(k) for k in keys if row.get(k) is not None}


def build_wealth_context(family_data: dict) -> dict:
    """组装四块 Wealth Context（纯函数，绝不计算）。"""
    ov = build_overview(family_data)
    alloc = (ov.get("asset_allocation") or {}).get("classes") or {}
    cashflow = ov.get("cashflow") or {}
    debt = ov.get("debt") or {}
    liquidity = ov.get("liquidity") or {}
    retirement = ov.get("retirement") or {}

    financial = {
        "wealth_score": _num(ov.get("wealth_score"), "overview.wealth_score"),
        "wealth_level": ov.get("wealth_level"),
        "net_worth": _num(ov.get("net_worth"), "overview.net_worth"),
        "total_assets": _num(ov.get("total_assets"), "overview.total_assets"),
        "total_liabilities": _num(ov.get("total_liabilities"), "overview.total_liabilities"),
        "monthly_income": _num(cashflow.get("income"), "overview.cashflow.income"),
        "monthly_expense": _num(cashflow.get("expense"), "overview.cashflow.expense"),
        "monthly_surplus": _num(cashflow.get("surplus"), "overview.cashflow.surplus"),
        "savings_rate": _num(cashflow.get("savings_rate"), "overview.cashflow.savings_rate"),
        "dti": _num(debt.get("dti"), "overview.debt.dti"),
        "emergency_months": _num(liquidity.get("emergency_months"),
                                 "overview.liquidity.emergency_months"),
        "real_estate_pct": _num((alloc.get("real_estate") or {}).get("pct"),
                                "overview.asset_allocation.classes.real_estate.pct"),
        "rfr": _num(retirement.get("rfr"), "overview.retirement.rfr"),
        "nwc": _num(retirement.get("nwc"), "overview.retirement.nwc"),
    }

    family = {
        "members": [_pick(p, ("name", "relation", "birth_year", "job"))
                    for p in (family_data.get("persons") or [])],
        "assets": [_pick(a, ("type", "name", "value"))
                   for a in (family_data.get("assets") or [])],
        "liabilities": [_pick(l, ("type", "name", "principal", "monthly_payment"))
                        for l in (family_data.get("liabilities") or [])],
        "insurance": [_pick(i, ("type", "name", "coverage", "annual_premium"))
                      for i in (family_data.get("insurance") or [])],
    }

    decision = {
        "issues": [_pick(i, ("severity", "title", "finding"))
                   for i in (ov.get("issues") or [])],
        "recommendations": [_pick(r, ("action", "detail"))
                            for r in (ov.get("recommendations") or [])],
    }

    goals = [_pick(g, ("name", "type", "target_amount", "gap", "coverage", "monthly_needed"))
             for g in (ov.get("goals") or [])]

    return {"family": family, "financial": financial, "decision": decision, "goals": goals}


def context_to_text(ctx: dict) -> str:
    """把 Wealth Context 序列化成紧凑文本，供 LLM 读（数字带 source 标注，防篡改）。"""
    fin = ctx["financial"]
    lines: list[str] = []

    # 财务指标（数字 + source）
    labels = {
        "wealth_score": "财富评分", "net_worth": "净资产", "total_assets": "总资产",
        "total_liabilities": "总负债", "monthly_income": "月收入", "monthly_expense": "月支出",
        "monthly_surplus": "月结余", "savings_rate": "储蓄率", "dti": "负债率 DTI",
        "emergency_months": "应急资金(月)", "real_estate_pct": "房产占比",
        "rfr": "养老 RFR", "nwc": "养老 NWC",
    }
    parts = []
    for key, label in labels.items():
        item = fin.get(key)
        if isinstance(item, dict) and item.get("value") is not None:
            parts.append(f"{label}={item['value']}（source: {item['source']}）")
    if parts:
        lines.append("【财务指标】" + "；".join(parts))
    else:
        lines.append("【财务指标】暂无数据")

    # 家庭概况
    fam = ctx["family"]
    n_issues = len(ctx["decision"].get("issues") or [])
    lines.append(
        f"【家庭概况】成员 {len(fam.get('members') or [])} 人，"
        f"资产 {len(fam.get('assets') or [])} 项，负债 {len(fam.get('liabilities') or [])} 项，"
        f"问题 {n_issues} 个"
    )

    # 问题列表
    for i in (ctx["decision"].get("issues") or [])[:5]:
        lines.append(f"· [{i.get('severity')}] {i.get('title')}：{i.get('finding')}")

    # 目标列表
    for g in (ctx.get("goals") or [])[:5]:
        gap = g.get("gap")
        lines.append(f"· 目标「{g.get('name')}」{f'缺口 {gap:,.0f} 元' if gap else ''}")

    return "\n".join(lines)
