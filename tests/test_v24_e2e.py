"""V2.4 Task 6：端到端（6 类多轮场景）契约测试。

验收重点（不能只测「记住上一句话」）：
- A 连续理解：第二轮 system 注入第一轮对话。
- B 用户纠正：纠正被记录进短期记忆。
- C 新信息重判：收入变化 → 旧判断确定性失效（stale）。
- D 判断失效：失效由确定性代码标记，再问时注入「已失效」提示，重新评估。
- 目标变化 / 历史事实更新：fact version 递增，旧版本 superseded，不误导。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider, converse
from app.agent.memory import record_fact
from app.agent.profile import apply_confirmation, create_confirm, extract_actions


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


def _user(fid):
    return {"family_id": fid, "tier": "free"}


def _c(name, args=None):
    return {"id": "c1", "name": name, "arguments": args or {}}


def _converse(fid, message, provider, tool, summary):
    """用共享 provider 驱动一轮对话（每轮重置脚本，chat_messages 累积供注入断言）。"""
    provider._chat_script = [
        {"content": None, "tool_calls": [_c(tool)]},
        {"content": None, "tool_calls": []},
    ]
    provider._script = ['{"summary":"' + summary + '"}']
    return converse(message, _user(fid), llm=provider)


def _confirm(fid, message):
    actions = extract_actions(message)
    assert actions, f"应抽取建档动作：{message}"
    card = create_confirm(fid, actions)
    return apply_confirmation(fid, card.pending_id, confirmed=True)


def _set_income(fid, amount):
    rows = db._rows("SELECT id FROM cashflow WHERE family_id=? AND flow_type='income'",
                    (fid,))
    assert rows
    db.update_entity("cashflow", rows[0]["id"], {"amount": amount})


# ============ A. 连续理解 ============

def test_continuous_followup_injects_history(family):
    p = FakeLLMProvider()
    _converse(family, "为什么养老有问题", p, "get_retirement", "你的养老需要关注")
    _converse(family, "那55岁退休呢", p, "get_retirement", "55岁退休需重新测算")
    # 第二轮第一次 chat 的 system 注入第一轮对话
    second_system = p.chat_messages[2][0]["content"]
    assert "为什么养老有问题" in second_system
    assert "近期对话" in second_system


# ============ B. 用户纠正 ============

def test_correction_recorded(family):
    p = FakeLLMProvider()
    _converse(family, "我想买房", p, "get_wealth_overview", "买房要结合你的资产")
    _converse(family, "不是，我是给父母换房", p, "get_wealth_overview",
              "明白了，重新评估")
    user_msgs = [r["message"] for r in db.recent_conversations(family, 10)
                 if r["role"] == "user"]
    assert "我想买房" in user_msgs
    assert "不是，我是给父母换房" in user_msgs     # 纠正被记住


# ============ C. 新信息重判（家庭状态变化） ============

def test_new_income_marks_stale(family):
    p = FakeLLMProvider()
    _converse(family, "我的现金流有问题", p, "get_wealth_issues", "现金流是主要矛盾")
    assert db.latest_judgment(family)["status"] == "active"
    _set_income(family, 50000)                       # 收入 10000 → 50000
    _converse(family, "我现在最大的风险是什么", p, "get_wealth_issues",
              "重新评估后结论变了")
    statuses = {r["status"] for r in
                db._rows("SELECT * FROM advisor_judgment WHERE family_id=?", (family,))}
    assert statuses == {"stale", "active"}           # 旧判断确定性失效，新判断写入


# ============ D. 判断失效（附「已失效」提示） ============

def test_judgment_invalidation_injects_hint(family):
    p = FakeLLMProvider()
    _converse(family, "帮我看看最大风险", p, "get_wealth_issues", "现金流是主要矛盾")
    _set_income(family, 50000)                       # 收入翻倍 → 旧判断失效
    _converse(family, "再帮我看看最大风险", p, "get_wealth_issues",
              "重新评估后现金流不再是主要矛盾")
    # 第二轮 system 注入「已失效」提示（确定性标记，非 LLM 猜测）
    second_system = p.chat_messages[2][0]["content"]
    assert "已失效" in second_system


# ============ ④ 目标变化 ============

def test_goal_change_version_bumps(family):
    _confirm(family, "给孩子准备教育金，目标50万")
    _confirm(family, "给孩子准备教育金，目标30万")
    goals = [f for f in db.current_facts(family) if f["key"] == "goal:教育"]
    assert len(goals) == 1
    assert "300" in goals[0]["value"]               # 新目标覆盖旧目标
    rows = db._rows("SELECT * FROM memory_fact WHERE family_id=? ORDER BY version",
                    (family,))
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[0]["superseded_by"] == rows[1]["id"]


# ============ ⑤ 历史事实更新 ============

def test_child_age_fact_update(family):
    record_fact(family, "child_birth_year", "2018", source="chat_confirmed",
                confidence="confirmed")
    record_fact(family, "child_birth_year", "2016", source="chat_confirmed",
                confidence="confirmed")
    facts = db.current_facts(family)
    assert facts[0]["value"] == "2016"              # 只返回当前有效版本
    rows = db._rows("SELECT * FROM memory_fact WHERE family_id=? ORDER BY version",
                    (family,))
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[0]["superseded_by"] == rows[1]["id"]
