"""V1.0 Step 2+3+4 契约测试：AdvisorContext 不变量冻结（T1–T8b，先红后绿）。

依据：docs/design-advisor-context.md §5/§8（用户 2026-08-15 锁定）。
铁律：数字唯一来源是 Engine/Decision；Context 永不成为计算来源（T4 = Phase 1 硬红线）。
零 API 成本（FakeLLMProvider/NullProvider 确定性），CI 安全。

八条不变量（任意一条变红即回归，须有意为之）：
  T1  context 不得丢：goals context + 模糊消息 → intent 被 SEED 到 intent_hint。
  T1b 用户当前 query 压倒页面 intent_hint（SEED 不是 OVERRIDE）。
  T2  原 query 不得丢：弹建档卡 → 取消 → AppliedResponse.original_query 返回原问题。
  T3  已有数字不得重复追问：family_state 暴露 Engine 已确认收入，缺数检测不含它。
  T4  context 不算数（🔴 硬红线）：payload 塞 gap=999999 → 数字只来自 Engine。
  T5  确定性基线不倒退：无 context 的题路由行为与冻结基线一致（17 锚套件同跑）。
  T6  payload 白名单：各 source 禁止字段被剥离，绝不静默接受。
  T7  advisor_path 消费 Context（Step 3 硬红线）：同一问题，有/无 Context，
      顾问回答必须产生可解释的差异；Context 块（【当前情境】）零数字（T4 同源）。
  T8  取消建档后继续回答（Step 4 硬红线）：取消 = 拒绝本次建档 ≠ 拒绝回答——
      原问题用 original_query 重新投入回答路径，不再次弹卡、走正常 Advisor 路径。
  T8b filing_declined 语义在代码层明确：同一建档话术不再弹卡/追问（防死循环）。
"""
import json
import re

import pytest

from app import db
from app.agent.entry import cancel_and_reanswer, converse
from app.agent.profile import apply_confirmation
from app.agent.provider import FakeLLMProvider, NullProvider
from app.schemas.agent import AgentResponse, ConfirmCard
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


# ---------- T7：advisor_path 消费 Context（Step 3 硬红线） ----------

class _ContextAwareAdvisor(FakeLLMProvider):
    """按 system 提示是否含聚焦对象返回不同回答：
    确定性演示「同一问题，有/无 Context，Advisor 回答可解释地不同」。
    第一轮调 get_goals（工具循环），第二轮按是否看到聚焦对象给不同结论。
    """

    def __init__(self):
        super().__init__()
        self.focused_seen = False
        self._calls = 0

    def chat(self, messages, tools=None):
        self.chat_messages.append(list(messages))
        system = messages[0]["content"] if messages else ""
        self.focused_seen = "聚焦对象" in system
        self._calls += 1
        if self._calls == 1:
            return {"content": "我先看看家庭目标。",
                    "tool_calls": [{"id": "c1", "name": "get_goals", "arguments": {}}]}
        return {"content": ("围绕孩子教育金目标给出安排建议。" if self.focused_seen
                            else "我先看看你的家庭整体情况。")}


def test_t7_advisor_path_consumes_context_explainable_difference(db_):
    """Step 3 硬红线：同一问题，有/无 Context，Advisor 回答必须产生可解释的差异。

    - 有 Context（goals 页传 goal_id）→ 顾问 system 提示出现【当前情境】聚焦对象
      （目标名「孩子教育金」），并围绕该目标回答。
    - 无 Context → 提示无聚焦对象，回答是泛化整体判断。
    - T4 同源：Context 块（【当前情境】）绝不含任何数字，数字只由 Engine 工具注入。
    """
    fid = build_family()
    user = _user(fid)
    goals = db_.dump_family(fid).get("goals") or []
    assert goals, "build_family 必须产出目标供聚焦"
    goal_row = goals[0]
    msg = "这个教育金目标怎么完成？"
    ctx = {"source": "goals", "intent_hint": "CHECK_GOALS",
           "payload": {"goal_id": goal_row["id"], "goal_type": goal_row.get("type")}}

    # 有 Context：顾问看到聚焦对象，回答围绕该目标
    llm_with = _ContextAwareAdvisor()
    r_with = converse(msg, user, llm=llm_with, context=ctx)
    assert llm_with.focused_seen is True, "有 Context 时顾问必须看到聚焦对象（Context 进入顾问大脑）"
    assert r_with.intent == "CHECK_GOALS"
    assert "孩子教育金" in r_with.summary, f"回答必须围绕聚焦目标，实际 summary={r_with.summary!r}"

    # 无 Context：同一问题 → 泛化整体回答（可解释的差异）
    llm_wo = _ContextAwareAdvisor()
    r_wo = converse(msg, user, llm=llm_wo)
    assert llm_wo.focused_seen is False, "无 Context 时提示不应有聚焦对象"
    assert "孩子教育金" not in r_wo.summary
    assert r_wo.summary != r_with.summary, "有/无 Context 回答必须可解释地不同"

    # T4 同源：顾问 system 提示里的【当前情境】块零数字（数字只由 Engine 工具注入）
    system0 = llm_with.chat_messages[0][0]["content"]
    m = re.search(r"【当前情境】\n(.*?)(?=\n【|\Z)", system0, re.S)
    assert m, "system 提示必须含【当前情境】块"
    block = m.group(1)
    assert re.search(r"\d", block) is None, f"Context 块含数字（T4 红线）：{block!r}"
    assert "gap" not in block and "monthly_need" not in block


# ---------- T8 / T8b：取消建档后继续回答（Step 4 硬红线） ----------

def test_t8_cancel_reanswers_original_query(db_):
    """取消建档 = 拒绝本次建档 ≠ 拒绝回答（Step 4 硬红线）：
    1. 用 original_query 重新投入回答路径（不猜 canned 文案）——原问题完整保留。
    2. 不再弹建档卡（防死循环）。
    3. 走正常 Advisor 路径：status=ok，回答用户最初的问题，而非「好的，已忽略」。
    """
    fid = db_.create_family("空家庭")
    user = _user(fid)
    msg = "我月收入 3 万，存款 50 万，这 30 万怎么配置？"

    # 建档话术（带金额）→ 必须先弹确认卡（G1 gate 现状，Step 4 不改它）
    card = converse(msg, user, llm=NullProvider())
    assert isinstance(card, ConfirmCard), f"建档话术必须先弹卡，实际 {type(card).__name__}"

    # 取消 → 原问题不丢、不二次弹卡、走正常 Advisor 路径回答原问题
    resp = cancel_and_reanswer(user, card.pending_id, llm=NullProvider())
    assert isinstance(resp, AgentResponse), \
        f"取消后必须回到正常回答路径，实际 {type(resp).__name__}"
    assert resp.status == "ok", f"取消后必须真的回答（status=ok），实际 {resp.status}"
    assert resp.intent == "CHECK_ALLOCATION", \
        f"必须回答原配置问题（原问题完整保留），实际 intent={resp.intent}"
    assert resp.summary != "好的，已忽略，没有改动你的档案。", "不得降级成 discarded 文案"

    # pending 已被消费：再次取消 → error（不重复回答、不重复弹卡）
    again = apply_confirmation(fid, card.pending_id, confirmed=False)
    assert again.type == "error"


def test_t8b_filing_declined_bypasses_filing_gate(db_):
    """filing_declined 语义在代码层明确：同一建档话术不再弹卡/追问（防死循环）。"""
    fid = db_.create_family("空")
    user = _user(fid)
    msg = "我月收入 3 万，存款 50 万"
    # 正常路径先确认会弹卡
    assert isinstance(converse(msg, user, llm=NullProvider()), ConfirmCard)
    # filing_declined 明确标记「已拒绝本次建档」→ 该话术按正常提问处理，不弹卡
    r = converse(msg, user, llm=NullProvider(), context={"filing_declined": True})
    assert isinstance(r, AgentResponse), f"filing_declined 后不得再弹卡，实际 {type(r).__name__}"
    assert r.status == "ok"
