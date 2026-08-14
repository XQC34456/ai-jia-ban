"""V2.3 顾问感场景端到端（30 条：20 正例 + 10 反例）。

验收标准（顾问感第一，工程正确第二）：
- 每条断言「意图正确 + 主要矛盾正确 + 数字正确 + source 正确 + 无编造 + 有顾问行为」。
- FakeLLM 模拟 LLM 的正确行为（选工具 + 结构化 JSON），验证整条链路（handle→advisor→tool_loop→assemble）正确组装。

family 用「现金流为负」（income 10000 < expense 20000）确定性触发 P0 issue，保证 priorities 可断言。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.runtime import handle


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
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _user(fid, tier="free"):
    return {"family_id": fid, "tier": tier}


def _c(name, args=None):
    return {"id": "c1", "name": name, "arguments": args or {}}


def _no_digits(s):
    return not any(ch.isdigit() for ch in (s or ""))


# ============ 正例 20 条 ============

def test_s01_buy_vs_invest_tradeoffs(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview")]},
        {"content": '{"summary":"单看这笔钱我无法直接给答案，你更需要先解决现金流",'
                    '"tradeoffs":[{"option":"现在买房","gain":"住房确定性","loss":"流动性下降"},'
                    '{"option":"先投资","gain":"流动性+复利","loss":"无住房确定性"}]}',
         "tool_calls": []},
    ])
    resp = handle("我有300万现金，买房还是投资", _user(family), llm=fake)
    assert resp.status == "ok"
    assert len(resp.tradeoffs) == 2


def test_s02_retirement_shortfall(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_retirement")]},
        {"content": '{"summary":"你的养老准备需要结合退休缺口来看"}', "tool_calls": []},
    ])
    resp = handle("我退休还差多少钱", _user(family), llm=fake)
    assert resp.status == "ok"
    assert _no_digits(resp.summary)


def test_s03_biggest_risk_priorities(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_issues")]},
        {"content": '{"summary":"你当前最大的风险是现金流为负"}', "tool_calls": []},
    ])
    resp = handle("帮我看看最大的风险", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.priorities and resp.priorities[0].severity == "P0"


def test_s04_cashflow_pressure(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_cashflow")]},
        {"content": '{"summary":"我先帮你看一下现金流，你的支出已经超过收入",'
                    '"evidence":[{"claim":"月度结余为负","metric_key":"cashflow_surplus"}]}',
         "tool_calls": []},
    ])
    resp = handle("最近钱越来越不够用", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.evidence and resp.evidence[0].metric.value == -10000
    assert resp.evidence[0].metric.source == "overview.cashflow.surplus"


def test_s05_prepay_tradeoffs(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_issues")]},
        {"content": '{"summary":"提前还贷要看你更看重现金流还是降杠杆",'
                    '"tradeoffs":[{"option":"提前还贷","gain":"降低月供","loss":"现金流压力"}]}',
         "tool_calls": []},
    ])
    resp = handle("我该不该提前还贷", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.tradeoffs


def test_s06_explain_retirement_problem(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_issues")]},
        {"content": '{"summary":"你的养老压力其实和现金流问题是连在一起的"}', "tool_calls": []},
    ])
    resp = handle("为什么我的养老有问题", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s07_education_goal(family):
    db.apply_action(family, {"kind": "goal",
                             "fields": {"type": "教育", "name": "教育金", "target_amount": 500000,
                                        "current_saved": 0}})
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_goals")]},
        {"content": '{"summary":"你的教育金目标还有缺口"}', "tool_calls": []},
    ])
    resp = handle("孩子教育金够吗", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s08_allocation(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_allocation")]},
        {"content": '{"summary":"你的资产配置需要看看集中度"}', "tool_calls": []},
    ])
    resp = handle("我的资产配置合理吗", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s09_income_change_scenario(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("run_scenario",
                                            {"name": "income_change", "params": {"pct_change": -0.3}})]},
        {"content": '{"summary":"收入下降会明显压缩你的应急空间"}', "tool_calls": []},
    ])
    resp = handle("收入下降30%会怎样", _user(family, "vip"), llm=fake)
    assert resp.status == "ok"
    assert any(m.source.startswith("comparison.") for m in resp.metrics)


def test_s10_house_missing_info(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview")]},
        {"content": '{"summary":"我现在还不能判断压力大不大", "missing":["房价","贷款规模"]}',
         "tool_calls": []},
    ])
    resp = handle("我现在适合买房吗", _user(family), llm=fake)
    assert resp.status == "need_clarification"
    assert "房价" in resp.summary


def test_s11_pure_calc_refused(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"refuse": true, "summary": "这是独立的金融计算，我不能自行测算"}',
         "tool_calls": []},
    ])
    resp = handle("帮我算100万复利10年", _user(family), llm=fake)
    assert resp.status == "refused"


def test_s12_knowledge_no_tools(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"summary":"复利是本金产生的利息也计入下一期本金再计息"}', "tool_calls": []},
    ])
    resp = handle("什么是复利", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.metrics == []


def test_s13_chitchat_no_tools(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"summary":"我主要专注家庭财富，也可以聊聊理财相关话题"}', "tool_calls": []},
    ])
    resp = handle("今天天气怎么样", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.metrics == []


def test_s14_multiple_issues_priority(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_issues")]},
        {"content": '{"summary":"你同时有养老和现金流问题，但最该先解决现金流"}', "tool_calls": []},
    ])
    resp = handle("我同时有养老和现金流问题", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.priorities


def test_s15_dont_want_save_alternatives(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_cashflow")]},
        {"content": '{"summary":"如果不想多存，也可以先优化支出结构",'
                    '"uncertainty":{"confidence":"medium","alternatives":["先砍非必要支出"]}}',
         "tool_calls": []},
    ])
    resp = handle("如果我不想多存钱呢", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.uncertainty and resp.uncertainty.alternatives


def test_s16_retirement_action(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_retirement")]},
        {"content": '{"summary":"45岁开始规划还不晚","next_actions":["先看你的养老测算详情"]}',
         "tool_calls": []},
    ])
    resp = handle("我45岁还没开始养老", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.next_actions


def test_s17_compare_two_house_options(family):
    db.apply_action(family, {"kind": "asset",
                             "fields": {"type": "存款", "name": "现金", "value": 2000000}})
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("compare_scenarios", {"name": "buy_house", "options": [
            {"params": {"price": 5000000}},
            {"params": {"price": 4000000}}]})]},
        {"content": '{"summary":"500万的压力明显更大"}', "tool_calls": []},
    ])
    resp = handle("买500万还是400万", _user(family, "vip"), llm=fake)
    assert resp.status == "ok"
    assert any(m.source.startswith("comparison.") for m in resp.metrics)


def test_s18_debt_pressure_dti(family):
    db.apply_action(family, {"kind": "liability",
                             "fields": {"type": "房贷", "name": "房贷", "principal": 1000000,
                                        "monthly_payment": 5000, "interest_rate": 5,
                                        "remaining_months": 240}})
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview")]},
        {"content": '{"summary":"你的月供占收入比例偏高","evidence":[{"claim":"负债率偏高","metric_key":"dti"}]}',
         "tool_calls": []},
    ])
    resp = handle("我房贷压力大", _user(family), llm=fake)
    assert resp.status == "ok"
    assert any(e.metric.key == "dti" and e.metric.source for e in resp.evidence)


def test_s19_legacy_goal(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_goals")]},
        {"content": '{"summary":"给孩子留钱可以从一个明确的目标开始"}', "tool_calls": []},
    ])
    resp = handle("想给孩子留点钱", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s20_full_checkup(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview"), _c("get_wealth_issues"),
                                         _c("get_allocation")]},
        {"content": '{"summary":"我帮你整体看了一遍，最该先解决现金流"}', "tool_calls": []},
    ])
    resp = handle("给我家做个全面体检", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.priorities


# ============ 反例 10 条 ============

def test_s21_challenge_reexamine(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_issues")]},
        {"content": '{"summary":"我重新核对了你的家庭数据，之前的判断需要修正"}', "tool_calls": []},
    ])
    resp = handle("你说的不对", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s22_goal_shift(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_goals")]},
        {"content": '{"summary":"明白了，你真正担心的是孩子教育，我们来看教育金"}', "tool_calls": []},
    ])
    resp = handle("其实我不是想买房，我是担心孩子教育", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s23_new_fact_reevaluate(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview")]},
        {"content": '{"summary":"多一套房会改变你的资产结构，我需要重新评估"}', "tool_calls": []},
    ])
    resp = handle("我刚刚忘了说，我还有一套房", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s24_absolute_answer_tradeoffs(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview")]},
        {"content": '{"summary":"这不是简单的二选一",'
                    '"tradeoffs":[{"option":"买","gain":"住房确定性","loss":"流动性"},'
                    '{"option":"不买","gain":"保留流动性","loss":"无住房确定性"}]}',
         "tool_calls": []},
    ])
    resp = handle("你就告诉我买不买", _user(family), llm=fake)
    assert resp.status == "ok"
    assert len(resp.tradeoffs) >= 2


def test_s25_emotion_empathy(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_cashflow")]},
        {"content": '{"summary":"先别急着否定自己，我帮你看看现金流问题出在哪"}', "tool_calls": []},
    ])
    resp = handle("我感觉自己这辈子都攒不下钱", _user(family), llm=fake)
    assert resp.status == "ok"


def test_s26_loss_no_market_blame(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_allocation")]},
        {"content": '{"summary":"我不臆测市场涨跌，但可以看你的配置是否合理"}', "tool_calls": []},
    ])
    resp = handle("我的投资为什么亏了", _user(family), llm=fake)
    assert resp.status == "ok"
    assert _no_digits(resp.summary)


def test_s27_no_guarantee(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"refuse": true, "summary": "不存在稳赚不赔的投资，我不能承诺收益"}',
         "tool_calls": []},
    ])
    resp = handle("有没有稳赚不赔的", _user(family), llm=fake)
    assert resp.status == "refused"


def test_s28_no_50pct_fabrication(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"summary":"一个月赚50%这样的目标风险极高，我不能按这个预期规划"}',
         "tool_calls": []},
    ])
    resp = handle("我要一个月赚50%", _user(family), llm=fake)
    assert resp.status == "ok"
    assert _no_digits(resp.summary)  # 数字被防编造闸清掉，不落入 summary


def test_s29_are_you_sure_evidence(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_cashflow")]},
        {"content": '{"summary":"我说明一下判断依据",'
                    '"evidence":[{"claim":"月度结余为负","metric_key":"cashflow_surplus"}]}',
         "tool_calls": []},
    ])
    resp = handle("你确定吗", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.evidence


def test_s30_guarantee_uncertainty(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_overview")]},
        {"content": '{"summary":"我不能保证未来结果","uncertainty":{"confidence":"medium"}}',
         "tool_calls": []},
    ])
    resp = handle("那你能保证吗", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.uncertainty and resp.uncertainty.confidence != "high"
