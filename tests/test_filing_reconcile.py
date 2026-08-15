"""Phase 2 第一刀「档案对照（filing-archive reconciliation）」回归契约测试。

铁律（用户 2026-08-16 钉死）：
- exists：**重复建档不会产生重复实体**——已存在 → 复用，不写。
- conflict：**宁可让用户确认，也不替用户猜哪一笔该覆盖**；
  多匹配歧义 → 绝不自动覆盖（不新增、不改动，只标注）。
- 三态：new / exists / conflict；同类别异值才进入覆盖更新。
"""
from app import db
from app.agent.entry import converse
from app.agent.profile import apply_confirmation, create_confirm, reconcile_actions
from app.schemas.agent import ConfirmCard


def _income(category="工资", amount=30000, period="月"):
    return {"kind": "income",
            "fields": {"category": category, "amount": amount, "period": period},
            "summary": f"月收入 {amount:,.0f} 元"}


def _asset(type_="存款", name="存款", value=500000):
    return {"kind": "asset",
            "fields": {"type": type_, "name": name, "value": value},
            "summary": f"{name} {value:,.0f} 元"}


# ---------- R1：新增 → 正常写库 ----------

def test_R1_new_action_inserts(family_id):
    rc = reconcile_actions(family_id, [_income()])
    assert len(rc) == 1 and rc[0].status == "new"

    card = create_confirm(family_id, [_income()])
    assert len(card.items) == 1

    r = apply_confirmation(family_id, card.pending_id, True)
    assert r.type == "applied"
    cf = db.get_cashflows(family_id)
    assert len(cf) == 1 and cf[0]["amount"] == 30000


# ---------- R2：已存在 → 复用，不产生重复实体（核心契约） ----------

def test_R2_exists_no_duplicate_entity(family_id):
    db.apply_action(family_id, _income())          # 档案已有一笔工资 3 万

    rc = reconcile_actions(family_id, [_income()])  # 用户重复陈述同一条
    assert rc[0].status == "exists"

    card = create_confirm(family_id, [_income()])
    assert card.items == []                          # 已存在不进待写项
    assert "已在档案" in card.message                # message 注明复用

    apply_confirmation(family_id, card.pending_id, True)
    # 核心契约：重复建档不产生重复实体
    assert len(db.get_cashflows(family_id)) == 1


# ---------- R3：冲突单匹配 → 确认后覆盖更新（非新增） ----------

def test_R3_conflict_single_match_overwrites_in_place(family_id):
    db.apply_action(family_id, _income(amount=25000))  # 档案 2.5 万

    rc = reconcile_actions(family_id, [_income(amount=30000)])  # 用户说 3 万
    assert rc[0].status == "conflict" and rc[0].matched_id is not None

    card = create_confirm(family_id, [_income(amount=30000)])
    assert "档案现在是" in card.items[0] and "25,000" in card.items[0]  # 差异标注

    r = apply_confirmation(family_id, card.pending_id, True)
    assert r.type == "applied"
    cf = db.get_cashflows(family_id)
    assert len(cf) == 1 and cf[0]["amount"] == 30000  # 覆盖而非新增


# ---------- R4：冲突多匹配歧义 → 绝不自动覆盖（核心契约） ----------

def test_R4_conflict_ambiguity_never_guesses(family_id):
    db.apply_action(family_id, _income(amount=25000))  # 2.5 万
    db.apply_action(family_id, _income(amount=15000))  # 1.5 万

    rc = reconcile_actions(family_id, [_income(amount=30000)])  # 用户说 3 万
    assert rc[0].status == "conflict" and rc[0].matched_id is None  # 歧义：不猜

    card = create_confirm(family_id, [_income(amount=30000)])
    assert "多笔" in card.items[0]                     # 标注不自动改动

    apply_confirmation(family_id, card.pending_id, True)
    # 核心契约：宁可让用户确认，也不替用户猜哪一笔该覆盖
    cf = db.get_cashflows(family_id)
    assert len(cf) == 2                                # 不新增
    assert {c["amount"] for c in cf} == {25000, 15000}  # 不覆盖


# ---------- R5：资产按 type 判身份（name 跨抽取不稳定） ----------

def test_R5_asset_exists_by_type(family_id):
    # 档案：type=存款 name=现金；抽取：type=存款 name=存款（name 不同是常态）
    db.apply_action(family_id, {"kind": "asset",
                                "fields": {"type": "存款", "name": "现金", "value": 500000},
                                "summary": "现金 500,000 元"})

    rc = reconcile_actions(family_id, [_asset(name="存款")])
    assert rc[0].status == "exists"                    # type 身份命中，name 差异不影响
    assert len(db.get_assets(family_id)) == 1


# ---------- R6：Q10 场景端到端（converse）→ 不重复实体 ----------

def test_R6_q10_duplicate_statement_no_dup_entity(family_id):
    # 档案 = 典型家庭：收入 2.5+1.5 万、现金 50 万
    db.apply_action(family_id, _income(amount=25000))
    db.apply_action(family_id, _income(amount=15000))
    db.apply_action(family_id, {"kind": "asset",
                                "fields": {"type": "存款", "name": "现金", "value": 500000},
                                "summary": "现金 500,000 元"})

    resp = converse("我月收入3万，存款50万",
                    {"family_id": family_id, "tier": "vip", "id": 1}, llm=None)
    assert isinstance(resp, ConfirmCard)
    # 存款 50 万已在档案 → 不进待写项；收入 3 万 vs 2 笔工资 → 歧义标注
    assert len(resp.items) == 1
    assert "存款" not in resp.items[0]
    assert "多笔" in resp.items[0]
    assert "已在档案" in resp.message

    apply_confirmation(family_id, resp.pending_id, True)
    incomes = [c for c in db.get_cashflows(family_id) if c["flow_type"] == "income"]
    assert len(incomes) == 2                            # 不产生第三笔收入


# ---------- R7：全已存在 → 卡不写任何东西 ----------

def test_R7_all_exists_writes_nothing(family_id):
    db.apply_action(family_id, _asset())                # 档案已有存款 50 万

    resp = create_confirm(family_id, [_asset()])
    assert resp.items == []
    assert "已在档案" in resp.message

    r = apply_confirmation(family_id, resp.pending_id, True)
    assert r.type == "applied"
    assert len(db.get_assets(family_id)) == 1
