"""评测脚本 observer 无副作用契约测试。

铁律：
- run_observation 的 pre_change 记录（observer）必须「只读」，绝不标记 stale。
- 否则会抢先把判断标 stale，导致 converse 里 detect_invalidation 因 status != active
  返回空，失效原因注入拿不到具体维度（这正是 obs4 顾问感 2.0 的评测侧根因）。
"""
import pytest

from app import db
from app.agent.provider import NullProvider
from advisor_eval import run_eval


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 10000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 5000, "period": "月"}})
    return fid


def _add_income(fid):
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 15000, "period": "月"}})


def _save_active_judgment(fid):
    db.save_judgment(fid,
                     priorities=[{"issue_id": "cashflow", "severity": "P0", "title": "现金流"}],
                     evidence=[],
                     recommendation="先解决现金流",
                     validity_conditions=run_eval._snapshot_conditions(fid))


def test_diff_snapshots_detects_changed_keys():
    changed = run_eval._diff_snapshots(
        {"cashflow_surplus": 5000.0, "dti": 0.5},
        {"cashflow_surplus": 20000.0, "dti": 0.5},
    )
    assert changed == [{"key": "cashflow_surplus", "before": 5000.0, "after": 20000.0}]


def test_observer_pre_change_does_not_stale(family, monkeypatch):
    """核心回归：observer 只记录 diff，不把判断标 stale。"""
    _save_active_judgment(family)
    assert db.latest_judgment(family)["status"] == "active"

    # 隔离 converse（避免真实 detect_invalidation 标 stale），聚焦 observer 行为
    monkeypatch.setattr(run_eval, "converse", lambda *a, **k: None)

    script = {
        "capture_invalidation": True,
        "turns": [{
            "message": "有变化吗",
            "pre_change": [{"fn": _add_income, "expect_stale": True, "label": "4A 加收入"}],
        }],
    }
    turns = run_eval.run_observation(script, {"family_id": family, "tier": "free"},
                                     NullProvider())

    step = turns[0]["invalidation_steps"][0]
    assert any(c["key"] == "cashflow_surplus" for c in step["changed"])  # 记录到了变化
    assert db.latest_judgment(family)["status"] == "active"  # 但没标 stale
