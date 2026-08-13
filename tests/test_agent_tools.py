"""A2 Tool Adapter 测试：四个取数工具 + 结构化错误转译 + 无财富计算守门。

约束：工具层只获取事实（调 service / 做 alias 转译 / 做参数校验 / 转译错误），
绝不计算 Wealth Score / RFR / NWC / DTI / 占比 / 风险 / 推荐，绝不调 LLM。
"""
from __future__ import annotations

import inspect

import pytest

from app import db
from app.agent.tools import (
    ToolError, resolve_scenario_name,
    get_overview, get_issues, get_goals, compare_scenario,
)
from app.schemas.scenario import SCENARIO_METRIC_KEYS


def _token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def _user(headers: dict) -> dict:
    """从 auth_headers 还原真实 user 记录（含 family_id / tier）。"""
    return db.get_user_by_token(_token(headers))


def _vip_user(client, headers) -> dict:
    client.post("/api/upgrade", headers=headers)
    return db.get_user_by_token(_token(headers))


def _seed(client, headers):
    client.post("/api/family/entity/person", headers=headers,
                json={"name": "本人", "relation": "本人", "birth_year": 1990})
    client.post("/api/family/entity/asset", headers=headers,
                json={"type": "存款", "name": "现金", "value": 1500000})
    client.post("/api/family/entity/asset", headers=headers,
                json={"type": "股票", "name": "股票", "value": 1500000})
    client.post("/api/family/entity/liability", headers=headers,
                json={"type": "房贷", "name": "房贷", "principal": 2000000,
                      "monthly_payment": 12000, "interest_rate": 0.035, "remaining_months": 240})
    client.post("/api/family/entity/cashflow", headers=headers,
                json={"flow_type": "income", "amount": 50000, "period": "月"})
    client.post("/api/family/entity/cashflow", headers=headers,
                json={"flow_type": "expense", "amount": 20000, "period": "月"})


# ---------- 四个取数工具：正常路径 ----------

def test_get_overview_normal(client, auth_headers):
    o = get_overview(_user(auth_headers))
    assert o["currency"] == "CNY"
    assert isinstance(o["wealth_score"], int)
    assert isinstance(o["net_worth"], (int, float))
    assert o["cashflow"] is not None and o["liquidity"] is not None


def test_get_overview_exposes_retirement_and_allocation_subfields(client, auth_headers):
    """CHECK_RETIREMENT → overview.retirement；CHECK_ALLOCATION → overview.asset_allocation（不新增端点）。"""
    _seed(client, auth_headers)
    o = get_overview(_user(auth_headers))
    assert "retirement" in o                      # CHECK_RETIREMENT 读这里
    assert "asset_allocation" in o                # CHECK_ALLOCATION 读这里
    assert o["retirement"] is not None            # 有 birth_year + 支出 → 退休块已产出


def test_get_issues_normal(client, auth_headers):
    _seed(client, auth_headers)
    issues = get_issues(_user(auth_headers))
    assert isinstance(issues, dict)
    for key in ("issues", "alerts", "priorities", "recommendations"):
        assert key in issues


def test_get_goals_normal(client, auth_headers):
    client.post("/api/family/entity/goal", headers=auth_headers,
                json={"type": "教育", "name": "孩子大学", "target_amount": 500000,
                      "target_date": "2030-01-01"})
    g = get_goals(_user(auth_headers))
    assert isinstance(g, dict) and "goals" in g   # 与 /api/wealth/goals 同形


# ---------- compare_scenario：正常 + 三层错误 ----------

def test_compare_scenario_normal(client, auth_headers):
    _seed(client, auth_headers)
    r = compare_scenario(_vip_user(client, auth_headers), "invest",
                         {"amount": 300000, "to_class": "equity"})
    assert r["scenario"] == "invest"
    assert set(r) >= {"baseline", "options", "comparison"}
    # 对比表行序 = C3.5 冻结的九指标顺序（工具只透传，不重排）
    assert [m["key"] for m in r["comparison"]["A"]] == list(SCENARIO_METRIC_KEYS)


def test_compare_scenario_forbidden_free_user(client, auth_headers):
    """免费用户 → 结构化权限状态（ToolError kind=forbidden），不写自然语言话术。"""
    with pytest.raises(ToolError) as e:
        compare_scenario(_user(auth_headers), "invest", {"amount": 300000})
    assert e.value.kind == "forbidden"


def test_compare_scenario_invalid_params(client, auth_headers):
    """参数类型/范围错误 → kind=invalid_params（422 等价）。"""
    with pytest.raises(ToolError) as e:
        compare_scenario(_vip_user(client, auth_headers), "invest", {"amount": -100})
    assert e.value.kind == "invalid_params"
    assert e.value.detail.get("errors")


def test_compare_scenario_unexecutable(client, auth_headers):
    """参数合法但业务不可执行 → kind=unexecutable（400 等价）。"""
    _seed(client, auth_headers)
    with pytest.raises(ToolError) as e:
        compare_scenario(_vip_user(client, auth_headers), "invest",
                         {"amount": 100000000, "to_class": "equity"})
    assert e.value.kind == "unexecutable"


# ---------- 场景 alias → frozen name ----------

def test_resolve_scenario_alias():
    assert resolve_scenario_name("买房") == "buy_house"
    assert resolve_scenario_name("提前还贷") == "prepay"
    assert resolve_scenario_name("投股票") == "invest"
    assert resolve_scenario_name("收入下降") == "income_change"
    # 已是 frozen name 则原样通过
    assert resolve_scenario_name("buy_house") == "buy_house"


def test_resolve_unknown_scenario():
    with pytest.raises(ToolError) as e:
        resolve_scenario_name("炒币")
    assert e.value.kind == "unknown_scenario"


# ---------- 守门：工具层不得包含财富计算逻辑 ----------

def test_tools_do_not_import_engine():
    """守门：Tool Adapter 不得引用财富计算层（engine）——财富公式唯一入口在 service。"""
    import app.agent.tools as t
    src = inspect.getsource(t)
    assert "engine" not in src
    assert "app.engine" not in src


def test_compare_scenario_delegates_to_service(monkeypatch, client, auth_headers):
    """守门：compare_scenario 必须原样透传 compare_scenarios 的返回，不得自己重算 comparison。"""
    import app.agent.tools as t
    fake = {"scenario": "invest", "baseline": {"net_worth": 1},
            "options": [], "comparison": {"A": [{"key": "net_worth", "delta": 999}]}}
    captured = {}

    def spy(data, name, options):
        captured["name"] = name
        captured["options"] = options
        return fake

    monkeypatch.setattr(t, "compare_scenarios", spy)
    result = compare_scenario(_vip_user(client, auth_headers), "投股票", {"amount": 1})
    assert result is fake                     # 返回同一个对象 → 无二次加工/重算
    assert captured["name"] == "invest"       # alias 已转译
