"""「51分」MetricRef 展示修复测试：数字保留在 Engine 真值，不进 prose。

设计依据：design-advisor-context.md §6——Engine finding 内部可保留数值，
但进入用户文案的 severity/summary 层时数字不得内联，改以 MetricRef 呈现。

三条不变量：
- T-D1  `_fallback_summary` 遇到带数字的 finding → 不内联进 summary（prose 边界硬闸）
- T-D2  `detect_allocation` 的 finding 是定性描述（无数字），真值在 metric.allocation_fitness
- T-D3  全链路：真实 issue → PriorityRef → fallback summary 无数字、含 title
"""
from app.agent.response import _fallback_summary
from app.decision import build_issues
from app.schemas.agent import PriorityRef


def _fd():
    return {
        "family": {"id": 1, "name": "测试家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1976}],
        "assets": [{"type": "存款", "value": 100000}],  # 100% 现金 → 配置适配度极低
        "liabilities": [],
        "cashflows": [
            {"flow_type": "income", "amount": 30000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
        "goals": [], "insurance": [], "reminders": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }


def _allocation_issue(fd):
    """从 build_issues 命中 ALLOCATION_LOW_FITNESS 的 issue（无则报错）。"""
    result = build_issues(fd)
    for i in result["issues"]:
        if i["issue_id"] == "ALLOCATION_LOW_FITNESS_001":
            return i
    raise AssertionError("该家庭未命中 ALLOCATION_LOW_FITNESS_001（fixture 失效）")


# ---------- T-D1：prose 边界硬闸 ----------

def test_td1_fallback_summary_never_inlines_numeric_finding():
    """带数字的 finding 不得内联进 summary prose。"""
    p = PriorityRef(issue_id="ALLOCATION_LOW_FITNESS_001", severity="P1",
                    title="资产配置适配度偏低", finding="配置适配度 51 分")
    s = _fallback_summary([p])
    assert "51" not in s
    assert "当前最需要关注：资产配置适配度偏低" in s


def test_td1_qualitative_finding_still_shown():
    """定性（无数字）的 finding 仍应作为补充信息显示。"""
    p = PriorityRef(issue_id="ALLOCATION_LOW_FITNESS_001", severity="P1",
                    title="资产配置适配度偏低", finding="当前资产结构偏离目标配置")
    s = _fallback_summary([p])
    assert "当前资产结构偏离目标配置" in s


# ---------- T-D2：detect_allocation 源头去数字，真值保留 ----------

def test_td2_allocation_finding_qualitative_and_metric_keeps_truth():
    issue = _allocation_issue(_fd())
    # finding 定性：无任何数字
    assert not any(ch.isdigit() for ch in issue["finding"])
    assert "配置适配度" not in issue["finding"]
    # 真值保留在 metric.allocation_fitness（Engine 确定性数字）
    score = issue["metric"]["allocation_fitness"]
    assert isinstance(score, (int, float))
    assert score < 60  # 该 fixture 必然低于健康线 60


# ---------- T-D3：全链路 —— issue → PriorityRef → summary 无数字 ----------

def test_td3_chain_summary_clean_with_real_issue():
    issue = _allocation_issue(_fd())
    p = PriorityRef(issue_id=issue["issue_id"], severity=issue["severity"],
                    title=issue["title"], finding=issue["finding"])
    s = _fallback_summary([p])
    assert "当前最需要关注：资产配置适配度偏低" in s
    assert not any(ch.isdigit() for ch in s)
