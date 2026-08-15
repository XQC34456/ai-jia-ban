"""V2.6 五层结构化回答契约测试：系统层 vs LLM 叙事层分离。

铁律：
- 系统层（①结论 ②变化 ③画像 ⑤行动）全部确定性：来自 build_overview +
  detect_invalidation 的 changed 清单，与 LLM 无关，数字绝不由 LLM 计算。
- LLM 叙事层（④判断）复用 AgentResponse.finding（已在组装层数字剥离）。
- layers 只扩不减：旧 AgentResponse 不传 layers → None，旧扁平字段不受影响。
"""
import pytest

from app import db
from app.agent.layers import attach_layers
from app.schemas.agent import AdvisorLayers, AgentResponse, ChartBlock


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 25000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 15000, "period": "月"}})
    return fid


def _resp(intent="VIEW_OVERVIEW", finding=None, recs=None, nexts=None):
    return AgentResponse(
        intent=intent, status="ok", summary="概览",
        finding=finding, recommendations=recs or [], next_actions=nexts or [],
    )


# ---------- Schema 只扩不减 ----------

def test_schema_layers_defaults_none():
    r = AgentResponse(intent="VIEW_OVERVIEW", status="ok", summary="x")
    assert r.layers is None


def test_layers_models_instantiate():
    c = ChartBlock(chart="radar", question="q", data={"a": 1})
    assert c.data == {"a": 1}
    l = AdvisorLayers(conclusion="c", charts=[c])
    assert l.conclusion == "c"


# ---------- 系统层确定性 ----------

def test_attach_builds_conclusion_and_charts(family):
    resp = attach_layers(_resp("VIEW_OVERVIEW"), family, invalidation=None)
    assert resp.layers is not None
    # ① 结论：含 wealth_level（确定性，非 LLM 拼写）
    assert resp.layers.conclusion
    assert "家庭财务" in resp.layers.conclusion
    # ③ 画像：VIEW_OVERVIEW → radar + cashflow
    charts = {c.chart for c in resp.layers.charts}
    assert "radar" in charts
    assert "cashflow" in charts


def test_retirement_intent_triggers_only_retirement_chart(family):
    resp = attach_layers(_resp("CHECK_RETIREMENT"), family, invalidation=None)
    assert {c.chart for c in resp.layers.charts} == {"retirement"}


def test_allocation_intent_triggers_allocation_chart(family):
    resp = attach_layers(_resp("CHECK_ALLOCATION"), family, invalidation=None)
    assert {c.chart for c in resp.layers.charts} == {"allocation"}


def test_scenario_compare_has_no_charts(family):
    resp = attach_layers(_resp("SCENARIO_COMPARE"), family, invalidation=None)
    assert resp.layers.charts == []


# ---------- ④ LLM 叙事层 + ⑤ 系统行动层分离 ----------

def test_judgment_reuses_finding(family):
    resp = attach_layers(_resp("VIEW_OVERVIEW", finding="我的判断叙事"), family, invalidation=None)
    assert resp.layers.judgment == "我的判断叙事"


def test_action_plan_is_deterministic_not_resp(family):
    """⑤行动来自 Decision build_issues 的确定性建议，绝不透传 LLM 的 recommendations。"""
    resp = attach_layers(
        _resp("VIEW_OVERVIEW", recs=["LLM建议A"], nexts=["LLM行动B"]), family, invalidation=None,
    )
    assert "LLM建议A" not in resp.layers.action_plan
    assert "LLM行动B" not in resp.layers.action_plan
    for a in resp.layers.action_plan:
        assert isinstance(a, str) and a


# ---------- ② 关键变化：确定性 diff 人话翻译 ----------

def test_changes_from_invalidation(family):
    invalidation = [{"key": "dti", "before": 0.3, "after": 0.5}]
    resp = attach_layers(_resp("VIEW_OVERVIEW"), family, invalidation=invalidation)
    assert resp.layers.changes == [
        {"key": "dti", "label": "负债率", "before": 0.3, "after": 0.5},
    ]


def test_no_invalidation_yields_empty_changes(family):
    resp = attach_layers(_resp("VIEW_OVERVIEW"), family, invalidation=None)
    assert resp.layers.changes == []


# ---------- 非 ok 状态不套五层 ----------

def test_non_ok_status_skips_layers(family):
    resp = _resp("VIEW_OVERVIEW")
    resp = resp.model_copy(update={"status": "need_clarification"})
    out = attach_layers(resp, family, invalidation=None)
    assert out.layers is None


# ---------- 幂等 ----------

def test_attach_idempotent(family):
    r1 = attach_layers(_resp("VIEW_OVERVIEW"), family, invalidation=None)
    r2 = attach_layers(r1, family, invalidation=[{"key": "dti", "before": 0.3, "after": 0.5}])
    assert r2 is r1
    assert r2.layers.changes == []  # 已附加 → 不再重复计算
