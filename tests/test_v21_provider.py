"""V2.1 Provider 注入通道测试：complete_json 支持可选 context，向后兼容。

铁律：
- context 是「已序列化文本」（str），由调用方 context_to_text 产出；provider 不依赖 context 模块。
- context=None 时行为与现状逐字节一致（messages 仍 [system, user]）。
"""
from app.agent import FakeLLMProvider


class _FakeResp:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


# ---------- FakeLLMProvider 捕获 context ----------

def test_fake_provider_captures_context():
    fake = FakeLLMProvider(script=[{"intent": "VIEW_OVERVIEW"}])
    fake.complete_json("sys", "user", {},
                       context="【财务指标】净资产=100（source: overview.net_worth）")
    assert fake.last_context == "【财务指标】净资产=100（source: overview.net_worth）"


def test_fake_provider_context_defaults_none():
    fake = FakeLLMProvider(script=[{"intent": "VIEW_OVERVIEW"}])
    fake.complete_json("sys", "user", {})
    assert fake.last_context is None


# ---------- DeepSeek 注入 context ----------

def test_deepseek_injects_context_into_system(monkeypatch):
    import app.agent.providers.deepseek as d
    captured = {}

    def fake_post(url, **kwargs):
        captured["json"] = kwargs["json"]
        return _FakeResp('{"intent": "CHECK_ALLOCATION"}')

    monkeypatch.setattr(d.httpx, "post", fake_post)
    provider = d.DeepSeekProvider(api_key="sk", model="m")
    provider.complete_json("sys", "user", {}, context="CTX_TEXT")
    assert "CTX_TEXT" in captured["json"]["messages"][0]["content"]


def test_deepseek_context_none_keeps_two_messages(monkeypatch):
    import app.agent.providers.deepseek as d
    captured = {}

    def fake_post(url, **kwargs):
        captured["json"] = kwargs["json"]
        return _FakeResp('{"intent": "CHECK_ALLOCATION"}')

    monkeypatch.setattr(d.httpx, "post", fake_post)
    provider = d.DeepSeekProvider(api_key="sk", model="m")
    provider.complete_json("sys", "user", {})
    assert len(captured["json"]["messages"]) == 2
