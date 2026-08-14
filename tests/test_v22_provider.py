"""V2.2 Provider Tool Calling 测试：chat(messages, tools) → {content, tool_calls}。

铁律：
- chat 是真实 function calling 通道（tools 参数 + tool_calls 解析），非 prompt 塞工具说明。
- 失败/超时/非法 arguments → 返回 None 或空 arguments（上层降级）。
- chat 与 complete_json 互不影响（complete_json 仍用 response_format=json_object 单轮）。
"""
from app.agent import FakeLLMProvider


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _toolcall(id_: str, name: str, args: str) -> dict:
    return {"id": id_, "type": "function",
            "function": {"name": name, "arguments": args}}


# ---------- FakeLLMProvider.chat 脚本 ----------

def test_fake_chat_script_returns_in_order():
    fake = FakeLLMProvider(chat_script=[
        {"content": None,
         "tool_calls": [{"id": "c1", "name": "get_wealth_issues", "arguments": {}}]},
        {"content": '{"summary": "ok"}', "tool_calls": []},
    ])
    first = fake.chat([{"role": "user", "content": "hi"}], tools=[])
    assert first["tool_calls"][0]["name"] == "get_wealth_issues"
    second = fake.chat([{"role": "user", "content": "hi"}], tools=[])
    assert second["content"] == '{"summary": "ok"}'


def test_fake_chat_script_exhausted_returns_none():
    fake = FakeLLMProvider(chat_script=[])
    assert fake.chat([{"role": "user", "content": "hi"}]) is None


def test_fake_chat_records_messages():
    fake = FakeLLMProvider(chat_script=[{"content": "{}", "tool_calls": []}])
    fake.chat([{"role": "user", "content": "hi"}])
    assert fake.chat_messages[0][0]["content"] == "hi"


# ---------- DeepSeek.chat：tools payload + tool_calls 解析 ----------

def test_chat_with_tools_sends_tools_and_tool_choice(monkeypatch):
    import app.agent.providers.deepseek as d
    captured = {}

    def fake_post(url, **kwargs):
        captured["json"] = kwargs["json"]
        return _FakeResp({"choices": [{"message": {"content": None, "tool_calls": []}}]})

    monkeypatch.setattr(d.httpx, "post", fake_post)
    p = d.DeepSeekProvider(api_key="sk", model="m")
    tools = [{"type": "function",
              "function": {"name": "get_wealth_issues", "parameters": {"type": "object"}}}]
    p.chat([{"role": "user", "content": "hi"}], tools=tools)
    assert captured["json"]["tools"] == tools
    assert captured["json"]["tool_choice"] == "auto"


def test_chat_parses_tool_calls(monkeypatch):
    import app.agent.providers.deepseek as d

    def fake_post(url, **kwargs):
        return _FakeResp({"choices": [{"message": {
            "content": None,
            "tool_calls": [_toolcall("c1", "get_wealth_issues", '{"a": 1}')],
        }}]})

    monkeypatch.setattr(d.httpx, "post", fake_post)
    p = d.DeepSeekProvider(api_key="sk", model="m")
    out = p.chat([{"role": "user", "content": "hi"}], tools=[])
    assert out["tool_calls"][0] == {"id": "c1", "name": "get_wealth_issues",
                                    "arguments": {"a": 1}}
    assert out["content"] is None


def test_chat_no_tools_returns_content(monkeypatch):
    import app.agent.providers.deepseek as d

    def fake_post(url, **kwargs):
        assert "tools" not in kwargs["json"]
        return _FakeResp({"choices": [{"message": {"content": '{"summary": "x"}',
                                                   "tool_calls": []}}]})

    monkeypatch.setattr(d.httpx, "post", fake_post)
    p = d.DeepSeekProvider(api_key="sk", model="m")
    out = p.chat([{"role": "user", "content": "hi"}])
    assert out["content"] == '{"summary": "x"}'


def test_chat_bad_arguments_json_tolerated(monkeypatch):
    import app.agent.providers.deepseek as d

    def fake_post(url, **kwargs):
        return _FakeResp({"choices": [{"message": {
            "content": None,
            "tool_calls": [_toolcall("c1", "get_wealth_issues", "not-json")],
        }}]})

    monkeypatch.setattr(d.httpx, "post", fake_post)
    p = d.DeepSeekProvider(api_key="sk", model="m")
    out = p.chat([{"role": "user", "content": "hi"}], tools=[])
    assert out["tool_calls"][0]["arguments"] == {}


def test_chat_error_returns_none(monkeypatch):
    import app.agent.providers.deepseek as d

    def fake_post(url, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(d.httpx, "post", fake_post)
    p = d.DeepSeekProvider(api_key="sk", model="m")
    assert p.chat([{"role": "user", "content": "hi"}]) is None
