"""V2.2 Tool Schema 注册表测试：9 个只读工具 + execute_tool（带 data_origin）。

铁律：
- 工具 = AI 顾问的眼睛和手，只读 Engine/Decision（real）或沙盘（scenario），绝不写库。
- 工具结果带 data_origin（real/scenario），供 LLM 区分现状与模拟。
- scenario 工具受 VIP 门（tier != vip → forbidden），复用 A2 契约，不重写校验。
"""
import pytest

from app import db
from app.agent.tools import ToolError


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 30000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _user(fid, tier="free"):
    return {"family_id": fid, "tier": tier}


# ---------- Schema 完整性 ----------

def test_tool_schemas_has_9_tools():
    from app.agent.tool_schemas import TOOL_SCHEMAS
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert names == {
        "get_family_profile", "get_wealth_overview", "get_wealth_issues",
        "get_cashflow", "get_allocation", "get_retirement", "get_goals",
        "run_scenario", "compare_scenarios",
    }


# ---------- 只读工具（real） ----------

def test_execute_overview_real_origin(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("get_wealth_overview", {}, _user(family))
    assert out["data_origin"] == "real"
    assert "wealth_score" in out["overview"]


def test_execute_issues_real_origin(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("get_wealth_issues", {}, _user(family))
    assert out["data_origin"] == "real"
    assert "issues" in out


def test_execute_cashflow_reads_subfield(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("get_cashflow", {}, _user(family))
    assert out["data_origin"] == "real"
    assert "surplus" in out["cashflow"]


def test_execute_retirement_and_allocation_subfields(family):
    from app.agent.tool_schemas import execute_tool
    ret = execute_tool("get_retirement", {}, _user(family))
    assert ret["data_origin"] == "real"
    assert "rfr" in ret["retirement"]
    alloc = execute_tool("get_allocation", {}, _user(family))
    assert "classes" in alloc["asset_allocation"]


def test_execute_goals_real_origin(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("get_goals", {}, _user(family))
    assert out["data_origin"] == "real"
    assert "goals" in out


def test_execute_family_profile_real_origin(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("get_family_profile", {}, _user(family))
    assert out["data_origin"] == "real"
    assert "persons" in out["family"]


# ---------- scenario 工具（VIP 门 + scenario 来源） ----------

def test_execute_run_scenario_vip_gate(family):
    from app.agent.tool_schemas import execute_tool
    with pytest.raises(ToolError) as e:
        execute_tool("run_scenario",
                     {"name": "income_change", "params": {"pct_change": -0.3}},
                     _user(family, "free"))
    assert e.value.kind == "forbidden"


def test_execute_run_scenario_single_option(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("run_scenario",
                       {"name": "income_change", "params": {"pct_change": -0.3}},
                       _user(family, "vip"))
    assert out["data_origin"] == "scenario"
    assert len(out["options"]) == 1
    assert "comparison" in out


def test_execute_compare_scenarios_multi_option(family):
    from app.agent.tool_schemas import execute_tool
    out = execute_tool("compare_scenarios",
                       {"name": "income_change",
                        "options": [{"params": {"pct_change": -0.1}},
                                    {"params": {"pct_change": -0.3}}]},
                       _user(family, "vip"))
    assert out["data_origin"] == "scenario"
    assert len(out["options"]) == 2
    assert set(out["comparison"].keys()) == {"A", "B"}


def test_execute_unknown_tool_raises(family):
    from app.agent.tool_schemas import execute_tool
    with pytest.raises(ToolError):
        execute_tool("nope", {}, _user(family))
