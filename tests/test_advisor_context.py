"""V1.0 Step 2 契约测试：AdvisorContext 不变量冻结（T1–T6，先红后绿）。

依据：docs/design-advisor-context.md §5/§8（用户 2026-08-15 锁定）。
铁律：数字唯一来源是 Engine/Decision；Context 永不成为计算来源（T4 = Phase 1 硬红线）。
零 API 成本（NullProvider 确定性回退），CI 安全。

六条不变量（任意一条变红即回归，须有意为之）：
  T1  context 不得丢：goals context + 模糊消息 → intent 被 SEED 到 intent_hint。
  T1b 用户当前 query 压倒页面 intent_hint（SEED 不是 OVERRIDE）。
  T2  原 query 不得丢：弹建档卡 → 取消 → AppliedResponse.original_query 返回原问题。
  T3  已有数字不得重复追问：family_state 暴露 Engine 已确认收入，缺数检测不含它。
  T4  context 不算数（🔴 硬红线）：payload 塞 gap=999999 → 数字只来自 Engine。
  T5  确定性基线不倒退：无 context 的题路由行为与冻结基线一致（17 锚套件同跑）。
  T6  payload 白名单：各 source 禁止字段被剥离，绝不静默接受。
"""
import json

import pytest

from app import db
from app.agent.entry import converse
from app.agent.profile import apply_confirmation
from app.agent.provider import NullProvider
from app.schemas.agent import ConfirmCard
from app.schemas.context import AdvisorContextRequest, build_advisor_context, detect_missing

from advisor_eval.family import build_family


@pytest.fixture
def db_(tmp_path, monkeypatch):
    """独立临时 SQLite，绝不污染 data.db（与 client fixture 同口径）。"""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def _user(fid: int) -> dict:
    return {"family_id": fid, "tier": "vip", "id": 1}


# ---------- T1 / T1b：context 不得丢 + query 压倒 hint ----------

def test_t1_context_seeds_intent_when_message_ambiguous(db_):
    """goals 页入口 + 模糊消息 → 意图被 SEED 到 CHECK_GOALS（无 context 时是兜底 Overview）。"""
    fid = build_family()
    user = _user(fid)
    ambiguous = "帮我看下我的家庭财务情况"

    # 无 context：模糊消息无关键词 → VIEW_OVERVIEW（兜底）
    no_ctx = converse(ambiguous, user, llm=NullProvider())
    assert no_ctx.intent == "VIEW_OVERVIEW"

    # 带 goals context + intent_hint：意图进入目标页（context 被决策链消费）
    ctx = {"source": "goals", "intent_hint": "CHECK_GOALS",
           "query": ambiguous, "payload": {"goal_type": "教育"}}
    with_ctx = converse(ambiguous, user, llm=NullProvider(), context=ctx)
    assert with_ctx.intent == "CHECK_GOALS"
    # 回答聚焦 payload 指向的目标（Engine 缺口出现）
    assert 900000 in [m.value for m in with_ctx.metrics]


def test_t1b_user_query_overrides_page_hint(db_):
    """从 Goals 页点进来后用户随口问退休 → 用户问题胜出，绝不被 hint 误导到目标页。"""
    fid = build_family()
    user = _user(fid)
    ctx = {"source": "goals", "intent_hint": "CHECK_GOALS"}
    r = converse("我退休够不够？", user, llm=NullProvider(), context=ctx)
    assert r.intent == "CHECK_RETIREMENT"   # 关键词强路由压过 hint


# ---------- T2：原 query 不得丢 ----------

def test_t2_cancel_returns_original_query(db_):
    """弹建档卡 → 取消 → 原问题随 AppliedResponse 返回，不丢（G3 契约底座）。"""
    fid = db_.create_family("空家庭")
    user = _user(fid)
    msg = "我月收入 3 万，存款 50 万"

    resp = converse(msg, user, llm=NullProvider())
    assert isinstance(resp, ConfirmCard), f"期望弹建档卡，实际 {type(resp).__name__}"

    canc = apply_confirmation(fid, resp.pending_id, confirmed=False)
    assert canc.type == "discarded"
    assert canc.original_query == msg, "取消后原问题必须随响应返回，供继续回答"

    # 确认路径不受影响
    resp2 = converse(msg, user, llm=NullProvider())
    app_resp = apply_confirmation(fid, resp2.pending_id, confirmed=True)
    assert app_resp.type == "applied"


# ---------- T3：已有数字不得重复追问 ----------

def test_t3_missing_excludes_known_income(db_):
    """已建档家庭：family_state 暴露 Engine 已确认收入，缺数检测绝不重复追问它。"""
    fid = build_family()
    user = _user(fid)

    ctx = build_advisor_context("我该提前还贷还是投资？", user, None)
    assert ctx.family_state is not None
    # family_state = Engine 已确认数据（原始明细含 income 现金流）
    cashflows = ctx.family_state.get("cashflows") or []
    assert any(c.get("flow_type") == "income" for c in cashflows), \
        "family_state 必须暴露已知收入"

    missing = detect_missing(ctx, "SCENARIO_COMPARE")
    assert "月收入" not in missing and "月支出" not in missing

    # 空家庭反例：收入/支出确实缺 → 缺数检测必须报出来
    empty = db_.create_family("空")
    empty_ctx = build_advisor_context("看看我家",
                                      {"family_id": empty, "tier": "vip", "id": 1}, None)
    assert "月收入" in detect_missing(empty_ctx, "VIEW_OVERVIEW")


# ---------- T4：context 不算数（🔴 Phase 1 硬红线） ----------

def test_t4_payload_numbers_never_enter_metrics(db_):
    """payload 恶意塞 gap=999999 / monthly_need=88888 → 数字只来自 Engine，永不进入输出。"""
    fid = build_family()
    user = _user(fid)
    malicious = {"source": "goals", "intent_hint": "CHECK_GOALS",
                 "payload": {"goal_id": 1, "gap": 999999, "monthly_need": 88888}}

    r = converse("这个教育金目标怎么完成？", user, llm=NullProvider(), context=malicious)
    assert r.intent == "CHECK_GOALS"

    # Engine 真值必须出现：教育金缺口 = 100万目标 − 10万已存 = 90万
    values = [m.value for m in r.metrics]
    assert 900000 in values, f"Engine 缺口必须出现，实际 metrics={values}"

    # 恶意 payload 数字永不进入任何输出字段（metrics/finding/推荐/摘要全查）
    dumped = json.dumps(r.model_dump(), ensure_ascii=False)
    assert "999999" not in dumped and "88888" not in dumped, \
        "context 的数字永不进入 Advisor 输出（T4 硬红线）"


# ---------- T5：确定性基线不倒退 ----------

def test_t5_no_context_routing_unchanged(db_):
    """契约只在有 context 时参与路由：无 context 的题行为必须与冻结基线一致。
    完整 17 个回归锚由 tests/test_advisor_benchmark.py 在同一个 pytest 会话内跑。"""
    fid = build_family()
    user = _user(fid)
    r = converse("这个孩子教育金目标怎么完成？", user, llm=NullProvider())
    assert r.intent == "CHECK_GOALS"
    assert 900000 in [m.value for m in r.metrics]


# ---------- T6：payload 白名单 ----------

def test_t6_payload_whitelist_strips_forbidden_fields():
    """各 source 的 payload 白名单：禁止字段被剥离并丢弃，绝不静默接受。"""
    req = AdvisorContextRequest(
        source="goals",
        payload={"goal_id": 1, "goal_type": "教育",
                 "gap": 999999, "monthly_need": 88888},
    )
    assert req.payload == {"goal_id": 1, "goal_type": "教育"}

    # 空白名单来源：payload 一律清空
    assert AdvisorContextRequest(source="overview", payload={"score": 51}).payload == {}
    assert AdvisorContextRequest(source="chat", payload={"x": 1}).payload == {}
