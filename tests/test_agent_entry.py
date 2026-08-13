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
