"""P1.4 建议采纳闭环测试：⑤ 下一步 → 可采纳结构（action_plans）→ 落地 action_plan。

铁律：数字由 Decision 确定性算，本层只把 recommendations 逐字透传成可采纳结构，
从 recommendation_id 解析 issue_id，绝不计算财富数字、绝不自造建议。
"""
import pytest

from app import db
from app.agent.layers import _build_action_plan, _build_action_plans, attach_layers
from app.schemas.agent import AgentResponse
from app.services import build_overview


@pytest.fixture
def fid(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 10000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _overview(fid):
    return build_overview(db.dump_family(fid))


def test_build_action_plans_derives_issue_id(fid):
    plans = _build_action_plans(_overview(fid))
    assert plans, "负现金流应产出可采纳建议"
    first = plans[0]
    assert first["issue_id"] == "CASHFLOW_NEGATIVE_001"
    assert first["recommendation_id"] == "CASHFLOW_NEGATIVE_001-R1"
    assert first["action"] == "削减非必要支出"
    assert first["detail"], "detail 逐字透传"


def test_build_action_plan_strings_unchanged(fid):
    strings = _build_action_plan(_overview(fid))
    assert strings, "字符串短句仍产出"
    assert all(isinstance(s, str) and s for s in strings)
    assert strings[0].startswith("削减非必要支出：")


def test_attach_layers_populates_action_plans(fid):
    resp = AgentResponse(intent="CHECK_ISSUES", status="ok", summary="风险诊断")
    out = attach_layers(resp, fid, None)
    assert out.layers is not None
    assert out.layers.action_plans, "可采纳结构非空"
    ap = out.layers.action_plans[0]
    assert ap.issue_id == "CASHFLOW_NEGATIVE_001" and ap.action == "削减非必要支出"
    # 向后兼容：action_plan 字符串仍与 action_plans 一一对应
    assert len(out.layers.action_plan) == len(out.layers.action_plans)
