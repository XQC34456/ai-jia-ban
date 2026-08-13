"""Decision Layer · 7 类问题检测器。

每个检测器接收 family_data + 共享上下文 ctx，返回一个 Issue dict 或 None。
只做「判断」，不计算任何财务数字（数字全部来自 Engine）；阈值与既有引擎一致。

Recommendation.scenario 只引用 engine.scenario 已实现的情景名
（buy_house / prepay / invest / income_change）；无对应情景的动作为 None（actionable=False）。
"""
from __future__ import annotations

from typing import Any

from .quadrant import retirement_quadrant

__all__ = ["DETECTORS"]


def _rec(action: str, detail: str, *, reason: str = "", target: dict | None = None,
         scenario: str | None = None) -> dict[str, Any]:
    """动作化建议：只到资产类别/行为层，绝不推荐具体产品。

    - target:   量化目标（数值），如 {"rfr": 1.0}
    - scenario: 可触发的已实现情景名；None 表示暂无对应情景（actionable=False）
    recommendation_id / priority / current 由 build_issues 组装时统一填充。
    """
    return {
        "recommendation_id": "",
        "action": action,
        "detail": detail,
        "reason": reason,
        "priority": None,
        "current": {},
        "target": target or {},
        "expected_effect": {},
        "actionable": scenario is not None,
        "scenario": scenario,
    }


# ---------- ① 现金流 ----------

def detect_cashflow(fd: dict, ctx: dict) -> dict | None:
    snap = ctx["snap"]
    inc = snap["monthly_income"]
    if inc <= 0:
        return None
    surplus = snap["monthly_surplus"]
    sr = snap["savings_rate"]
    if surplus < 0:
        return {
            "issue_id": "CASHFLOW_NEGATIVE_001", "type": "cashflow", "severity": "P0",
            "title": "家庭现金流为负",
            "finding": f"月支出 {snap['monthly_expense']:,.0f} 元超过月收入 {inc:,.0f} 元",
            "reason": ["支出超过收入", "家庭在持续消耗积蓄"],
            "metric": {"monthly_income": inc, "monthly_expense": snap["monthly_expense"],
                       "monthly_surplus": surplus},
            "target": {"monthly_surplus": "≥ 0"},
            "recommendations": [_rec(
                "削减非必要支出", "找出大额非必要支出，先把月度结余转正",
                reason="月度支出超过收入，结余为负",
                target={"monthly_surplus": 0.0}, scenario="income_change")],
            "scenarios": ["income_change"],
        }
    if sr is not None and sr < 0.2:
        return {
            "issue_id": "CASHFLOW_LOW_SAVINGS_001", "type": "cashflow", "severity": "P1",
            "title": "储蓄率偏低",
            "finding": f"当前储蓄率 {sr*100:.0f}%，低于 20% 健康线",
            "reason": ["月度结余偏薄", "长期目标资金积累会偏慢"],
            "metric": {"savings_rate": round(sr, 3), "monthly_surplus": surplus},
            "target": {"savings_rate": "≥ 20%"},
            "recommendations": [_rec(
                "提升储蓄率", "逐步把储蓄率提升到 20% 以上，先自动转账再消费",
                reason="月度结余偏薄，储蓄率低于 20% 健康线",
                target={"savings_rate": 0.20}, scenario="income_change")],
            "scenarios": ["income_change"],
        }
    return None


# ---------- ② 流动性 ----------

def detect_liquidity(fd: dict, ctx: dict) -> dict | None:
    em = ctx["snap"]["emergency_months"]
    if em is None:
        return None
    if em < 3:
        sev, title = "P0", "应急资金严重不足"
    elif em < 6:
        sev, title = "P1", "应急资金偏低"
    else:
        return None
    return {
        "issue_id": "LIQUIDITY_LOW_001", "type": "liquidity", "severity": sev,
        "title": title,
        "finding": f"当前应急资金仅覆盖 {em:.1f} 个月支出",
        "reason": ["流动现金类资产不足", "低于 6 个月的安全线"],
        "metric": {"emergency_months": em},
        "target": {"emergency_months": "≥ 6 个月"},
        "recommendations": [_rec(
            "补足应急金", "优先补足 3~6 个月生活开支的应急金，放在活期/货币基金等随时可取账户",
            reason="流动现金类资产不足，低于 6 个月安全线",
            target={"emergency_months": 6.0})],
        "scenarios": [],
    }


# ---------- ③ 负债 ----------

def detect_debt(fd: dict, ctx: dict) -> dict | None:
    liabilities = fd.get("liabilities", [])
    if not liabilities:
        return None
    snap = ctx["snap"]
    dti = _dti(liabilities, fd.get("cashflows", []))
    if dti is None:
        return None
    if dti > 0.5:
        sev, title = "P0", "负债压力过大"
    elif dti > 0.3:
        sev, title = "P1", "负债压力偏高"
    else:
        return None
    # 还贷 vs 投资：高息债或高 DTI 优先降负债
    max_rate = max((float(l.get("interest_rate") or 0) for l in liabilities), default=0.0)
    max_rate = max_rate / 100.0 if max_rate > 1 else max_rate
    prefer_debt = max_rate > 0.06 or dti > 0.4
    guidance = ("优先降低负债" if prefer_debt
                else "可兼顾投资与还贷")
    return {
        "issue_id": "DEBT_HIGH_001", "type": "debt", "severity": sev,
        "title": title,
        "finding": f"每月还贷占收入 {dti*100:.0f}%",
        "reason": ["月供占收入比例偏高", "挤压可用于储蓄与投资的现金流"],
        "metric": {"dti": round(dti, 3), "total_debt": snap["total_liabilities"],
                   "max_interest_rate": round(max_rate, 4)},
        "target": {"dti": "≤ 30%"},
        "recommendations": [_rec(
            "优先降低负债" if prefer_debt else "控制杠杆",
            "评估提前还贷或拉长期限，把月供压到收入 30% 以内" + ("；当前更应优先还贷而非追加投资" if prefer_debt else ""),
            reason="月供占收入比例偏高，挤压储蓄与投资现金流",
            target={"dti": 0.30}, scenario="prepay")],
        "scenarios": ["prepay"],
    }


def _dti(liabilities, cashflows) -> float | None:
    from app.engine import metrics
    return metrics.debt_to_income(liabilities, cashflows)


# ---------- ④ 资产配置 ----------

def detect_allocation(fd: dict, ctx: dict) -> dict | None:
    if not fd.get("assets"):
        return None
    fit = ctx["fit"]
    alloc = ctx["alloc"]
    score = fit["score"]
    if score >= 60:
        return None
    sev = "P0" if score < 30 else "P1"
    recs = [_rec(_action_text(a), _detail_text(a),
                 reason=f"配置适配度 {score} 分，偏离目标配置",
                 target=_target_for(a), scenario="invest")
            for a in alloc["adjustments"][:2]]
    if not recs:
        recs = [_rec("调整资产配置", "按目标配置逐步增配低配大类、减配超配大类",
                     reason=f"配置适配度 {score} 分，偏离目标配置",
                     target={"allocation_fitness": 60}, scenario="invest")]
    return {
        "issue_id": "ALLOCATION_LOW_FITNESS_001", "type": "allocation", "severity": sev,
        "title": "资产配置适配度偏低",
        "finding": f"配置适配度 {score} 分",
        "reason": list(fit["reasons"]) or ["当前配置偏离目标配置"],
        "metric": {"allocation_fitness": score,
                   "real_estate_pct": fit["concentration"]["real_estate_pct"],
                   "deviation": fit["deviation"]},
        "target": {"allocation_fitness": "≥ 60"},
        "recommendations": recs,
        "scenarios": ["invest"],
    }


def _action_text(a: dict) -> str:
    cls_name = {"cash": "现金", "fixed_income": "固收", "equity": "权益"}.get(a["asset_class"], a["asset_class"])
    return f"{a['action']}{cls_name}"


def _detail_text(a: dict) -> str:
    cls_name = {"cash": "现金", "fixed_income": "固收", "equity": "权益"}.get(a["asset_class"], a["asset_class"])
    if a["action"] == "减配":
        return f"{cls_name}占比 {a['current_pct']*100:.0f}%，高于目标上限 {a['target_high']*100:.0f}%，未来新增资金暂不继续增加该类"
    return f"{cls_name}占比 {a['current_pct']*100:.0f}%，低于目标下限 {a['target_low']*100:.0f}%，未来新增资金优先补充该类"


def _target_for(a: dict) -> dict:
    """配置建议的量化目标：增配→目标下限，减配→目标上限（ratio）。"""
    v = a["target_low"] if a["action"] == "增配" else a["target_high"]
    return {a["asset_class"]: round(v, 3)}


# ---------- ⑤ 养老 ----------

def detect_retirement(fd: dict, ctx: dict) -> dict | None:
    rfr = ctx["rfr"]
    if rfr is None:
        return None
    fr = rfr["funding_ratio"]
    nwc = rfr["net_worth_coverage"]
    q = retirement_quadrant(fr, nwc)
    if q == "养老健康" or q == "未知":
        return None
    metric = {"rfr": fr, "nwc": nwc}
    if q == "资产充足但流动性不足":
        sev, title = "P0", "退休流动资金不足"
        finding = f"RFR 仅 {fr:.2f}，但 NWC 达 {nwc:.2f}"
        reason = ["房产等低流动性资产占比过高", "退休时可投资（金融）资产不足"]
        recs = [_rec("增加金融资产", "未来新增资金优先配置现金/固收，降低新增资金进入房产的比例",
                     reason="房产等低流动性资产占比过高，退休可投资资产不足",
                     target={"rfr": 1.0}, scenario="invest")]
        scenarios = ["invest"]
    elif q == "养老资金不足":
        sev, title = "P0", "养老资金不足"
        finding = f"RFR {fr:.2f}、NWC {nwc:.2f}，均低于 1"
        reason = ["退休资金需求现值大于可动用资产", "净资产亦不足覆盖退休生活"]
        recs = [_rec("加大养老储备", "提升储蓄率并增加长期权益/固收积累，提高退休可投资资产",
                     reason="退休资金需求现值大于可动用资产",
                     target={"rfr": 1.0}, scenario="invest")]
        scenarios = ["invest"]
    else:  # 高杠杆/资产结构问题
        sev, title = "P1", "高杠杆资产结构问题"
        finding = f"RFR {fr:.2f} 达标，但 NWC 仅 {nwc:.2f}"
        reason = ["净资产口径覆盖不足，可能存在未清负债拖累"]
        recs = [_rec("降低负债", "优先降低负债，改善净资产对退休需求的覆盖",
                     reason="净资产口径覆盖不足，可能有未清负债拖累",
                     target={"nwc": 1.0}, scenario="prepay")]
        scenarios = ["prepay"]
    return {
        "issue_id": "RETIREMENT_LIQUIDITY_001", "type": "retirement", "severity": sev,
        "title": title, "finding": finding, "reason": reason,
        "metric": metric, "target": {"rfr": 1.0},
        "recommendations": recs,
        "scenarios": scenarios,
    }


# ---------- ⑥ 家庭目标 ----------

def detect_goals(fd: dict, ctx: dict) -> dict | None:
    goals = fd.get("goals", [])
    if not goals:
        return None
    snap = ctx["snap"]
    funding = snap["goals_funding"]
    if funding["total_monthly_needed"] > 0 and not funding["feasible"]:
        return {
            "issue_id": "GOALS_OVER_COMMIT_001", "type": "goals", "severity": "P1",
            "title": "目标资金超出现金流能力",
            "finding": (f"各目标合计每月需存 {funding['total_monthly_needed']:,.0f} 元，"
                        f"但月结余仅 {funding['monthly_surplus']:,.0f} 元"),
            "reason": ["目标过多或金额过高", "超出家庭月结余承受能力"],
            "metric": {"total_monthly_needed": funding["total_monthly_needed"],
                       "monthly_surplus": funding["monthly_surplus"],
                       "shortfall": funding["shortfall"]},
            "target": {"monthly_surplus": "≥ total_monthly_needed"},
            "recommendations": [_rec(
                "评估目标优先级", "评估各目标优先级，或延长期限、下调金额，避免挤压日常现金流",
                reason="目标合计所需储蓄超出家庭月结余",
                target={"monthly_surplus": funding["total_monthly_needed"]},
                scenario="income_change")],
            "scenarios": ["income_change"],
        }
    # 无资金竞争问题，但个别目标存在缺口 → 提示最大缺口
    gaps = [g for g in snap["goals"] if g.get("gap", 0) > 0]
    if gaps:
        g = max(gaps, key=lambda x: x["gap"])
        return {
            "issue_id": "GOALS_GAP_001", "type": "goals", "severity": "P2",
            "title": f"{g['name']}存在资金缺口",
            "finding": f"目标需 {g['target_amount']:,.0f} 元，缺口 {g['gap']:,.0f} 元",
            "reason": ["当前已备资金不足以覆盖目标金额"],
            "metric": {"goal": g["name"], "gap": g["gap"],
                       "monthly_needed": g.get("monthly_needed")},
            "target": {"gap": 0},
            "recommendations": [_rec(
                "设定定存计划", "设定每月定存金额，让目标进度可跟踪",
                reason="当前已备资金不足以覆盖目标金额",
                target={"gap": 0})],
            "scenarios": [],
        }
    return None


# ---------- ⑦ 重大决策 ----------

def detect_decision(fd: dict, ctx: dict) -> dict | None:
    """识别需要主动决策的点：V1 只识别「大额闲置现金」这一最清晰信号。"""
    snap = ctx["snap"]
    em = snap["emergency_months"]
    if not em or em <= 12:
        return None
    # 有 3 年内用款目标时，现金可能是为目标储备，不提示闲置
    if _has_short_term_goal(fd.get("goals", [])):
        return None
    return {
        "issue_id": "DECISION_IDLE_CASH_001", "type": "decision", "severity": "P2",
        "title": "现金闲置，可考虑投资配置",
        "finding": f"应急资金覆盖 {em:.1f} 个月，远高于 6 个月安全线",
        "reason": ["大量现金长期闲置", "未充分发挥复利积累"],
        "metric": {"emergency_months": em},
        "target": {"emergency_months": "6~12 个月"},
        "recommendations": [_rec(
            "配置闲置现金", "保留 6~12 个月应急金后，将多余现金按目标配置投入固收/权益",
            reason="大量现金长期闲置，未发挥复利积累",
            target={"emergency_months": 12.0}, scenario="invest")],
        "scenarios": ["invest"],
    }


def _has_short_term_goal(goals) -> bool:
    from datetime import date as _date
    today = _date.today()
    for g in goals or []:
        if g.get("goal_kind") == "cashflow":
            if 0 <= int(g.get("start_year") or 0) <= 3:
                return True
        elif g.get("target_date"):
            from app.engine import metrics
            months = metrics._months_until(g["target_date"], today)
            if months is not None and 0 < months <= 36:
                return True
    return False


DETECTORS = [
    detect_cashflow,
    detect_liquidity,
    detect_debt,
    detect_allocation,
    detect_retirement,
    detect_goals,
    detect_decision,
]
