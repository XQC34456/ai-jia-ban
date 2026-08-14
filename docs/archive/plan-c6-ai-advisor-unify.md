# Phase 6C：AI 顾问统一收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/api/agent/chat` 成为唯一 AI 顾问入口——吸收 V1 对话建档能力，七意图 Agent 成为唯一 AI 主链，修复 CHECK_ISSUES/CHECK_GOALS/EXPLAIN_RESULT 空壳问题。

**Architecture:** 新增一个薄薄的入口编排层 `converse()`：先跑 V1 抽取（命中建档 → 返回确认卡片 `ConfirmCard`），否则走 A3 Runtime `handle()`（七意图）。`handle()`、七意图、MetricRef 硬闸、拒算门、VIP 门**零改动**。P1 修复落在 `response.py`：从 `build_issues`/`build_goals` 结构化结果确定性提取 finding/metrics/recommendations，绝不靠 LLM 编数字。

**Tech Stack:** FastAPI + pydantic v2 · Python 3.10 · Vue 3 CDN（无构建）· pytest + TestClient · Playwright 冒烟。

## Global Constraints（用户冻结，逐字遵守）

- 不修改 A1-A4、Wealth Engine、API Schema 的既有契约（七意图、MetricRef、`handle()`、`AGENT_INTENTS`、`SCENARIO_PARAM_MODELS` 全不动）。
- 财富计算唯一入口仍是 `build_overview`；Agent 只取数·识别·映射·引用·解释，绝不加工·再计算。
- metric value 必带 source（MetricRef 硬闸）。
- 建档走「抽取 → 确认卡片 → `/api/confirm` 落地」，落地前不写库（防 LLM 幻觉污染数据）。
- `build_issues` 是 AI 顾问唯一问题判断口径；`/api/report`、`/api/family` 暂留 `health_check`（不扩大范围）。
- 成员「月收入」是死字段，短期只从 UI 隐藏，不动 Engine / 数据库列。
- TDD：先写失败测试再实现。完成跑全量 pytest + Playwright + 真实家庭回归。

---

## Task 1: 新增确认卡片 Schema（`ConfirmCard` / `AppliedResponse`）

**Files:**
- Modify: `app/schemas/agent.py`（只增不改：在 `AgentRequest` 之后追加两个新模型）
- Test: `tests/test_agent_schemas.py`（新建）

**Interfaces:**
- Produces: `ConfirmCard`（`type`/`pending_id`/`message`/`items`），`AppliedResponse`（`type`/`message`）。
- 与 V1 确认流形状对齐，前端 `chat.js` 可复用现有 `d.type==='confirm'` 分支。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_schemas.py
from app.schemas.agent import ConfirmCard, AppliedResponse

def test_confirm_card_shape():
    c = ConfirmCard(pending_id="abc", message="确认", items=["a", "b"])
    assert c.type == "confirm"
    assert c.model_dump()["items"] == ["a", "b"]

def test_applied_response_shape():
    a = AppliedResponse(type="applied", message="已记录")
    assert a.type == "applied"
    a2 = AppliedResponse(type="discarded", message="已忽略")
    assert a2.type == "discarded"
```

- [ ] **Step 2: 跑测试确认失败**（`ImportError: cannot import name 'ConfirmCard'`）

- [ ] **Step 3: 实现**

```python
# app/schemas/agent.py 末尾追加（不改任何既有模型）
class ConfirmCard(BaseModel):
    """建档确认卡片：抽取到动作后返回，等用户在 /api/confirm 确认。"""
    type: Literal["confirm"] = "confirm"
    pending_id: str
    message: str
    items: list[str] = Field(default_factory=list)


class AppliedResponse(BaseModel):
    """建档确认落地结果。type ∈ applied / discarded / error。"""
    type: Literal["applied", "discarded", "error"]
    message: str
```

- [ ] **Step 4: 跑测试确认通过**

- [ ] **Step 5: Commit** `feat(agent): add ConfirmCard/AppliedResponse schemas`

---

## Task 2: 建档吸收 → `app/agent/profile.py`

**Files:**
- Create: `app/agent/profile.py`（从 `chat.py` 迁入 `_PENDING`、`handle_confirm`、`_build_applied_response`；`answer_question`/`_llm_answer`/`_template_answer` 不迁，删除）
- Test: `tests/test_agent_profile.py`（新建）

**Interfaces:**
- Consumes: `app.extraction.get_extractor`、`app.db.apply_action`、`app.db.dump_family`、`app.decision.build_issues`
- Produces:
  - `extract_actions(message: str) -> list[dict]`（空列表 = 非建档）
  - `create_confirm(family_id: int, actions: list[dict]) -> ConfirmCard`
  - `apply_confirmation(family_id: int, pending_id: str, confirmed: bool) -> AppliedResponse`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_profile.py
from app.agent.profile import extract_actions, create_confirm, apply_confirmation
from app import db

def test_extract_actions_hits_profile():
    a = extract_actions("我月薪2万，房贷月供8000，存款50万")
    kinds = {x["kind"] for x in a}
    assert "income" in kinds and "liability" in kinds and "asset" in kinds

def test_extract_actions_no_profile():
    assert extract_actions("我最大的财务问题是什么") == []

def test_confirm_apply_roundtrip(family_id):
    actions = extract_actions("我月薪3万")
    card = create_confirm(family_id, actions)
    assert card.pending_id and card.items
    r = apply_confirmation(family_id, card.pending_id, True)
    assert r.type == "applied"
    cf = db.get_cashflows(family_id)
    assert any(c["flow_type"] == "income" and c["amount"] == 30000 for c in cf)

def test_confirm_discard(family_id):
    card = create_confirm(family_id, extract_actions("我月薪3万"))
    r = apply_confirmation(family_id, card.pending_id, False)
    assert r.type == "discarded"
    assert db.get_cashflows(family_id) == []

def test_confirm_expired(family_id):
    r = apply_confirmation(family_id, "nope", True)
    assert r.type == "error"
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**（迁入逻辑，落地响应改用 `build_issues` 口径——但前端不消费，只保留 message）

```python
"""建档吸收层：V1 的「抽取 → 确认卡片 → 落地」能力迁入 Agent 包。
铁律：抽取到动作只进 pending，确认后才 write 库；落地不计算财富，只写数据。
"""
from __future__ import annotations

import uuid
from typing import Any

from .. import db
from ..extraction import get_extractor
from ..schemas.agent import AppliedResponse, ConfirmCard

_PENDING: dict[str, dict[str, Any]] = {}


def extract_actions(message: str) -> list[dict[str, Any]]:
    return get_extractor().extract(message)


def create_confirm(family_id: int, actions: list[dict[str, Any]]) -> ConfirmCard:
    pending_id = uuid.uuid4().hex
    _PENDING[pending_id] = {"family_id": family_id, "actions": actions}
    return ConfirmCard(
        pending_id=pending_id,
        message="我理解到以下信息，确认后我就为你建档：",
        items=[a["summary"] for a in actions],
    )


def apply_confirmation(family_id: int, pending_id: str, confirmed: bool) -> AppliedResponse:
    pending = _PENDING.pop(pending_id, None)
    if pending is None or pending["family_id"] != family_id:
        return AppliedResponse(type="error", message="该确认已失效，请重新输入。")
    if not confirmed:
        return AppliedResponse(type="discarded", message="好的，已忽略，没有改动你的档案。")
    for action in pending["actions"]:
        db.apply_action(family_id, action)
    joined = "、".join(a["summary"] for a in pending["actions"])
    return AppliedResponse(type="applied", message=f"已记录：{joined}。")
```

- [ ] **Step 4: 跑测试确认通过**

- [ ] **Step 5: Commit** `feat(agent): absorb V1 profile extraction+confirm into app/agent/profile.py`

---

## Task 3: 入口编排 → `app/agent/entry.py::converse()`

**Files:**
- Create: `app/agent/entry.py`
- Test: `tests/test_agent_entry.py`（新建）

**Interfaces:**
- Consumes: `app.agent.profile.extract_actions/create_confirm`、`app.agent.runtime.handle`
- Produces: `converse(message, user, llm=None, context=None) -> ConfirmCard | AgentResponse`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_entry.py
from app.agent.entry import converse
from app.agent.provider import NullProvider
from app.schemas.agent import AgentResponse, ConfirmCard

def _user(family_id):
    return {"family_id": family_id, "tier": "free", "id": 1}

def test_converse_routes_to_confirm(family_id):
    r = converse("我月薪3万", _user(family_id), llm=NullProvider())
    assert isinstance(r, ConfirmCard)

def test_converse_routes_to_agent(family_id):
    r = converse("我最大的财务问题是什么", _user(family_id), llm=NullProvider())
    assert isinstance(r, AgentResponse)
    assert r.intent == "CHECK_ISSUES"
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**

```python
"""AI 顾问统一入口：抽取（建档）优先，否则走七意图 Agent。A3 handle() 零改动。"""
from __future__ import annotations

from .profile import create_confirm, extract_actions
from .provider import LLMProvider
from .runtime import handle
from ..schemas.agent import AgentResponse, ConfirmCard

__all__ = ["converse"]


def converse(message: str, user: dict, llm: LLMProvider | None = None,
             context: dict | None = None) -> ConfirmCard | AgentResponse:
    actions = extract_actions(message)
    if actions:
        return create_confirm(user["family_id"], actions)
    return handle(message, user, llm=llm, context=context)
```

- [ ] **Step 4: 跑测试确认通过**

- [ ] **Step 5: Commit** `feat(agent): add converse() unified entry (profile-first, then 7-intent)`

---

## Task 4: P1 修复 → `app/agent/response.py`

**Files:**
- Modify: `app/agent/response.py`
- Test: `tests/test_agent_runtime.py`（追加）＋ `tests/test_agent_response.py`（新建）

**Interfaces:**
- Consumes: `build_issues` 的 `{issues, recommendations}`、`build_goals` 的 `list[GoalOut]`
- Produces: `build_metrics` 新增 CHECK_ISSUES/CHECK_GOALS/EXPLAIN_RESULT 分支；`build_response` 新增 `finding`/`recommendations` 填充。

**关键：问题是什么由 build_issues 决定；本层只读字段，绝不编数字。**

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_response.py
from app.agent.response import build_metrics, build_response
from app.decision import build_issues
from app.services.goals import build_goals

_FAMILY = {
    "persons": [], "assets": [{"type": "房产", "name": "房", "value": 3000000}],
    "liabilities": [{"type": "房贷", "principal": 1000000, "monthly_payment": 12000,
                     "interest_rate": 3.5, "remaining_months": 240}],
    "cashflows": [{"flow_type": "income", "amount": 20000, "period": "月"},
                  {"flow_type": "expense", "amount": 15000, "period": "月"}],
    "goals": [{"type": "教育", "name": "教育金", "target_amount": 1000000,
               "target_date": "2036", "current_saved": 100000}],
    "reminders": [], "insurance": [], "family_profile": None,
}

def test_check_issues_metrics_nonempty():
    r = build_issues(_FAMILY)
    ms = build_metrics("CHECK_ISSUES", r)
    assert ms                                  # 不再空
    for m in ms:
        assert m.value is not None and m.source.startswith("issues.")

def test_check_issues_response_has_substance():
    r = build_issues(_FAMILY)
    resp = build_response("CHECK_ISSUES", "ok", r, summary="已梳理")
    assert resp.finding                        # 非空
    assert resp.recommendations                # 非空
    assert resp.metrics                        # 非空

def test_check_goals_response_has_substance():
    r = {"goals": build_goals(_FAMILY)}
    resp = build_response("CHECK_GOALS", "ok", r, summary="已汇总")
    assert resp.finding and resp.recommendations
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**

```python
# app/agent/response.py —— build_metrics 增加分支；build_response 增加 finding/recommendations

_ISSUE_METRIC_LABELS = {
    "emergency_months": "应急资金（月）",
    "dti": "负债率 DTI",
    "savings_rate": "储蓄率",
    "monthly_surplus": "月结余",
    "monthly_income": "月收入",
    "monthly_expense": "月支出",
    "total_debt": "总负债",
    "max_interest_rate": "最高利率",
    "allocation_fitness": "配置适配度",
    "real_estate_pct": "房产占比",
    "deviation": "配置偏离",
    "rfr": "养老 RFR",
    "nwc": "养老 NWC",
    "gap": "目标缺口",
    "monthly_needed": "每月需存",
    "shortfall": "资金缺口",
}
_ISSUE_METRIC_UNITS = {"dti": "pct", "savings_rate": "pct", "max_interest_rate": "pct",
                       "real_estate_pct": "pct", "rfr": "ratio", "nwc": "ratio",
                       "emergency_months": "months"}


def _issue_metrics(result: dict) -> list[MetricRef]:
    out: list[MetricRef] = []
    for i in (result.get("issues") or []):
        iid = i.get("issue_id") or i.get("type")
        for k, v in (i.get("metric") or {}).items():
            if v is None:
                continue
            out.append(MetricRef(
                key=f"{iid}_{k}", label=_ISSUE_METRIC_LABELS.get(k, k),
                unit=_ISSUE_METRIC_UNITS.get(k, "money"), value=v,
                source=f"issues.{iid}.metric.{k}"))
    return out


def _goal_metrics(result: dict) -> list[MetricRef]:
    out: list[MetricRef] = []
    for g in (result.get("goals") or []):
        gid = g.get("goal_id") or g.get("name")
        if g.get("gap") is not None:
            out.append(MetricRef(key=f"goal_{gid}_gap", label="目标缺口", unit="money",
                                 value=g["gap"], source=f"goals.{gid}.gap"))
        if g.get("coverage") is not None:
            out.append(MetricRef(key=f"goal_{gid}_coverage", label="目标覆盖率", unit="pct",
                                 value=g["coverage"], source=f"goals.{gid}.coverage"))
    return out


def _context_metrics(result: dict) -> list[MetricRef]:
    """EXPLAIN_RESULT：context 若带 metrics 则原样重放，否则读顶层数值字段。"""
    if isinstance(result.get("metrics"), list):
        return [MetricRef(**m) if isinstance(m, dict) else m for m in result["metrics"]
                if isinstance(m, dict) and m.get("value") is not None]
    return []
```

并在 `build_metrics` 的 `return []` 之前插入：

```python
    if intent == "CHECK_ISSUES":
        return _issue_metrics(result)
    if intent == "CHECK_GOALS":
        return _goal_metrics(result)
    if intent == "EXPLAIN_RESULT":
        return _context_metrics(result)
```

`build_response` 增加确定性 finding/recommendations：

```python
def build_response(intent, status, result=None, summary="", finding=None,
                   next_actions=None, recommendations=None):
    metrics = build_metrics(intent, result)
    if finding is None and result:
        finding = _derive_finding(intent, result)
    if recommendations is None and result:
        recommendations = _derive_recommendations(intent, result)
    return AgentResponse(...)  # 其余不变


def _derive_finding(intent: str, result: dict) -> str | None:
    if intent == "CHECK_ISSUES":
        issues = result.get("issues") or []
        if not issues:
            return "暂未发现需要关注的财富问题。"
        return "；".join(f"{i['title']}：{i['finding']}" for i in issues[:3])
    if intent == "CHECK_GOALS":
        goals = result.get("goals") or []
        gapped = [g for g in goals if g.get("gap", 0) > 0]
        if not goals:
            return "尚未设置家庭目标。"
        if not gapped:
            return f"共 {len(goals)} 个目标，暂未发现资金缺口。"
        biggest = max(gapped, key=lambda g: g["gap"])
        return (f"共 {len(goals)} 个目标，其中 {len(gapped)} 个存在资金缺口，"
                f"最大缺口是「{biggest['name']}」{biggest['gap']:,.0f} 元。")
    if intent == "EXPLAIN_RESULT":
        return result.get("finding")
    return None


def _derive_recommendations(intent: str, result: dict) -> list[str]:
    if intent == "CHECK_ISSUES":
        out = []
        for r in (result.get("recommendations") or [])[:3]:
            out.append(f"{r.get('action')}：{r.get('detail')}".strip("："))
        return [s for s in out if s]
    if intent == "CHECK_GOALS":
        out = []
        for g in (result.get("goals") or []):
            if g.get("gap", 0) > 0:
                mn = g.get("monthly_needed")
                out.append(f"「{g['name']}」：已备 {g['current_saved']:,.0f} / "
                           f"{g['target_amount']:,.0f} 元，缺口 {g['gap']:,.0f} 元"
                           + (f"，每月需存 {mn:,.0f} 元" if mn else ""))
        return out[:3]
    if intent == "EXPLAIN_RESULT":
        return result.get("recommendations") or []
    return []
```

- [ ] **Step 4: 跑测试确认通过**（含既有 `test_agent_runtime.py` 全绿，`test_build_metrics_every_value_has_source` 不受影响——它只测 3 个 overview 意图）

- [ ] **Step 5: Commit** `fix(agent): populate finding/metrics/recommendations for CHECK_ISSUES/GOALS/EXPLAIN`

---

## Task 5: API 收口（`/api/agent/chat` → `converse`，`/api/confirm` → `profile`）

**Files:**
- Modify: `app/api/agent.py`（`/chat` 改调 `converse`；去掉 `response_model=AgentResponse`，改为直接返回 `.model_dump()`）
- Modify: `app/main.py`（`/api/confirm` 改调 `profile.apply_confirmation`；`/api/chat` 暂保留为 deprecated 别名指向 `converse`，**本任务不删除 `chat.py`**）
- Test: `tests/test_agent_api.py`（更新 passthrough 测试 patch 目标；新增 confirm 端到端）

**退役顺序（铁律）：先迁移 → 前端 0 引用（Task 7）→ 测试 0 依赖 → 再删实现（Task 8）。本任务只做迁移，不删 `chat.py`，确保 `/api/confirm` 迁移后仍正常。**

**Interfaces:**
- Consumes: `app.agent.entry.converse`、`app.agent.profile.apply_confirmation`
- Produces: `/api/agent/chat` → `ConfirmCard | AgentResponse`；`/api/confirm` → `AppliedResponse`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent_api.py 追加
from app.schemas.agent import ConfirmCard

def test_agent_chat_profile_confirm(client, auth_headers):
    r = client.post("/api/agent/chat", json={"message": "我月薪3万"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "confirm" and body["pending_id"] and body["items"]

def test_confirm_apply_endpoint(client, auth_headers):
    r = client.post("/api/agent/chat", json={"message": "我月薪3万"}, headers=auth_headers)
    pid = r.json()["pending_id"]
    r2 = client.post("/api/confirm", json={"pending_id": pid, "confirmed": True},
                     headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["type"] == "applied"
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**

```python
# app/api/agent.py
from ..agent import converse, get_provider
from ..schemas.agent import AgentRequest

@router.post("/chat")
def agent_chat(body: AgentRequest, user: dict = Depends(get_current_user)):
    result = converse(body.message, user, llm=get_provider(), context=body.context)
    return result.model_dump()
```

```python
# app/main.py
from .api.agent import ...  # 或 from .agent import profile
from .agent.profile import apply_confirmation

@app.post("/api/confirm")
def confirm_endpoint(body: ConfirmIn, user: dict = Depends(get_current_user)):
    return apply_confirmation(user["family_id"], body.pending_id, body.confirmed).model_dump()
```

同时更新 `test_agent_chat_passthrough_verbatim`：把 `monkeypatch.setattr("app.api.agent.handle", ...)` 改为 patch `app.api.agent.converse`（断言仍为逐字段一致）。

- [ ] **Step 4: 跑全量 pytest 确认通过**（`test_chat.py` 删除；确认无其它文件 import `app.chat`）

- [ ] **Step 5: Commit** `refactor(api): retire /api/chat, unify entry to /api/agent/chat + /api/confirm`

---

## Task 6: 成员「月收入」死字段从 UI 隐藏

**Files:**
- Modify: `static/views/data.js`（`SECTIONS` 的 `person` 项：从 `fields` 与 `columns` 各删 `monthly_income` 一条）
- Test: `tests/test_frontend_contract.py`（若其断言 person 字段清单则同步；否则用 Playwright 冒烟覆盖）

**Interfaces:**
- 不改 DB 列、不改 Engine。仅 UI 不再展示/编辑 `person.monthly_income`。

- [ ] **Step 1:** 删除 `data.js` 中 person 的 `{ key: 'monthly_income', label: '月收入（元）', type: 'number' }`（fields）与 `{ key: 'monthly_income', label: '月收入', money: true }`（columns）。
- [ ] **Step 2:** `node --check` 校验语法（拷贝 `.mjs` 临时文件）。
- [ ] **Step 3:** Playwright 走查 `/data` 成员 tab，确认表单与表格均无「月收入」。
- [ ] **Step 4: Commit** `fix(data): hide inert person.monthly_income field`

---

## Task 7: 前端接线 → `static/views/chat.js`

**Files:**
- Modify: `static/views/chat.js`
- Test: Playwright 冒烟（新建 `D:\tmp\phase6c_smoke.py`）

**Interfaces:**
- `send()` → `POST /api/agent/chat`；响应若 `type==='confirm'` 走既有确认卡片分支，否则渲染 `AgentResponse`（intent 标签 + summary + finding + metrics 带 source + recommendations + next_actions + limitations）。
- `confirm()` → `POST /api/confirm`（URL 不变，仍读 `d.message` / `d.type==='applied'`）。

- [ ] **Step 1:** `send()` 把 `api('/api/chat', ...)` 改为 `api('/api/agent/chat', ...)`；非 confirm 分支由 `{who:'bot', text:d.message}` 改为推入 `{who:'bot', agent:d}` 结构化消息。
- [ ] **Step 2:** 模板新增 `agent` 消息渲染块（在 `.chat-msg` 之后）：

```html
<div v-else-if="m.agent" class="chat-agent card">
  <div class="agent-intent">{{ m.agent.summary }}</div>
  <div v-if="m.agent.finding" class="agent-finding">{{ m.agent.finding }}</div>
  <ul v-if="m.agent.metrics && m.agent.metrics.length" class="agent-metrics">
    <li v-for="(x, i) in m.agent.metrics" :key="i">
      <b>{{ x.label }}</b> {{ fmtMetric(x) }}
      <span class="src" :title="x.source">{{ x.source }}</span>
    </li>
  </ul>
  <ul v-if="m.agent.recommendations && m.agent.recommendations.length" class="agent-recs">
    <li v-for="(r, i) in m.agent.recommendations" :key="i">{{ r }}</li>
  </ul>
</div>
```

- [ ] **Step 3:** 新增 `fmtMetric(x)`（按 `x.unit` 格式化：money→`fmtMoney`、pct→`*100`%、months→`个月`、ratio→`×`、score→分数）。`need_clarification`/`refused` 状态显示 summary + next_actions。
- [ ] **Step 4:** `style.css` 追加 `.chat-agent`/`.agent-intent`/`.agent-finding`/`.agent-metrics`/`.agent-recs` 轻量样式（复用 token）。
- [ ] **Step 5:** Playwright 冒烟：注册 → 建档「我月薪3万」→ 确认卡片 → 确认 → 「已记录」→ 问「我最大的财务问题是什么」→ 出现带 source 的指标与建议。零 console/page error。
- [ ] **Step 6: Commit** `feat(chat): wire AI advisor to /api/agent/chat with AgentResponse rendering`

---

## Task 8: 退役清理 + 全量回归

**Files:**
- Delete: `app/chat.py`、`app/main.py` 的 `/api/chat` 端点与 `ChatIn`、`tests/test_chat.py`
- Test: 全量 pytest + Playwright

**前提：Task 7 已让前端 0 引用 `/api/chat`，此时删除实现是安全的。**

- [ ] **Step 1:** 删除 `app/chat.py`；`app/main.py` 移除 `from . import chat`、`/api/chat` 端点、`ChatIn`。
- [ ] **Step 2:** 删除 `tests/test_chat.py`（其建档/确认用例已由 `test_agent_profile.py`/`test_agent_api.py` 覆盖；answer_question 用例由 CHECK_ISSUES 用例替代）。
- [ ] **Step 3:** `pytest -q` 全绿；`grep -r "app.chat\|/api/chat" app/ static/ tests/` 确认 0 引用。
- [ ] **Step 4:** 跑 `D:\tmp\phase6c_smoke.py` 冒烟 PASS。
- [ ] **Step 5: Commit** `refactor(chat): remove retired V1 chat after zero references`

---

## Task 9: 最终验收与冻结

**Files:**
- Modify: `README.md`（「已完成」章节补 家庭数据 + AI 顾问统一收口）
- Test: 真实家庭 6 项验收

- [ ] **Step 1:** 复用 Phase 6B 真实家庭脚本重跑 6 项验收：① 建档 ② 数据闭环 ③ 七意图（CHECK_ISSUES/GOALS 现为有 substance）④ 拒算门 ⑤ VIP 边界 ⑥ 数据修改→财富结果同步。
- [ ] **Step 2:** 专项确认：`/api/chat` 已不存在；`/api/agent/chat` 是唯一 AI 顾问入口；`/api/confirm` 迁移后正常。
- [ ] **Step 3:** 更新 `README.md`。
- [ ] **Step 4:** `git add -A && git commit`（记录最终 commit hash，作为 V0.1 测试版冻结点）。

---

## 自检清单（写完后自查）

1. **Spec 覆盖**：建档吸收 ✓（Task 2/3）· 统一入口 ✓（Task 3/5/7）· P1 三意图修复 ✓（Task 4）· Issues 口径 ✓（Task 2 落地 + build_issues）· 成员月收入 ✓（Task 6）· `/api/confirm` 兼容 ✓（Task 5）· `/api/report`/`/api/family` 不动 ✓（未列入任务）。
2. **不破坏既有契约**：`AGENT_INTENTS`/`MetricRef`/`handle()`/`build_overview` 全部未列在 Modify 清单中。
3. **占位符扫描**：无 TBD/TODO。
4. **类型一致**：`converse` 返回 `ConfirmCard | AgentResponse`；端点 `.model_dump()`；`build_metrics` 新分支返回 `list[MetricRef]`。
