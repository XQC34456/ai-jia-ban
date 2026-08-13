"""统一 Scenario API（VIP）：把 engine.scenario.run_scenario 封装成标准入口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..engine import metrics, scenario as sc
from ..schemas.scenario import SCENARIO_NAMES, ScenarioRequest
from .deps import get_current_user, require_vip

__all__ = ["router"]

router = APIRouter(prefix="/api/wealth", tags=["scenario"])


@router.post("/scenario/{name}")
def run_scenario_endpoint(name: str, body: ScenarioRequest, user: dict = Depends(get_current_user)):
    """统一情景模拟入口。name ∈ {buy_house, prepay, invest, income_change}。"""
    require_vip(user)
    if name not in SCENARIO_NAMES:
        raise HTTPException(400, f"未知场景: {name}")
    data = db.dump_family(user["family_id"])
    snap = metrics.snapshot(data)
    result = sc.run_scenario(data, snap, name, body.params)
    # 统一错误契约：engine 的内联校验错误（如「请填写房价」）转成 HTTP 400，
    # 与其它 4xx 一样走 {"detail": "..."} 结构，前端无需区分两种错误形态。
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
