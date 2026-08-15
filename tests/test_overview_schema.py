"""Overview schema 回归测试：确保 build_overview 新增字段不被 response_model 剥掉。

Task 1.1 曾在 overview.py 暴露 `dimensions`，但 schemas/wealth.py 漏声明 → /overview
的 response_model=Overview 把 dimensions 剥掉 → health 雷达显示「暂无数据」。
本测试锁死「build_overview 产出的关键字段，必须能在 Overview.model_validate 后存活」。
"""
from app.schemas.wealth import Overview
from app.services import build_overview


def _data():
    return {
        "family": {},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1990}],
        "assets": [{"type": "存款", "name": "活期", "value": 300000}],
        "liabilities": [{"type": "房贷", "name": "房贷", "principal": 500000,
                         "monthly_payment": 4000, "interest_rate": 0.04,
                         "remaining_months": 240}],
        "cashflows": [{"flow_type": "income", "category": "工资", "amount": 25000, "period": "月"},
                      {"flow_type": "expense", "category": "生活", "amount": 15000, "period": "月"}],
        "goals": [], "reminders": [],
        "insurance": [{"person_id": None, "type": "重疾", "name": "重疾险",
                       "annual_premium": 5000, "coverage": 500000}],
        "family_profile": {},
    }


def test_overview_schema_keeps_dimensions():
    o = build_overview(_data())
    assert len(o["dimensions"]) == 7            # build_overview 产出 7 维健康评分
    m = Overview.model_validate(o)              # 模拟 response_model 序列化
    assert len(m.dimensions) == 7               # 关键：不被 Overview 剥掉


def test_overview_schema_dimensions_has_protection():
    """7 维健康雷达必须含 protection（区别于 detect.py 的 7 类型）。"""
    o = build_overview(_data())
    names = {d["name"] for d in o["dimensions"]}
    assert "protection" in names
    m = Overview.model_validate(o)
    assert "protection" in {d["name"] for d in m.dimensions}
