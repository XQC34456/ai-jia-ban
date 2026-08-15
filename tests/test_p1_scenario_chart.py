"""P1.2 情景证据图测试：SCENARIO_COMPARE 从 comparison 生成 baseline vs 方案图。

铁律：数字由 compare_scenarios 确定性算，本层只搬运 baseline/option 字段，
绝不加工财富数字。本测试断言：
- _build_scenario_chart 只选 5 个关键指标（cashflow/liquidity/dti/net_worth/wealth_score）；
- attach_layers 对 SCENARIO_COMPARE + scenario_comparison 产出 scenario_compare 图块；
- 图块 data 里的数字与 comparison 原值逐字节一致（无加工）。
"""
import pytest

from app import db
from app.agent.layers import _build_scenario_chart, attach_layers
from app.schemas.agent import AgentResponse

# 与 services.scenario._diff 产出的 9 行结构一致（key/label/unit/baseline/option/delta）
_SAMPLE_COMPARISON = {
    "A": [
        {"key": "net_worth", "label": "净资产", "unit": "万", "baseline": 500.0, "option": 480.0, "delta": -20.0},
        {"key": "wealth_score", "label": "财富评分", "unit": "分", "baseline": 72.0, "option": 65.0, "delta": -7.0},
        {"key": "rfr", "label": "退休资金率", "unit": "%", "baseline": 0.8, "option": 0.75, "delta": -0.05},
        {"key": "nwc", "label": "退休净财富覆盖", "unit": "倍", "baseline": 2.1, "option": 1.9, "delta": -0.2},
        {"key": "cashflow", "label": "月现金流", "unit": "元", "baseline": 10000.0, "option": -3000.0, "delta": -13000.0},
        {"key": "liquidity", "label": "应急月数", "unit": "月", "baseline": 6.0, "option": 2.0, "delta": -4.0},
        {"key": "dti", "label": "负债率", "unit": "%", "baseline": 0.35, "option": 0.62, "delta": 0.27},
        {"key": "real_estate_pct", "label": "房产占比", "unit": "%", "baseline": 0.6, "option": 0.7, "delta": 0.1},
        {"key": "goal_completion", "label": "目标完成度", "unit": "%", "baseline": 0.8, "option": 0.7, "delta": -0.1},
    ],
}


def test_build_scenario_chart_selects_only_five_metrics():
    block = _build_scenario_chart(_SAMPLE_COMPARISON)
    assert block is not None
    assert block.chart == "scenario_compare"
    keys = [s["key"] for s in block.data["series"]]
    assert keys == ["cashflow", "liquidity", "dti", "net_worth", "wealth_score"], \
        "只取 5 个关键指标，且按 _SCENARIO_CHART_METRICS 顺序"


def test_build_scenario_chart_preserves_numbers_verbatim():
    block = _build_scenario_chart(_SAMPLE_COMPARISON)
    cashflow = next(s for s in block.data["series"] if s["key"] == "cashflow")
    assert cashflow["baseline"] == 10000.0 and cashflow["option"] == -3000.0, \
        "数字逐字节搬运，不加工"


def test_build_scenario_chart_empty_when_no_rows():
    assert _build_scenario_chart(None) is None
    assert _build_scenario_chart({"A": []}) is None
    # 所有行都不是关键指标 → 不产出图块（防前端拿到空图）
    assert _build_scenario_chart({"A": [{"key": "rfr", "label": "退休资金率",
                                         "unit": "%", "baseline": 1, "option": 1}]}) is None


@pytest.fixture
def fid(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 30000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _resp(scenario_comparison):
    return AgentResponse(
        intent="SCENARIO_COMPARE", status="ok", summary="情景对比",
        finding="现金流会转负", scenario_comparison=scenario_comparison,
    )


def test_attach_layers_emits_scenario_chart_for_scenario_intent(fid):
    resp = attach_layers(_resp(_SAMPLE_COMPARISON), fid, None)
    assert resp.layers is not None
    assert len(resp.layers.charts) == 1
    assert resp.layers.charts[0].chart == "scenario_compare"


def test_attach_layers_no_scenario_chart_without_comparison(fid):
    # 情景意图但无 comparison（advisor 未调对比工具）→ 不产出 scenario_compare 图
    resp = attach_layers(_resp(None), fid, None)
    assert resp.layers is not None
    assert all(c.chart != "scenario_compare" for c in resp.layers.charts)


def test_attach_layers_idempotent(fid):
    resp = attach_layers(_resp(_SAMPLE_COMPARISON), fid, None)
    again = attach_layers(resp, fid, None)
    assert again is resp, "已附加 layers 应幂等返回原对象"
