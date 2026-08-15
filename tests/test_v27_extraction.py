"""V27.1 自然语言多字段抽取测试：LLM function-calling 走共享 Provider。

铁律：
- 抽取=转写用户原话（金额来自 user 的话），非计算/编造。
- LLM 抽不到（chat 返回 None / 无 tool_calls）→ 空列表，由上层规则兜底。
"""
from app.agent.entry import converse
from app.agent.provider import FakeLLMProvider, NullProvider
from app.agent.profile import create_confirm, extract_actions, looks_like_filing
from app.extraction import extract_with_llm, validate_actions
from app.schemas.agent import AgentResponse


def test_extract_with_llm_multi_field():
    llm = FakeLLMProvider(chat_script=[{
        "content": None,
        "tool_calls": [{
            "id": "c1", "name": "record_family_info",
            "arguments": {"actions": [
                {"kind": "income", "fields": {"category": "工资", "amount": 38000,
                                              "period": "月", "person_name": "本人"}},
                {"kind": "expense", "fields": {"category": "房租", "amount": 5000, "period": "月"}},
                {"kind": "liability", "fields": {"type": "房贷", "monthly_payment": 3000}},
            ]},
        }],
    }])
    actions = extract_with_llm("月收入3.8万，房贷3000，房租5000", llm)
    kinds = [a["kind"] for a in actions]
    assert kinds == ["income", "expense", "liability"]
    assert actions[0]["fields"]["amount"] == 38000
    # summary 带 category/period（Task 1 同步修 _summarize）
    assert actions[0]["summary"] == "本人月收入 38,000 元"
    assert actions[1]["summary"] == "房租 5,000 元/月"
    assert actions[2]["summary"] == "房贷月供 3,000 元"


def test_extract_with_llm_no_toolcall_returns_empty():
    llm = FakeLLMProvider(chat_script=[{"content": "好的", "tool_calls": []}])
    assert extract_with_llm("我的资产配置合理吗", llm) == []


def test_extract_with_llm_chat_none_returns_empty():
    llm = FakeLLMProvider(chat_script=[])  # 脚本耗尽 → chat 返回 None
    assert extract_with_llm("随便说一句", llm) == []


# ---------- Task 2: validate_actions 确定性校验 ----------

def test_validate_actions_drops_negative_amount():
    actions = [{"kind": "income", "fields": {"category": "工资", "amount": -500, "period": "月"}}]
    assert validate_actions(actions) == []


def test_validate_actions_drops_non_numeric():
    actions = [{"kind": "expense", "fields": {"category": "房租", "amount": "很多", "period": "月"}}]
    assert validate_actions(actions) == []


def test_validate_actions_dedups_batch():
    a = {"kind": "expense", "fields": {"category": "房租", "amount": 5000, "period": "月"}}
    assert validate_actions([a, dict(a)]) == [a]


# ---------- Task 2: LLM 主 + 规则兜底 ----------

def test_extract_actions_llm_primary():
    llm = FakeLLMProvider(chat_script=[{
        "content": None,
        "tool_calls": [{"id": "c1", "name": "record_family_info",
                        "arguments": {"actions": [
                            {"kind": "income", "fields": {"category": "工资", "amount": 38000,
                                                          "period": "月", "person_name": "本人"}},
                        ]}}],
    }])
    actions = extract_actions("我月收入3.8万", llm)
    assert len(actions) == 1
    assert actions[0]["fields"]["amount"] == 38000


def test_extract_actions_rule_fallback_when_llm_empty():
    llm = FakeLLMProvider(chat_script=[{"content": None, "tool_calls": []}])  # LLM 抽不到
    actions = extract_actions("我月薪2万", llm)
    assert any(a["kind"] == "income" and a["fields"]["amount"] == 20000 for a in actions)


# ---------- Task 2: 第三层「明确追问」判定 ----------

def test_looks_like_filing_true_for_statement():
    assert looks_like_filing("我收入还行，房贷不太多") is True


def test_looks_like_filing_true_when_amount_present():
    assert looks_like_filing("我有房贷3000，想优化资产配置") is True


def test_looks_like_filing_false_for_question():
    assert looks_like_filing("我的资产配置合理吗") is False


def test_converse_filing_miss_asks_clarification(family_id):
    r = converse("我收入还行，房贷不太多",
                 {"family_id": family_id, "tier": "free", "id": 1}, llm=NullProvider())
    assert isinstance(r, AgentResponse)
    assert r.status == "need_clarification"


# ---------- Task 3: 批量确认卡后端 groups 分组 ----------

def test_confirm_card_groups_by_kind():
    actions = [
        {"kind": "income", "fields": {"category": "工资", "amount": 38000, "period": "月"},
         "summary": "本人月收入 38,000 元"},
        {"kind": "expense", "fields": {"category": "房租", "amount": 5000, "period": "月"},
         "summary": "房租 5,000 元/月"},
        {"kind": "expense", "fields": {"category": "生活", "amount": 5000, "period": "月"},
         "summary": "生活 5,000 元/月"},
    ]
    card = create_confirm(1, actions)
    labels = [g["label"] for g in card.groups]
    assert labels == ["收入", "支出"]
    assert card.groups[1]["items"] == ["房租 5,000 元/月", "生活 5,000 元/月"]
    assert card.groups[1]["icon"] == "🔵"
    assert len(card.items) == 3  # items 保留（只扩不减）


def test_confirm_card_group_fallback_kind():
    actions = [{"kind": "insurance", "fields": {}, "summary": "意外险"}]
    card = create_confirm(1, actions)
    assert card.groups[0]["label"] == "其他"
    assert card.groups[0]["items"] == ["意外险"]
