"""P1.3 结构化追问：系统缺数检测，不由 LLM 决定。

铁律：本模块只读 dump_family 的数据形状，判断「回答当前意图所需的必需证据是否已录入」。
缺什么 → 产出结构化追问（question 是要问用户的问题，reason 是为什么缺）。
绝不计算财富数字、绝不编造问题，最多 3 条（按清单顺序）。

本模块为纯函数：follow_up_questions(intent, data) -> list[dict]。
入口在 attach_layers()（唯一同时拿到 intent + dump_family 的地方）。
"""
from __future__ import annotations

__all__ = ["follow_up_questions"]


# ---- 数据形状检测（只判有无，不读数值、不算数） ----

def _has_age(data: dict) -> bool:
    return any(p.get("birth_year") for p in (data.get("persons") or []))


def _has_income(data: dict) -> bool:
    return any(c.get("flow_type") == "income" for c in (data.get("cashflows") or []))


def _has_expense(data: dict) -> bool:
    return any(c.get("flow_type") == "expense" for c in (data.get("cashflows") or []))


def _has_asset(data: dict) -> bool:
    return bool(data.get("assets"))


def _has_liability(data: dict) -> bool:
    return bool(data.get("liabilities"))


def _has_goal(data: dict) -> bool:
    return bool(data.get("goals"))


# ---- 意图 → 追问清单：[(检测函数, 问题, 为什么缺)] ----

_INTENT_CHECKS: dict[str, list[tuple]] = {
    "VIEW_OVERVIEW": [
        (_has_income, "你的月收入大概多少？", "总览需要收入数据算月结余"),
        (_has_expense, "你的月支出大概多少？", "总览需要支出数据算月结余"),
        (_has_asset, "你的主要资产有哪些？", "总览需要资产数据算净资产"),
    ],
    "CHECK_ISSUES": [
        (_has_income, "你的月收入是多少？", "风险诊断需要收入现金流"),
        (_has_expense, "你的月支出是多少？", "风险诊断需要支出现金流"),
        (_has_liability, "你有房贷、车贷等负债吗？", "债务风险诊断需要负债数据"),
    ],
    "CHECK_RETIREMENT": [
        (_has_age, "你今年多大？", "退休测算需要年龄推算退休年限"),
        (_has_asset, "你目前攒了多少养老钱？", "退休测算需要资产数据算覆盖"),
        (_has_income, "你现在每月收入多少？", "退休测算需要收入算储蓄能力"),
    ],
    "CHECK_ALLOCATION": [
        (_has_asset, "你的钱都放在哪（存款/基金/房产）？", "配置分析需要资产分布"),
    ],
    "CHECK_GOALS": [
        (_has_goal, "你有什么财务目标（教育金/养老/买房）？", "目标进度需要先有目标"),
    ],
    "SCENARIO_COMPARE": [
        (_has_income, "你现在的月收入是多少？", "情景模拟需要收入作为基线"),
        (_has_expense, "你现在的月支出是多少？", "情景模拟需要支出作为基线"),
        (_has_asset, "你目前有哪些资产？", "情景模拟需要资产作为基线"),
    ],
    "EXPLAIN_RESULT": [],
}


def follow_up_questions(intent: str, data: dict) -> list[dict]:
    """检测当前意图缺失的必需证据，产出结构化追问（最多 3 条，按清单顺序）。"""
    out: list[dict] = []
    for check, question, reason in _INTENT_CHECKS.get(intent, []):
        if not check(data):
            out.append({"question": question, "reason": reason})
        if len(out) >= 3:
            break
    return out
