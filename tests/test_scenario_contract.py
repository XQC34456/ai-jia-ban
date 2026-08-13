"""C3.5 契约冻结守门测试：锁定 Scenario 名称 / 九指标 / 参数模型 / 双层错误契约。

约束：只 import app.schemas（契约层）+ app.engine（仅为核对枚举一致），
绝不校验财富公式的正确性——那是 engine 单测的职责。
"""
from __future__ import annotations

from typing import get_args

import pytest
from pydantic import BaseModel, ValidationError

from app.engine import allocation, scenario as engine_scenario
from app.schemas import Overview
from app.schemas.scenario import (
    SCENARIO_NAMES, SCENARIO_METRICS, SCENARIO_METRIC_KEYS, SCENARIO_PARAM_MODELS,
    BuyHouseParams, PrepayParams, InvestParams, IncomeChangeParams,
)


def _upgrade(client, h):
    client.post("/api/upgrade", headers=h)


def _seed(client, h):
    client.post("/api/family/entity/person", headers=h, json={"name": "本人", "relation": "本人", "birth_year": 1990})
    client.post("/api/family/entity/asset", headers=h, json={"type": "存款", "name": "现金", "value": 1500000})
    client.post("/api/family/entity/asset", headers=h, json={"type": "股票", "name": "股票", "value": 1500000})
    client.post("/api/family/entity/liability", headers=h,
                json={"type": "房贷", "name": "房贷", "principal": 2000000, "monthly_payment": 12000,
                      "interest_rate": 0.035, "remaining_months": 240})
    client.post("/api/family/entity/cashflow", headers=h, json={"flow_type": "income", "amount": 50000, "period": "月"})
    client.post("/api/family/entity/cashflow", headers=h, json={"flow_type": "expense", "amount": 20000, "period": "月"})


# ---------- ① Scenario 名称冻结 ----------

def test_scenario_names_frozen():
    assert set(SCENARIO_NAMES) == {"buy_house", "prepay", "invest", "income_change"}
    assert set(engine_scenario.SCENARIOS) == set(SCENARIO_NAMES)
    assert set(SCENARIO_PARAM_MODELS) == set(SCENARIO_NAMES)


# ---------- ③ 九指标冻结 ----------

def test_metrics_frozen_nine_in_order():
    assert SCENARIO_METRIC_KEYS == (
        "net_worth", "wealth_score", "rfr", "nwc", "cashflow",
        "liquidity", "dti", "real_estate_pct", "goal_completion",
    )
    assert len(SCENARIO_METRICS) == 9


# ---------- ④ 参数模型：类型/范围/必填 ----------

def test_param_models_are_pydantic():
    for model in SCENARIO_PARAM_MODELS.values():
        assert issubclass(model, BaseModel)


def test_param_models_validate_ranges():
    assert BuyHouseParams(price=1).down_payment_ratio == 0.3       # 默认值生效
    with pytest.raises(ValidationError):
        BuyHouseParams(price=-100)
    with pytest.raises(ValidationError):
        BuyHouseParams(price=1, loan_years=80)
    with pytest.raises(ValidationError):
        PrepayParams(prepay_amount=1, method="xxx")
    with pytest.raises(ValidationError):
        InvestParams(amount=1, to_class="nope")
    with pytest.raises(ValidationError):
        IncomeChangeParams(pct_change=-1)


def test_invest_to_class_matches_engine_asset_classes():
    """InvestParams.to_class 的合法取值必须与 engine 六大类一致，防止两处枚举漂移。"""
    allowed = get_args(InvestParams.model_fields["to_class"].annotation)
    assert set(allowed) == set(allocation.ASSET_CLASSES)


# ---------- ④ 双层错误契约：类型/范围 422，业务不可执行 400 ----------

def test_compare_param_type_error_422(client, auth_headers):
    _upgrade(client, auth_headers)
    r = client.post("/api/wealth/scenario/invest/compare", headers=auth_headers,
                    json={"options": [{"id": "A", "params": {"amount": -100}}]})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_compare_business_unexecutable_400(client, auth_headers):
    _seed(client, auth_headers)
    _upgrade(client, auth_headers)
    r = client.post("/api/wealth/scenario/invest/compare", headers=auth_headers,
                    json={"options": [{"id": "A", "params": {"amount": 100000000, "to_class": "equity"}}]})
    assert r.status_code == 400
    assert "detail" in r.json()


# ---------- ⑥ known_limitations 透传 ----------

def test_compare_passthrough_known_limitations(client, auth_headers):
    _seed(client, auth_headers)
    _upgrade(client, auth_headers)
    r = client.post("/api/wealth/scenario/income_change/compare", headers=auth_headers,
                    json={"options": [{"id": "A", "params": {"pct_change": 0.1}}]})
    assert r.status_code == 200
    body = r.json()
    expected = [
        "retirement_debt_service_not_included",
        "goal_retirement_semantic_overlap",
        "other_asset_liquidity_assumption",
    ]
    assert body["baseline"]["retirement"]["known_limitations"] == expected
    # 方案变化不得隐藏限制：每个 option 的 overview 透传同一份限制
    for opt in body["options"]:
        assert opt["overview"]["retirement"]["known_limitations"] == expected
