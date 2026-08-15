"""V27.1 自然语言多字段抽取测试：LLM function-calling 走共享 Provider。

铁律：
- 抽取=转写用户原话（金额来自 user 的话），非计算/编造。
- LLM 抽不到（chat 返回 None / 无 tool_calls）→ 空列表，由上层规则兜底。
"""
from app.agent.provider import FakeLLMProvider
from app.extraction import extract_with_llm


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
