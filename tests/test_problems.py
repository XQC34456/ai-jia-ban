"""build_problems 纯映射 + 问题口径统一回归测试。

核心铁律：财富判断只有一个地方（build_issues）。
build_problems 只能做 shape 转换（P0/P1/P2→5/3/2、finding→why、
recommendations[0].detail→advice），绝不新增/删减问题、不重算 severity。
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import db
from app.decision import build_issues, build_problems
from app.main import app


# ---------- 测试数据 ----------

def _fd(**overrides):
    base = {
        "family": {"id": 1, "name": "测试家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1976}],
        "assets": [{"type": "存款", "value": 100000}],
        "liabilities": [],
        "cashflows": [
            {"flow_type": "income", "amount": 30000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
        "goals": [], "insurance": [], "reminders": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }
    base.update(overrides)
    return base


def _problems(**overrides):
    return build_problems(_fd(**overrides))


def _has(problems, substr):
    return any(substr in p["title"] for p in problems)


# ---------- 纯映射不变式 ----------

def test_build_problems_is_pure_shape_adapter():
    fd = _fd(cashflows=[
        {"flow_type": "income", "amount": 10000, "period": "月"},
        {"flow_type": "expense", "amount": 20000, "period": "月"},
    ])
    issues = build_issues(fd)["issues"]
    problems = build_problems(fd)
    # 不增不减
    assert len(problems) == len(issues)
    assert [p["title"] for p in problems] == [i["title"] for i in issues]
    # shape 固定
    for p in problems:
        assert set(p) == {"severity", "title", "why", "advice"}
        assert isinstance(p["severity"], int)


def test_field_mapping():
    fd = _fd(cashflows=[
        {"flow_type": "income", "amount": 10000, "period": "月"},
        {"flow_type": "expense", "amount": 20000, "period": "月"},
    ])
    issues = {i["title"]: i for i in build_issues(fd)["issues"]}
    problems = {p["title"]: p for p in build_problems(fd)}
    assert problems, "应有至少一个问题"
    for title, p in problems.items():
        i = issues[title]
        assert p["severity"] == {"P0": 5, "P1": 3, "P2": 2}[i["severity"]]
        assert p["why"] == i["finding"]
        if i.get("recommendations"):
            assert p["advice"] == i["recommendations"][0]["detail"]


# ---------- 回归：旧 6 类不丢 ----------

def test_empty_family_no_problems():
    assert build_problems({}) == []


def test_legacy_categories_regression():
    """证明统一口径后，旧 health_check 能识别的风险类型一条都没丢。"""
    # 1 应急资金不足
    assert _has(_problems(
        assets=[{"type": "存款", "value": 10000}],
        cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                   {"flow_type": "expense", "amount": 20000, "period": "月"}]), "应急资金")

    # 2 负债压力
    assert _has(_problems(
        liabilities=[{"type": "房贷", "principal": 2000000, "monthly_payment": 20000,
                      "interest_rate": 0.035, "remaining_months": 240}]), "负债")

    # 3 现金流为负
    assert _has(_problems(
        cashflows=[{"flow_type": "income", "amount": 10000, "period": "月"},
                   {"flow_type": "expense", "amount": 20000, "period": "月"}]), "现金流")

    # 4 房产集中 → 配置适配度 / 退休流动资金不足（更细的表达）
    p = _problems(
        assets=[{"type": "房产", "value": 8000000}, {"type": "存款", "value": 100000}],
        cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                   {"flow_type": "expense", "amount": 28000, "period": "月"}])
    assert _has(p, "配置") or _has(p, "退休")

    # 5 目标缺口
    assert _has(_problems(
        goals=[{"type": "教育", "name": "教育金", "target_amount": 1000000,
                "target_date": "2036", "current_saved": 50000}]), "缺口")

    # 6 目标资金竞争（多目标超月结余）——target_date 需完整 ISO 日期才能算 monthly_needed
    far = date.today().replace(year=date.today().year + 5).isoformat()
    assert _has(_problems(
        goals=[{"type": "买房", "name": "首付", "target_amount": 2000000,
                "target_date": far, "current_saved": 0},
               {"type": "教育", "name": "教育金", "target_amount": 1500000,
                "target_date": far, "current_saved": 0}]), "现金流能力")


def test_new_categories_covered():
    """build_issues 比旧 health_check 多出的风险类型也必须被 build_problems 覆盖。"""
    # 养老：房产重、可投资资产少 → 退休流动资金不足
    p = _problems(
        assets=[{"type": "房产", "value": 8000000}, {"type": "存款", "value": 100000}],
        cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                   {"flow_type": "expense", "amount": 28000, "period": "月"}])
    assert _has(p, "退休")

    # 闲置现金：大量现金、无短期目标
    p = _problems(
        assets=[{"type": "存款", "value": 3000000}],
        cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                   {"flow_type": "expense", "amount": 10000, "period": "月"}])
    assert _has(p, "现金")


# ---------- /api/family 与 /api/report 同源 ----------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _register(c, username="alice", password="secret123"):
    r = c.post("/api/register", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _ent(c, h, table, payload):
    r = c.post(f"/api/family/entity/{table}", headers=h, json=payload)
    assert r.status_code == 200, r.text
    return r.json().get("id")


def test_family_and_report_same_problem_source(client):
    u = _register(client)
    h = {"Authorization": "Bearer " + u["token"]}
    # VIP（/api/report 需 VIP）
    assert client.post("/api/upgrade", headers=h).status_code == 200

    # 建档：触发多类问题
    _ent(client, h, "person", {"name": "本人", "relation": "本人", "birth_year": 1988})
    _ent(client, h, "cashflow", {"flow_type": "income", "category": "工资",
                                 "amount": 30000, "period": "月"})
    _ent(client, h, "cashflow", {"flow_type": "expense", "category": "日常",
                                 "amount": 28000, "period": "月"})
    _ent(client, h, "asset", {"type": "房产", "name": "自住房", "value": 3000000})
    _ent(client, h, "asset", {"type": "存款", "name": "活期", "value": 100000})

    family = client.get("/api/family", headers=h).json()
    report = client.get("/api/report", headers=h).json()

    # 同源
    assert family["problems"] == report["problems"]

    # 都等于 build_problems(dump_family)
    fid = db.get_user_by_username(u["username"])["family_id"]
    data = db.dump_family(fid)
    expected = build_problems(data)
    assert family["problems"] == expected
    assert report["problems"] == expected
