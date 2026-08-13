"""对话编排（抽取 → 确认 → 落地 → 重算）集成测试。"""
import pytest

from app import chat, db


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db.create_family("测试家庭")


def test_full_confirm_flow(family):
    # 抽取 → 确认
    r = chat.handle_message(family, "我月薪2万，老婆1万5")
    assert r["type"] == "confirm"
    assert len(r["items"]) >= 2

    # 确认 → 落地 → 重算
    r2 = chat.handle_confirm(family, r["pending_id"], True)
    assert r2["type"] == "applied"
    assert r2["snapshot"]["monthly_income"] == 35000


def test_cancel_flow(family):
    r = chat.handle_message(family, "存款50万")
    r2 = chat.handle_confirm(family, r["pending_id"], False)
    assert r2["type"] == "discarded"
    snap = db.dump_family(family)
    assert snap["assets"] == []


def test_question_returns_grounded_answer(family):
    chat.handle_confirm(family, chat.handle_message(family, "我月薪2万")["pending_id"], True)
    chat.handle_confirm(family, chat.handle_message(family, "存款50万")["pending_id"], True)
    r = chat.handle_message(family, "我家现在最大的风险是什么？")
    assert r["type"] == "answer"
    assert r["snapshot"] is not None
    assert len(r["message"]) > 0
