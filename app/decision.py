"""兼容层：转发到 app.engine.scenario。旧 import 路径（from . import decision）不变。"""
from __future__ import annotations

from typing import Any

from . import calc_engine as ce
from . import db
from .engine.scenario import run_scenario


def simulate(family_id: int, scenario: str, params: dict[str, Any]) -> dict[str, Any]:
    """旧签名入口：内部 dump 家庭数据 + 计算快照后转发到情景引擎。"""
    data = db.dump_family(family_id)
    snap = ce.snapshot(data)
    return run_scenario(data, snap, scenario, params)
