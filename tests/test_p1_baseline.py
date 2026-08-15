"""P1.1 确定性基线测试：priorities/metrics 不随 LLM 工具选择漂移。

铁律：数字由 Engine/Decision 确定性算，LLM 绝不计算/编造。
本测试用 FakeLLMProvider 让 LLM「故意不调 get_wealth_issues」，断言基线仍保证
priorities + overview 指标恒在（系统层保证，不由 LLM 决定）。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.advisor import _with_baseline, advise


@pytest.fixture
def fid(tmp_path, monkeypatch):
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


def _call(name, args=None):
    return {"id": "c1", "name": name, "arguments": args or {}}


# ---------- 单元：_with_baseline 补缺 + 去重 ----------

def test_with_baseline_adds_missing_and_skips_existing(fid):
    user = _user(fid)
    # LLM 只调了 get_cashflow，没调 get_wealth_issues / get_wealth_overview
    tr = [{"name": "get_cashflow", "result": {"data_origin": "real", "cashflow": {"surplus": 10000}}}]
    merged = _with_baseline(tr, "CHECK_ISSUES", user)
    names = [t["name"] for t in merged]
    assert names.count("get_cashflow") == 1, "已调工具不重复补"
    assert "get_wealth_issues" in names, "基线应补 get_wealth_issues"
    assert "get_wealth_overview" in names, "基线应补 get_wealth_overview"


def test_with_baseline_skips_when_no_tools(fid):
    """纯聊天/知识问答（零工具）→ 不注入财富画像基线（否则「天气」带出财富指标）。"""
    assert _with_baseline([], "VIEW_OVERVIEW", _user(fid)) == []


# ---------- 集成：LLM 故意跳过 issues，priorities 仍恒在 ----------

def test_advise_priorities_deterministic_when_llm_skips_issues(fid):
    fake = FakeLLMProvider(
        script=[{"summary": "现金流偏紧"}],
        chat_script=[
            {"content": None, "tool_calls": [_call("get_cashflow")]},
            {"content": '{"summary": "现金流偏紧"}', "tool_calls": []},
        ],
    )
    resp = advise(_user(fid), "我失业半年能撑多久", fake, intent="CHECK_ISSUES")
    assert resp is not None
    assert resp.priorities, "基线应保证 get_wealth_issues 恒在 → priorities 非空"
    assert any(m.key == "liquidity_months" for m in resp.metrics), \
        "基线应保证 get_wealth_overview 恒在 → 应急月数指标存在"
