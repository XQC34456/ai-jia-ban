"""P1.3 结构化追问测试：系统缺数检测，不由 LLM 决定。

铁律：本层只读 dump_family 数据形状，缺什么问什么，绝不计算财富数字、绝不编造问题。
本测试断言：
- follow_up_questions 按意图清单检测缺失证据，最多 3 条；
- attach_layers 对 ok 回答附加 follow_up_questions（幂等，与五层同源）。
"""
import pytest

from app import db
from app.agent.followup import follow_up_questions
from app.agent.layers import attach_layers
from app.schemas.agent import AgentResponse


def _empty() -> dict:
    return {"persons": [], "cashflows": [], "assets": [], "liabilities": [], "goals": []}


# ---------- 单元：follow_up_questions 缺数检测 ----------

def test_retirement_empty_asks_age_first():
    qs = follow_up_questions("CHECK_RETIREMENT", _empty())
    assert qs, "退休测算无数据必问"
    assert "多大" in qs[0]["question"], "年龄是退休测算第一必需证据"
    assert qs[0]["reason"], "追问必须带原因"


def test_overview_empty_caps_at_three():
    qs = follow_up_questions("VIEW_OVERVIEW", _empty())
    assert len(qs) == 3, "最多 3 条追问"


def test_allocation_with_assets_no_followup():
    data = _empty()
    data["assets"] = [{"type": "存款", "value": 100000}]
    assert follow_up_questions("CHECK_ALLOCATION", data) == [], \
        "资产已录入 → 配置分析不再追问"


def test_explain_result_never_follows_up():
    assert follow_up_questions("EXPLAIN_RESULT", _empty()) == []


def test_unknown_intent_no_followup():
    assert follow_up_questions("NOPE", _empty()) == []


def test_full_data_no_followup():
    data = {
        "persons": [{"birth_year": 1990}],
        "cashflows": [
            {"flow_type": "income", "amount": 30000},
            {"flow_type": "expense", "amount": 20000},
        ],
        "assets": [{"value": 100000}],
        "liabilities": [{"monthly_payment": 3000}],
        "goals": [{"name": "养老"}],
    }
    assert follow_up_questions("CHECK_ISSUES", data) == [], \
        "现金流+负债齐全 → 风险诊断不再追问"


# ---------- 集成：attach_layers 附加 follow_up_questions ----------

@pytest.fixture
def empty_fid(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db.create_family("空家庭")


def test_attach_layers_populates_followups(empty_fid):
    resp = AgentResponse(intent="CHECK_RETIREMENT", status="ok", summary="退休测算")
    out = attach_layers(resp, empty_fid, None)
    assert out.layers is not None
    assert out.follow_up_questions, "空家庭 + 退休意图 → 追问非空"
    first = out.follow_up_questions[0]
    assert isinstance(first.question, str) and isinstance(first.reason, str)


def test_attach_layers_followup_idempotent(empty_fid):
    resp = attach_layers(
        AgentResponse(intent="CHECK_RETIREMENT", status="ok", summary="退休测算"),
        empty_fid, None)
    again = attach_layers(resp, empty_fid, None)
    assert again is resp, "已附加 layers → 幂等返回，follow_up_questions 不重复算"


def test_attach_layers_non_ok_skips_followups(empty_fid):
    resp = AgentResponse(intent="CHECK_RETIREMENT", status="need_clarification", summary="？")
    out = attach_layers(resp, empty_fid, None)
    assert out.layers is None and out.follow_up_questions == [], \
        "澄清/拒绝/错误 → 不套五层、不出追问"
