"""Wealth Engine · 长期财富投影测试。"""
from app.engine import projection as pr


def test_future_value():
    assert abs(pr.future_value(100000, 0.03, 1) - 103000) < 1e-6
    assert abs(pr.future_value(100000, 0.05, 2) - 110250) < 1e-6


def test_project_net_worth_zero_surplus():
    seq = pr.project_net_worth(500000, 0, 0.0, 3)
    assert seq == [500000, 500000, 500000, 500000]


def test_project_net_worth_grows():
    seq = pr.project_net_worth(0, 12000, 0.0, 2)
    assert seq[1] == 144000
    assert seq[2] == 288000


def test_project_net_worth_with_return():
    # 100万，月结余 1万，年化 6%，1 年后 = 100万*1.06 + 12万 = 118万
    seq = pr.project_net_worth(1000000, 10000, 0.06, 1)
    assert seq[1] == 1180000.0
