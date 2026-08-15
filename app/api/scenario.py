"""统一 Scenario API（VIP）：把 engine.scenario.run_scenario 封装成标准入口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from .. import db
from ..engine import metrics, scenario as sc
from ..schemas.scenario import (
    SCENARIO_NAMES, SCENARIO_PARAM_MODELS, CompareRequest, CompareResponse, ScenarioRequest,
)
from ..services.scenario import compare_scenarios
from .deps import get_current_user, require_vip

__all__ = ["router"]

router = APIRouter(prefix="/api/wealth", tags=["scenario"])


@router.post("/scenario/{name}")
def run_scenario_endpoint(name: str, body: ScenarioRequest, user: dict = Depends(get_current_user)):
    """统一情景模拟入口。name ∈ {buy_house, prepay, invest, income_change}。"""
    require_vip(user, "scenario")
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


def _validate_params(name: str, params: dict) -> dict:
    """按冻结的参数契约（SCENARIO_PARAM_MODELS）做强校验：类型/范围错误 → 422。"""
    model = SCENARIO_PARAM_MODELS[name]
    try:
        return model(**params).model_dump()
    except ValidationError as e:
        errs = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise HTTPException(422, "参数不合法：" + "；".join(errs))


@router.post("/scenario/{name}/compare", response_model=CompareResponse)
def compare_scenarios_endpoint(name: str, body: CompareRequest, user: dict = Depends(get_current_user)):
    """情景对比入口：baseline + 多方案完整 Overview（调整后 Wealth Score/RFR/NWC 由后端重算）。

    双层错误契约：参数类型/范围非法 → 422；参数合法但当前家庭数据不可执行 → 400。
    """
    require_vip(user, "scenario")
    if name not in SCENARIO_NAMES:
        raise HTTPException(400, f"未知场景: {name}")
    if not body.options:
        raise HTTPException(400, "请至少提供一个方案")
    data = db.dump_family(user["family_id"])
    options = []
    for o in body.options:
        params = _validate_params(name, o.params)
        options.append({"id": o.id, "name": o.name, "params": params})
    try:
        return compare_scenarios(data, name, options)
    except ValueError as e:
        raise HTTPException(400, str(e))
