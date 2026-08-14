"""V2.3 Advisor Brain 提示词测试：六步 SOP + 主要矛盾 + 证据 + 权衡 + 不确定 + 反例行为。

铁律：
- 提示词约束 LLM 思考（不写 if/else 状态机），测试锁定关键约束词防回归成自由 tool_loop。
- run_advisor 对含 evidence/tradeoffs/uncertainty 的 JSON 原样透传（循环结构不变）。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.advisor import _ADVISOR_SYSTEM, run_advisor


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


def _user(fid):
    return {"family_id": fid, "tier": "free"}


# ---------- 提示词约束（防回归成自由发挥 tool_loop） ----------

def test_advisor_system_has_six_step_sop():
    for kw in ("UNDERSTAND", "DIAGNOSE", "PRIORITIZE", "VERIFY", "REASON", "RECOMMEND", "ACT"):
        assert kw in _ADVISOR_SYSTEM


def test_advisor_system_forbids_best_answer():
    assert ("最优" in _ADVISOR_SYSTEM) or ("最佳" in _ADVISOR_SYSTEM)


def test_advisor_system_requires_evidence_and_tradeoff():
    assert "evidence" in _ADVISOR_SYSTEM
    assert "metric_key" in _ADVISOR_SYSTEM
    assert "tradeoffs" in _ADVISOR_SYSTEM
    assert "uncertainty" in _ADVISOR_SYSTEM
    assert "主要矛盾" in _ADVISOR_SYSTEM


def test_advisor_system_handles_counter_examples():
    for kw in ("质疑", "情绪", "绝对答案", "新事实"):
        assert kw in _ADVISOR_SYSTEM


# ---------- run_advisor 兼容新 JSON 结构 ----------

def test_run_advisor_passes_through_extended_json(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None,
         "tool_calls": [{"id": "c1", "name": "get_wealth_issues", "arguments": {}}]},
        {"content": '{"summary":"现金流优先",'
                    '"evidence":[{"claim":"储蓄率偏低","metric_key":"savings_rate"}],'
                    '"tradeoffs":[{"option":"先还贷","gain":"省利息","loss":"流动性降"}],'
                    '"uncertainty":{"confidence":"low","missing":["房贷利率"]}}',
         "tool_calls": []},
    ])
    raw = run_advisor(_user(family), "帮我看风险", fake)
    assert raw is not None
    assert raw["tool_results"]
    content = raw["content"]
    assert "evidence" in content and "tradeoffs" in content and "uncertainty" in content
