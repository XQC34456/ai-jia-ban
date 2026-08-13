"""建档吸收层契约测试（Phase 6C：extract → create_confirm → apply_confirmation）。"""
from app import db
from app.agent.profile import apply_confirmation, create_confirm, extract_actions


def test_extract_actions_hits_profile():
    a = extract_actions("我月薪2万，房贷月供8000，存款50万")
    kinds = {x["kind"] for x in a}
    assert "income" in kinds and "liability" in kinds and "asset" in kinds


def test_extract_actions_no_profile():
    assert extract_actions("我最大的财务问题是什么") == []


def test_confirm_apply_roundtrip(family_id):
    actions = extract_actions("我月薪3万")
    card = create_confirm(family_id, actions)
    assert card.pending_id and card.items
    r = apply_confirmation(family_id, card.pending_id, True)
    assert r.type == "applied"
    cf = db.get_cashflows(family_id)
    assert any(c["flow_type"] == "income" and c["amount"] == 30000 for c in cf)


def test_confirm_discard(family_id):
    card = create_confirm(family_id, extract_actions("我月薪3万"))
    r = apply_confirmation(family_id, card.pending_id, False)
    assert r.type == "discarded"
    assert db.get_cashflows(family_id) == []


def test_confirm_expired(family_id):
    r = apply_confirmation(family_id, "nope", True)
    assert r.type == "error"
