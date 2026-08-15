"""对话建档去重测试：同一资产/现金流不重复插入（只拦 AI 建档，不拦手动录入）。"""
import pytest

from app import db


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db.create_family("去重测试")


def test_asset_dedup(family):
    action = {"kind": "asset", "fields": {"type": "存款", "name": "银行活期", "value": 100000}}
    db.apply_action(family, action)
    db.apply_action(family, action)  # 重复
    assert len(db.get_assets(family)) == 1


def test_income_dedup(family):
    action = {"kind": "income", "fields": {"category": "工资", "amount": 30000, "period": "月"}}
    db.apply_action(family, action)
    db.apply_action(family, action)
    assert len(db.get_cashflows(family)) == 1


def test_expense_dedup(family):
    action = {"kind": "expense", "fields": {"category": "日常", "amount": 20000, "period": "月"}}
    db.apply_action(family, action)
    db.apply_action(family, action)
    assert len(db.get_cashflows(family)) == 1


def test_different_value_not_deduped(family):
    db.apply_action(family, {"kind": "asset", "fields": {"type": "存款", "name": "银行活期", "value": 100000}})
    db.apply_action(family, {"kind": "asset", "fields": {"type": "存款", "name": "银行活期", "value": 200000}})
    assert len(db.get_assets(family)) == 2
