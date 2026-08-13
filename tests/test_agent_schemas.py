"""ConfirmCard / AppliedResponse 契约测试（Phase 6C 建档吸收层新增 schema）。"""
from app.schemas.agent import AppliedResponse, ConfirmCard


def test_confirm_card_shape():
    c = ConfirmCard(pending_id="abc", message="确认", items=["a", "b"])
    assert c.type == "confirm"
    assert c.model_dump()["pending_id"] == "abc"
    assert c.model_dump()["items"] == ["a", "b"]


def test_confirm_card_items_default_empty():
    c = ConfirmCard(pending_id="abc", message="确认")
    assert c.items == []


def test_applied_response_shape():
    a = AppliedResponse(type="applied", message="已记录")
    assert a.type == "applied"
    d = AppliedResponse(type="discarded", message="已忽略")
    assert d.type == "discarded"
    e = AppliedResponse(type="error", message="已失效")
    assert e.type == "error"
