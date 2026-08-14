"""V2.1 端到端契约测试：converse 预取 Wealth Context → LLM 兜底注入（打通链路）。

H 评测雏形：断言「意图正确 + context 数字正确 + source 正确 + 无编造」。
铁律：
- 只在 route_intent 的 LLM 兜底注入 context（关键词命中的确定性路径不注入）。
- 参数抽取不注入 context（防 context 数字被 LLM 误当参数默认值）。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider, converse
from app.agent.context import build_wealth_context
from app.services import build_overview


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


def test_converse_chain_injects_context(family):
    """用户问「财富评分多少」（关键词不命中 → LLM 兜底）→ context 注入 FakeLLM。"""
    user = {"family_id": family, "tier": "free"}
    fake = FakeLLMProvider(script=[{"intent": "VIEW_OVERVIEW"}])
    converse("我的财富评分是多少", user, llm=fake)
    assert fake.last_context is not None
    assert "overview.wealth_score" in fake.last_context  # source 标注出现在 context 文本


def test_converse_keyword_hit_skips_llm(family):
    """「风险问题」关键词命中 CHECK_ISSUES → 确定性路径，不调 LLM、不注入 context。"""
    user = {"family_id": family, "tier": "free"}
    fake = FakeLLMProvider(script=[{"intent": "CHECK_ISSUES"}])
    converse("我有什么风险问题", user, llm=fake)
    assert fake.last_context is None


def test_golden_context_numbers_match_engine(family):
    """黄金场景：context 数字 == build_overview，且每个带 value 的数字都有 source。"""
    data = db.dump_family(family)
    ctx = build_wealth_context(data)
    ov = build_overview(data)
    assert ctx["financial"]["wealth_score"]["value"] == ov["wealth_score"]
    assert ctx["financial"]["net_worth"]["value"] == ov["net_worth"]
    for item in ctx["financial"].values():
        if isinstance(item, dict) and item.get("value") is not None:
            assert item.get("source"), "带 value 的数字必须带 source"
