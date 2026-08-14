"""converse() 统一入口契约测试（建档优先，否则走七意图 Agent）。"""
from app.agent.entry import converse
from app.agent.provider import NullProvider
from app.schemas.agent import AgentResponse, ConfirmCard


def _user(family_id):
    return {"family_id": family_id, "tier": "free", "id": 1}


def test_converse_routes_to_confirm(family_id):
    r = converse("我月薪3万", _user(family_id), llm=NullProvider())
    assert isinstance(r, ConfirmCard)


def test_converse_routes_to_agent(family_id):
    r = converse("我最大的财务问题是什么", _user(family_id), llm=NullProvider())
    assert isinstance(r, AgentResponse)
    assert r.intent == "CHECK_ISSUES"


def test_converse_passes_invalidation_to_memory(family_id, monkeypatch):
    """entry 层：converse 把 detect_invalidation 的 changed 清单透传给 build_memory_context。"""
    from app.agent import entry
    captured = {}

    def _fake_invalidation(fid):
        return [{"key": "insurance_count", "before": 0, "after": 1}]

    def _spy_memory(fid, conversation_turns=None, invalidation=None):
        captured["invalidation"] = invalidation
        return ""

    monkeypatch.setattr(entry, "detect_invalidation", _fake_invalidation)
    monkeypatch.setattr(entry, "build_memory_context", _spy_memory)
    converse("我最大的财务问题是什么", _user(family_id), llm=NullProvider())
    assert captured["invalidation"] == [{"key": "insurance_count", "before": 0, "after": 1}]
