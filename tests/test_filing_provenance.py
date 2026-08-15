"""Phase 2 第三刀「来源追踪（filing_provenance 事件日志）」回归契约测试。

铁律（用户 2026-08-16 钉死）：
- 来源只做「这条事实从哪里来、为什么变成现在这样」的可查询事件，
  不演化成 provenance/audit 系统；不碰档案表，不注入 LLM。
- 四种状态都记录：new / exists / conflict_overwrite / conflict_ambiguous。
- conflict_overwrite 保留 matched_id + prev_value（哪条被改、改前是什么）。
- **未确认不写事件**（用户看到建议 ≠ 用户完成了档案变更）。
"""
from app import db
from app.agent.profile import apply_confirmation, create_confirm


def _income(category="工资", amount=30000, period="月"):
    return {"kind": "income",
            "fields": {"category": category, "amount": amount, "period": period},
            "summary": f"月收入 {amount:,.0f} 元"}


def _provenance(family_id):
    return db.get_product_events(family_id, "filing_provenance")


# ---------- P1：new → 记来源事件 ----------

def test_P1_new_records_provenance(family_id):
    card = create_confirm(family_id, [_income()])
    r = apply_confirmation(family_id, card.pending_id, True)
    assert r.type == "applied"

    evs = _provenance(family_id)
    assert len(evs) == 1
    assert evs[0]["event_type"] == "filing_provenance"
    m = evs[0]["meta"]
    assert m["status"] == "new"
    assert m["kind"] == "income"
    assert "30,000" in m["summary"]


# ---------- P2：exists → 复用也记来源事件 ----------

def test_P2_exists_records_provenance(family_id):
    db.apply_action(family_id, _income())            # 档案已有收入 3 万

    card = create_confirm(family_id, [_income()])    # 用户重复陈述
    apply_confirmation(family_id, card.pending_id, True)

    evs = _provenance(family_id)
    assert len(evs) == 1
    assert evs[0]["meta"]["status"] == "exists"


# ---------- P3：conflict_overwrite → 记 matched_id + prev_value ----------

def test_P3_conflict_overwrite_records_provenance(family_id):
    db.apply_action(family_id, _income(amount=25000))   # 档案 2.5 万

    card = create_confirm(family_id, [_income(amount=30000)])  # 用户说 3 万
    apply_confirmation(family_id, card.pending_id, True)

    evs = _provenance(family_id)
    assert len(evs) == 1
    m = evs[0]["meta"]
    assert m["status"] == "conflict_overwrite"
    assert m["kind"] == "income"
    # matched_id 指向被覆盖的档案行
    cf = db.get_cashflows(family_id)
    assert len(cf) == 1
    assert m["matched_id"] == cf[0]["id"]
    # prev_value = 改前的人类可读值
    assert "25,000" in m["prev_value"]


# ---------- P4：conflict_ambiguous → 记歧义，无 matched_id ----------

def test_P4_conflict_ambiguous_records_provenance(family_id):
    db.apply_action(family_id, _income(amount=25000))
    db.apply_action(family_id, _income(amount=15000))

    card = create_confirm(family_id, [_income(amount=30000)])
    apply_confirmation(family_id, card.pending_id, True)

    evs = _provenance(family_id)
    assert len(evs) == 1
    m = evs[0]["meta"]
    assert m["status"] == "conflict_ambiguous"
    assert "matched_id" not in m          # 歧义：不定位、不猜


# ---------- P5：未确认不记事件（核心契约） ----------

def test_P5_unconfirmed_records_nothing(family_id):
    card = create_confirm(family_id, [_income()])

    # 取消确认 → 不写任何来源事件（用户看到建议 ≠ 完成了档案变更）
    r = apply_confirmation(family_id, card.pending_id, False)
    assert r.type == "discarded"
    assert _provenance(family_id) == []


# ---------- P6：get_product_events 过滤 + meta 解析 ----------

def test_P6_get_product_events_filters_and_parses(family_id):
    db.record_event(family_id, "entry")             # 干扰事件
    card = create_confirm(family_id, [_income()])
    apply_confirmation(family_id, card.pending_id, True)

    all_evs = db.get_product_events(family_id)
    assert len(all_evs) == 2                         # entry + filing_provenance

    filt = db.get_product_events(family_id, "filing_provenance")
    assert len(filt) == 1
    assert all(e["event_type"] == "filing_provenance" for e in filt)
    # meta 已解析为 dict（json.loads），不是字符串
    assert isinstance(filt[0]["meta"], dict)
