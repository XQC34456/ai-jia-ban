"""review-status 端点逻辑测试：确定性失效检测 + 失效原因持久展示。"""
import pytest

from app import db
from app.agent.memory import build_review_status


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db.create_family("重评估测试")


def _judge(family_id, conditions):
    return db.save_judgment(
        family_id,
        priorities=[{"issue_id": "DEBT_HIGH_001", "severity": "P1",
                     "title": "负债偏高", "finding": "DTI 偏高"}],
        evidence=[],
        recommendation="控制负债",
        validity_conditions=conditions,
    )


def test_no_judgment(family):
    r = build_review_status(family)
    assert r["has_judgment"] is False
    assert r["status"] is None
    assert r["stale_reasons"] == []


def test_stale_after_data_change(family):
    _judge(family, {"cashflow_surplus": 10000})
    # 数据变化：新增收入 50000 → 月度结余从 10000 变 50000
    db.apply_action(family, {"kind": "income",
                             "fields": {"category": "工资", "amount": 50000, "period": "月"}})
    r = build_review_status(family)
    assert r["has_judgment"] is True
    assert r["status"] == "stale"
    assert any(x["key"] == "cashflow_surplus" and x["before"] == 10000 and x["after"] == 50000
               for x in r["stale_reasons"])


def test_stale_reasons_persist(family):
    _judge(family, {"cashflow_surplus": 10000})
    db.apply_action(family, {"kind": "income",
                             "fields": {"category": "工资", "amount": 50000, "period": "月"}})
    build_review_status(family)          # 第一次：标记失效
    r = build_review_status(family)      # 第二次：失效原因应仍在
    assert r["status"] == "stale"
    assert any(x["key"] == "cashflow_surplus" and x["before"] == 10000 and x["after"] == 50000
               for x in r["stale_reasons"])


def test_no_change_stays_active(family):
    db.apply_action(family, {"kind": "income",
                             "fields": {"category": "工资", "amount": 50000, "period": "月"}})
    _judge(family, {"cashflow_surplus": 50000})
    r = build_review_status(family)
    assert r["has_judgment"] is True
    assert r["status"] == "active"
    assert r["stale_reasons"] == []
