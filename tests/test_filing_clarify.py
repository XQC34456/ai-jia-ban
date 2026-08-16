"""Phase 2 第四刀「缺数检测（字段级精准追问）」测试。

铁律：
- `_filing_clarify` 是纯函数：只负责字段级追问文案，不碰 extraction / 计算 / 写库。
- 无命中 → 回退原笼统 `_FILING_CLARIFY_SUMMARY`，不硬猜未知类别。
- 端到端：建档路径抽空但像建档 → need_clarification 且追问到「缺的那个字段」。
"""
from app.agent.entry import _FILING_CLARIFY_SUMMARY, _filing_clarify, converse
from app.agent.provider import NullProvider
from app.schemas.agent import AgentResponse


# ---------- D1–D7：纯函数规则表 ----------

def test_clarify_asset():
    assert "多少钱" in _filing_clarify("我有笔存款")


def test_clarify_liability():
    assert "月供" in _filing_clarify("我有房贷")


def test_clarify_income():
    assert "月收入" in _filing_clarify("我月收入")


def test_clarify_expense():
    assert "支出" in _filing_clarify("我每月开销")


def test_clarify_fund():
    assert "投了多少钱" in _filing_clarify("我有基金")


def test_clarify_goal():
    assert "目标金额" in _filing_clarify("我想给孩子准备教育金")


def test_clarify_fallback_unknown():
    # 保险：looks_like_filing 识别但规则表不覆盖 → 回退笼统，绝不硬猜
    assert _filing_clarify("我有保险") == _FILING_CLARIFY_SUMMARY


# ---------- D8：端到端接线 ----------

def test_converse_miss_asks_precise_clarification(family_id):
    r = converse("我有笔存款",
                 {"family_id": family_id, "tier": "free", "id": 1}, llm=NullProvider())
    assert isinstance(r, AgentResponse)
    assert r.status == "need_clarification"
    assert "多少钱" in (r.summary or "")
