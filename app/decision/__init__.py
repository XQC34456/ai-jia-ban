"""Decision Layer：判断层（规则引擎，确定性，零 LLM）。

Engine 算数字，Decision Layer 判问题——把「数字」翻译成「问题 / 原因 / 优先级 / 建议」。
输出统一为财富问题对象（Issue），供 AI Agent / 前端 / 报告 / 提醒共同读取。

simulate 是历史「决策模拟」入口的兼容转发：内部 dump 家庭数据 + 快照后转给情景引擎
（引擎层收 data/snap，兼容层仍收 family_id；主链路 /api/decision 依赖它）。
"""
from __future__ import annotations

from typing import Any

from .issue import build_issues, compute_context
from .quadrant import retirement_quadrant

from .. import calc_engine as ce
from .. import db
from ..engine.scenario import run_scenario

__all__ = ["build_issues", "compute_context", "retirement_quadrant", "simulate"]


def simulate(family_id: int, scenario: str, params: dict[str, Any]) -> dict[str, Any]:
    """旧签名入口：内部 dump 家庭数据 + 计算快照后转发到情景引擎。"""
    data = db.dump_family(family_id)
    snap = ce.snapshot(data)
    return run_scenario(data, snap, scenario, params)
