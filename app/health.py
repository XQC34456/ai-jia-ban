"""家庭财富体检：从快照里挑出"最值得关注的 3 个问题"。

规则引擎，确定性输出；每个问题带"问题 / 为什么 / 建议"三段。
"""
from __future__ import annotations

from typing import Any

from . import calc_engine as ce


def health_check(family_data: dict[str, Any]) -> list[dict[str, Any]]:
    """返回按严重度排序的体检问题列表（最多 3 个）。"""
    assets = family_data.get("assets", [])
    liabilities = family_data.get("liabilities", [])
    cashflows = family_data.get("cashflows", [])
    goals = family_data.get("goals", [])

    problems: list[dict[str, Any]] = []

    inc = ce.monthly_income(cashflows)
    exp = ce.monthly_expense(cashflows, liabilities)
    em = ce.emergency_months(assets, cashflows, liabilities)
    dti = ce.debt_to_income(liabilities, cashflows)
    sr = ce.savings_rate(cashflows, liabilities)
    total_assets = ce.total_assets(assets)

    # 1. 应急资金不足
    if em is not None and em < 6:
        severity = 5 if em < 3 else 3
        problems.append({
            "severity": severity,
            "title": "应急资金不足",
            "why": f"你家的应急资金只能覆盖约 {em:.1f} 个月的支出，低于 6 个月的安全线。",
            "advice": "优先补足 3~6 个月生活开支的应急金，放在活期/货币基金等随时可取的账户。",
        })
    elif em is None and exp > 0:
        problems.append({
            "severity": 2,
            "title": "缺少流动性信息",
            "why": "已记录每月支出，但还没有存款/现金类资产，无法评估应急能力。",
            "advice": "补充家庭存款、货币基金等流动现金信息。",
        })

    # 2. 负债压力过大
    if dti is not None and dti > 0.5:
        problems.append({
            "severity": 5,
            "title": "负债压力过大",
            "why": f"每月还贷占收入的 {dti*100:.0f}%，超过 50% 警戒线。",
            "advice": "评估是否提前还贷或拉长期限，把月供压到收入的 30% 以内。",
        })
    elif dti is not None and dti > 0.3:
        problems.append({
            "severity": 3,
            "title": "负债压力偏高",
            "why": f"每月还贷占收入的 {dti*100:.0f}%，处于偏高区间。",
            "advice": "关注利率变化，预留缓冲，避免再新增高杠杆负债。",
        })

    # 3. 储蓄率过低 / 现金流为负
    if sr is not None and sr < 0:
        problems.append({
            "severity": 5,
            "title": "家庭现金流为负",
            "why": f"月支出 {exp:,.0f} 元超过月收入 {inc:,.0f} 元，家庭在持续消耗积蓄。",
            "advice": "找出大额非必要支出，先把月度结余转正。",
        })
    elif sr is not None and sr < 0.2:
        problems.append({
            "severity": 3,
            "title": "储蓄率偏低",
            "why": f"当前储蓄率 {sr*100:.0f}%，低于 20% 的健康线，长期目标资金积累会偏慢。",
            "advice": "尝试把储蓄率逐步提升到 20% 以上。",
        })

    # 4. 资产集中度过高（房产占大头）
    if total_assets > 0:
        house = sum(float(a.get("value") or 0) for a in assets if a.get("type") == "房产")
        if house / total_assets > 0.7:
            problems.append({
                "severity": 4,
                "title": "资产过度集中于房产",
                "why": f"房产占总资产 {(house/total_assets)*100:.0f}%，流动性和抗风险能力偏弱。",
                "advice": "逐步增加金融资产比例，避免家庭财富与房价高度绑定。",
            })

    # 5. 目标缺口大
    for g in goals:
        gap = ce.goal_gap(g)
        if gap["target_amount"] > 0 and gap["gap"] > 0:
            extra = f"（每月需存 {gap['monthly_needed']:,.0f} 元）" if gap["monthly_needed"] else ""
            problems.append({
                "severity": 3,
                "title": f"{gap['name']}存在资金缺口",
                "why": f"目标需 {gap['target_amount']:,.0f} 元，当前已备 {gap['current_saved']:,.0f} 元，缺口 {gap['gap']:,.0f} 元{extra}。",
                "advice": "设定每月定存金额，让目标进度可跟踪。",
            })

    # 6. 目标资金竞争：各目标每月需存总额超过月结余
    funding = ce.goals_funding(goals, ce.monthly_surplus(cashflows, liabilities))
    if funding["total_monthly_needed"] > 0 and not funding["feasible"]:
        problems.append({
            "severity": 4,
            "title": "目标资金超出现金流能力",
            "why": (f"各目标合计每月需存 {funding['total_monthly_needed']:,.0f} 元，"
                    f"但月结余仅 {funding['monthly_surplus']:,.0f} 元，"
                    f"每月缺口 {funding['shortfall']:,.0f} 元。"),
            "advice": "评估目标优先级，或延长目标期限、下调目标金额。",
        })

    # 按严重度排序，取前 3
    problems.sort(key=lambda p: p["severity"], reverse=True)
    return problems[:3]
