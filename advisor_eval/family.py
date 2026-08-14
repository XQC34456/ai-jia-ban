"""评测专用家庭 fixture：db 直接建档（非 LLM、非 converse/API）。

铁律：这里的数据是「外部家庭状态」，不经 converse/API，不产生对话记忆。
数字由评测脚本设定（与 LLM 无关），用于驱动财富引擎产出确定性的顾问判断。

家庭画像（典型中国家庭）：
- 本人（男 40 岁）+ 配偶（女 38 岁）+ 孩子（10 岁）
- 月收入 4 万（本人 2.5 + 配偶 1.5），月支出 3 万（日常 1.5 + 教育 0.3 + 房贷月供 1.2）
- 资产：现金 50 万 + 股票基金 30 万；负债：房贷 200 万（月供 1.2 万，DTI 30%）
- 目标：孩子教育金 100 万（已存 10 万）；无保险（顾问应主动发现的缺口）
"""
from __future__ import annotations

from app import db

__all__ = ["build_family", "add_insurance", "add_income"]


def build_family(name: str = "典型中国家庭") -> int:
    """建档并返回 family_id。房贷月供只放 liability.monthly_payment（engine 会自动
    把它计入 monthly_expense），不重复放进 expense。"""
    fid = db.create_family(name)
    # 成员
    db.apply_action(fid, {"kind": "person", "fields": {
        "name": "本人", "relation": "本人", "birth_year": 1986, "monthly_income": 25000}})
    db.apply_action(fid, {"kind": "person", "fields": {
        "name": "配偶", "relation": "配偶", "birth_year": 1988, "monthly_income": 15000}})
    db.apply_action(fid, {"kind": "person", "fields": {
        "name": "孩子", "relation": "子女", "birth_year": 2016}})
    # 收入（现金流计算口径来自 cashflow 表）
    db.apply_action(fid, {"kind": "income", "fields": {
        "category": "工资", "amount": 25000, "period": "月"}})
    db.apply_action(fid, {"kind": "income", "fields": {
        "category": "工资", "amount": 15000, "period": "月"}})
    # 支出（不含房贷月供——房贷走 liability.monthly_payment）
    db.apply_action(fid, {"kind": "expense", "fields": {
        "category": "日常", "amount": 15000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense", "fields": {
        "category": "教育", "amount": 3000, "period": "月"}})
    # 资产
    db.apply_action(fid, {"kind": "asset", "fields": {
        "type": "存款", "name": "现金", "value": 500000}})
    db.apply_action(fid, {"kind": "asset", "fields": {
        "type": "股票", "name": "股票基金", "value": 300000}})
    # 负债
    db.apply_action(fid, {"kind": "liability", "fields": {
        "type": "房贷", "name": "房贷", "principal": 2000000,
        "monthly_payment": 12000, "interest_rate": 0.035, "remaining_months": 240}})
    # 目标
    db.apply_action(fid, {"kind": "goal", "fields": {
        "type": "教育", "name": "孩子教育金", "target_amount": 1000000,
        "current_saved": 100000}})
    return fid


def add_insurance(fid: int, coverage: float = 3000000, annual_premium: float = 12000) -> None:
    """评测专用外部状态变更：直接 INSERT insurance 表（不经 converse/API）。

    apply_action 无 insurance kind，故用 SQL 直插；明确标注这是「家庭之外的真实
    事实变化」，用于观察点 4 测失效检测。
    """
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO insurance (family_id, type, name, annual_premium, coverage) "
        "VALUES (?, ?, ?, ?, ?)",
        (fid, "寿险", "家庭保障计划", annual_premium, coverage),
    )
    conn.commit()


def add_income(fid: int, amount: float = 15000) -> None:
    """评测专用外部状态变更：新增一笔收入（apply_action，经公开接口）。

    改变 cashflow_surplus → 触发 validity_conditions 的失效检测（观察点 4 的正向验证）。
    """
    db.apply_action(fid, {"kind": "income", "fields": {
        "category": "工资", "amount": amount, "period": "月"}})
