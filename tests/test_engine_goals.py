"""Wealth Engine · 现金流型目标测算测试。"""
from app.engine import goals as g


def test_plan_cashflow_goal_zero_start():
    r = g.plan_cashflow_goal(100000, 4, 0, inflation=0.0, return_rate=0.0)
    assert r["fv_target"] == 400000
    assert r["gap"] == 400000
    assert r["monthly_save"] is None          # 无积累期，无「每月定存」
    assert r["immediate_shortfall"] == 400000  # 需立即一次性备齐


def test_plan_cashflow_goal_with_years():
    r = g.plan_cashflow_goal(100000, 4, 6)
    assert r["fv_target"] > 400000          # 通胀放大
    assert r["monthly_save"] < r["fv_target"] / (6 * 12)  # 收益摊薄每月定投


def test_plan_cashflow_goal_partially_saved():
    r = g.plan_cashflow_goal(100000, 4, 6, current_saved=100000, inflation=0.0, return_rate=0.0)
    assert r["fv_target"] == 400000
    assert r["fv_saved"] == 100000
    assert r["gap"] == 300000


def test_allocation_recommendation_long_horizon_more_aggressive():
    near = g.allocation_recommendation(2)
    far = g.allocation_recommendation(10)
    assert near["conservative_pct"] > far["conservative_pct"]
    assert far["aggressive_pct"] > near["aggressive_pct"]
