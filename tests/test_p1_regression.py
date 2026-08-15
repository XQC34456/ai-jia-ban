"""P1 回归测试：10 个真实问题 → 确定性意图路由（无 LLM，零 API 成本）。

来源：.verify/probe_p1_questions.py 用真实 LLM 跑 10 题，暴露 4 个路由 bug：
  1) 「收入下降 20%」被 looks_like_filing 误判建档（我的 V27.1 回归）
  2) 「失业半年能撑多久」无关键词 → LLM 误判 CHECK_ALLOCATION
  3) 「提前还车贷」关键词「提前还贷/还贷」匹配不到（「车」夹中间）→ LLM 兜底不稳定
  4) 「剩下的钱怎么投」无关键词 → LLM 兜底在 CHECK_GOALS/CHECK_ALLOCATION 间漂移

本测试用无 LLM 的确定性 route_intent 把这 10 题意图冻结，防回归。
铁律：只测「识别」，不做财富计算。
"""
from app.agent.profile import looks_like_filing
from app.agent.router import route_intent

# 10 个真实问题 → 期望意图（问题集 = 产品验收基线，逐题冻结）
P1_QUESTIONS = [
    ("我的家庭财务健康吗？", "VIEW_OVERVIEW"),             # 无关键词 → 兜底即总览
    ("我现在最大的风险是什么？", "CHECK_ISSUES"),           # 风险
    ("我的资产配置合理吗？", "CHECK_ALLOCATION"),            # 配置
    ("我该不该提前还车贷？", "SCENARIO_COMPARE"),            # 提前还
    ("我每个月剩下的钱应该怎么投？", "CHECK_ALLOCATION"),     # 怎么投
    ("如果我失业半年能撑多久？", "CHECK_ISSUES"),            # 失业/撑多久
    ("孩子教育金够不够？", "CHECK_GOALS"),                  # 教育金
    ("我退休以后够不够用？", "CHECK_RETIREMENT"),            # 退休
    ("房贷和投资哪个优先？", "SCENARIO_COMPARE"),            # 投资
    ("如果收入下降 20% 会怎么样？", "SCENARIO_COMPARE"),      # 收入下降
]


def test_p1_questions_route_deterministically():
    for q, expected in P1_QUESTIONS:
        got = route_intent(q)
        assert got == expected, f"{q!r} 应路由 {expected}，实得 {got}"


def test_p1_scenario_questions_not_treated_as_filing():
    """情景/变化问题带金额，也绝不能在建档层被拦截成建档追问。"""
    assert looks_like_filing("如果收入下降 20% 会怎么样") is False
    assert looks_like_filing("如果我失业半年能撑多久") is False
    assert looks_like_filing("我该不该提前还车贷") is False
