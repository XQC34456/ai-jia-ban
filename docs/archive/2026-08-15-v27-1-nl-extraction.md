# V27.1 自然语言多字段建档 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户一句话说完「月收入 3.8 万、房贷 3000、房租 5000、车贷 3500、孩子学费 3000、生活费 5000」时，系统一次抽出全部 6 项，进批量确认卡，确认后一次落库。

**Architecture:** 抽取走 `LLMProvider.chat()`（function-calling，复用已注入的 DeepSeek Provider），产出 `actions[]`；确定性 `validate_actions()` 校验；`RuleExtractor` 兜底（离线/降级）；`ConfirmCard` 升级成分组展示；确认后才 `apply_action` 落库。**铁律不破：抽取=转写用户原话（非计算），数字只在确认卡确认后进库，Engine 才确定性计算。**

**Tech Stack:** FastAPI + Pydantic v2 + SQLite；LLM 走 `LLMProvider.chat()` function-calling；前端 Vue 3 CDN。

## Global Constraints

- 数字铁律：抽取只转写用户亲口说的金额，**绝不计算/编造派生数**（结余率、评分、缺口等一律 Engine）。
- 落地前绝不写库：抽取→pending→确认卡→确认后才 `apply_action`。
- 只扩不减：`ConfirmCard` 保留 `items`，新增 `groups`；不破坏旧前端/旧测试。
- Provider 抽象不破：核心层只认 `LLMProvider` Protocol，绝不 import httpx/requests。
- 抽取代用与顾问同一套 `LLM_API_KEY/LLM_MODEL/LLM_BASE_URL`（`get_provider()`），不新增配置。

---

### Task 1: LLM 抽取接入共享 Provider（function-calling）

**Files:**
- Modify: `app/extraction.py`（新增 `extract_with_llm()`；修 `_summarize()` 让 summary 带 category/period）

**Interfaces:**
- Consumes: `LLMProvider.chat(messages, tools) -> {"content","tool_calls":[{"id","name","arguments"}]}`（[provider.py](app/agent/provider.py) 已冻结）。
- Produces: `extract_with_llm(message: str, llm) -> list[dict]`（规范化动作列表，无结果→`[]`）。

- [ ] **Step 1: 写失败测试**

`tests/test_v27_extraction.py`：
```python
from app.agent.provider import FakeLLMProvider
from app.extraction import extract_with_llm


def test_extract_with_llm_multi_field():
    llm = FakeLLMProvider(chat_script=[{
        "content": None,
        "tool_calls": [{
            "id": "c1", "name": "record_family_info",
            "arguments": {"actions": [
                {"kind": "income", "fields": {"category": "工资", "amount": 38000, "period": "月", "person_name": "本人"}},
                {"kind": "expense", "fields": {"category": "房租", "amount": 5000, "period": "月"}},
                {"kind": "liability", "fields": {"type": "房贷", "monthly_payment": 3000}},
            ]},
        }],
    }])
    actions = extract_with_llm("月收入3.8万，房贷3000，房租5000", llm)
    kinds = [a["kind"] for a in actions]
    assert kinds == ["income", "expense", "liability"]
    assert actions[0]["fields"]["amount"] == 38000


def test_extract_with_llm_no_toolcall_returns_empty():
    llm = FakeLLMProvider(chat_script=[{"content": "好的", "tool_calls": []}])
    assert extract_with_llm("我的资产配置合理吗", llm) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_v27_extraction.py -v`
Expected: `ImportError: cannot import name 'extract_with_llm'`

- [ ] **Step 3: 实现 `extract_with_llm` + 修 `_summarize`**

在 `app/extraction.py`（`_normalize_action` 之后）新增：
```python
def extract_with_llm(message: str, llm) -> list[dict[str, Any]]:
    """用注入的 LLMProvider（chat + function-calling）做一次结构化抽取。

    返回规范化动作列表；llm 为 None / chat 返回 None / 无 tool_calls → []。
    金额全部来自用户原话转写（非计算），符合铁律。
    """
    result = llm.chat(
        [
            {"role": "system", "content": f"当前年份是 {date.today().year} 年。"},
            {"role": "user", "content": message},
        ],
        [_EXTRACT_TOOL],
    )
    if not result:
        return []
    actions: list[dict[str, Any]] = []
    for call in result.get("tool_calls") or []:
        if call.get("name") != "record_family_info":
            continue
        args = call.get("arguments") or {}
        for a in args.get("actions", []):
            norm = _normalize_action(a)
            if norm is None:
                continue
            norm["summary"] = _summarize(norm)
            actions.append(norm)
    return actions
```

重写 `_summarize`（替换现有第 329–353 行，修掉「category 不进 summary」的缺字段显示）：
```python
def _summarize(action: dict[str, Any]) -> str:
    f = action["fields"]
    kind = action["kind"]

    if kind == "liability":
        label = f.get("type") or f.get("name") or "负债"
        if f.get("monthly_payment"):
            return f"{label}月供 {f['monthly_payment']:,.0f} 元"
        if f.get("principal"):
            return f"{label}本金 {f['principal']:,.0f} 元"
        return label

    if kind == "person":
        name = f.get("name") or "成员"
        if f.get("birth_year"):
            age = date.today().year - int(f["birth_year"])
            return f"{name}（{age} 岁）"
        return name

    if kind == "income":
        who = f.get("person_name") or ""
        cat = f.get("category") or "工资"
        return f"{who}{cat} {f['amount']:,.0f} 元/月" if f.get("amount") is not None else f"{who}{cat}"

    if kind == "expense":
        cat = f.get("category") or "其他"
        return f"{cat} {f['amount']:,.0f} 元/月" if f.get("amount") is not None else cat

    if kind == "asset":
        label = f"{f.get('type') or '资产'}{f.get('name') or ''}".strip()
        return f"{label} {f['value']:,.0f} 元" if f.get("value") is not None else label

    if kind == "goal":
        g = f.get("type") or "目标"
        return f"{g} {f['target_amount']:,.0f} 元" if f.get("target_amount") is not None else g

    return kind
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_v27_extraction.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/extraction.py tests/test_v27_extraction.py
git commit -m "feat(v27.1): LLM function-calling extraction via shared provider"
```

---

### Task 2: 抽取调度（LLM 主 + 规则兜底）+ 确定性校验

**Files:**
- Modify: `app/extraction.py`（新增 `validate_actions()`）
- Modify: `app/agent/profile.py`（`extract_actions` 接 `llm`，走 LLM→校验→规则兜底→校验）
- Modify: `app/agent/entry.py`（`converse` 传 `llm` 进 `extract_actions`）

**Interfaces:**
- Consumes: Task 1 的 `extract_with_llm`；`RuleExtractor().extract`。
- Produces: `validate_actions(actions) -> list[dict]`；`extract_actions(message, llm=None) -> list[dict]`。

- [ ] **Step 1: 写失败测试**

`tests/test_v27_extraction.py` 追加：
```python
from app.extraction import validate_actions


def test_validate_actions_drops_negative_amount():
    actions = [{"kind": "income", "fields": {"category": "工资", "amount": -500, "period": "月"}}]
    assert validate_actions(actions) == []


def test_validate_actions_dedups_batch():
    a = {"kind": "expense", "fields": {"category": "房租", "amount": 5000, "period": "月"}}
    assert validate_actions([a, dict(a)]) == [a]  # 批内同 kind+fields 去重


def test_extract_actions_llm_primary_rule_fallback():
    llm = FakeLLMProvider(chat_script=[{"content": None, "tool_calls": []}])  # LLM 抽不到 → 规则兜底
    actions = extract_actions("我月薪2万", llm)
    assert any(a["kind"] == "income" and a["fields"]["amount"] == 20000 for a in actions)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_v27_extraction.py -v`
Expected: `NameError: validate_actions` / `TypeError: extract_actions() got unexpected keyword 'llm'`

- [ ] **Step 3: 实现**

`app/extraction.py` 新增 `validate_actions`（放在 `_summarize` 之后）：
```python
def validate_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """确定性校验：金额必须正数/有限、period 合法、批内去重。不过则丢弃该动作。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in actions:
        norm = _normalize_action(a)
        if norm is None:
            continue
        f = norm["fields"]
        bad = False
        for k in ("amount", "value", "monthly_payment", "principal", "target_amount"):
            v = f.get(k)
            if v is not None and (not isinstance(v, (int, float)) or v != v or v <= 0):
                bad = True
        if bad:
            continue
        if f.get("period") not in (None, "月", "年"):
            f["period"] = "月"
        key = (norm["kind"], json.dumps(f, ensure_ascii=False, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out
```

`app/agent/profile.py`：改 import + `extract_actions`：
```python
from ..extraction import RuleExtractor, extract_with_llm, validate_actions
from .provider import LLMProvider

def extract_actions(message: str, llm: LLMProvider | None = None) -> list[dict[str, Any]]:
    """自然语言 → 建档动作；空列表 = 非建档表述（交给七意图 Agent）。

    V27.1：LLM 主抽取（一次抽全）→ validate 校验；失败/无结果 → RuleExtractor 兜底。
    两条路径产物都过确定性校验，且只在确认卡确认后才落库（防 LLM 幻觉污染数据）。
    """
    if llm is not None:
        try:
            actions = extract_with_llm(message, llm)
        except Exception:
            actions = []
        if actions:
            return validate_actions(actions)
    return validate_actions(RuleExtractor().extract(message))
```

`app/agent/entry.py` 第 26 行改为：
```python
    actions = extract_actions(message, llm=llm)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_v27_extraction.py tests/test_agent_entry.py -v`（如无 test_agent_entry.py 则 `pytest tests/ -v`）
Expected: 全绿，既有建档测试不回归。

- [ ] **Step 5: Commit**

```bash
git add app/extraction.py app/agent/profile.py app/agent/entry.py tests/test_v27_extraction.py
git commit -m "feat(v27.1): LLM-primary extraction with rule fallback + deterministic validation"
```

---

### Task 3: 批量确认卡（后端 groups 分组）

**Files:**
- Modify: `app/schemas/agent.py`（`ConfirmCard` 加 `groups`）
- Modify: `app/agent/profile.py`（`create_confirm` 建分组）
- Test: `tests/test_v27_extraction.py`（或 `tests/test_profile.py`）

**Interfaces:**
- Consumes: `actions`（含 `kind`/`summary`）。
- Produces: `ConfirmCard.groups: list[dict]` = `[{"label","icon","items":[summary,...]}]`。

- [ ] **Step 1: 写失败测试**

```python
from app.agent.profile import create_confirm


def test_confirm_card_groups_by_kind():
    actions = [
        {"kind": "income", "fields": {"category": "工资", "amount": 38000, "period": "月"},
         "summary": "工资 38,000 元/月"},
        {"kind": "expense", "fields": {"category": "房租", "amount": 5000, "period": "月"},
         "summary": "房租 5,000 元/月"},
        {"kind": "expense", "fields": {"category": "生活", "amount": 5000, "period": "月"},
         "summary": "生活 5,000 元/月"},
    ]
    card = create_confirm(1, actions)
    labels = [g["label"] for g in card.groups]
    assert labels == ["收入", "支出"]
    assert card.groups[1]["items"] == ["房租 5,000 元/月", "生活 5,000 元/月"]
    assert len(card.items) == 3  # items 保留（只扩不减）
```

- [ ] **Step 2: 跑测试确认失败**

Expected: `AttributeError: 'ConfirmCard' object has no attribute 'groups'`（或断言失败）

- [ ] **Step 3: 实现**

`app/schemas/agent.py` 的 `ConfirmCard`：
```python
class ConfirmCard(BaseModel):
    """建档确认卡片：抽取到动作后返回，等用户在 /api/confirm 确认落地。"""
    type: Literal["confirm"] = "confirm"
    pending_id: str
    message: str
    items: list[str] = Field(default_factory=list)
    groups: list[dict] = Field(default_factory=list)   # V27.1 分组展示（只扩不减）
```

`app/agent/profile.py` 顶部加：
```python
_KIND_META = {
    "income": ("收入", "🟢"), "expense": ("支出", "🔵"),
    "asset": ("资产", "🟢"), "liability": ("负债", "🟠"),
    "goal": ("目标", "🟣"), "person": ("成员", "⚪"),
}
```

`create_confirm` 改为：
```python
def create_confirm(family_id: int, actions: list[dict[str, Any]]) -> ConfirmCard:
    pending_id = uuid.uuid4().hex
    _PENDING[pending_id] = {"family_id": family_id, "actions": actions}
    groups: list[dict] = []
    for a in actions:
        label, icon = _KIND_META.get(a["kind"], ("其他", "⚪"))
        g = next((g for g in groups if g["label"] == label), None)
        if g is None:
            g = {"label": label, "icon": icon, "items": []}
            groups.append(g)
        g["items"].append(a["summary"])
    return ConfirmCard(
        pending_id=pending_id,
        message="我理解到以下信息，确认后我就为你建档：",
        items=[a["summary"] for a in actions],
        groups=groups,
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_v27_extraction.py -v`
Expected: 通过

- [ ] **Step 5: Commit**

```bash
git add app/schemas/agent.py app/agent/profile.py tests/test_v27_extraction.py
git commit -m "feat(v27.1): grouped confirm card (backend)"
```

---

### Task 4: 批量确认卡（前端分组渲染）

**Files:**
- Modify: `static/views/chat.js`（存 `groups`；分组渲染；更新占位示例文案）

**Interfaces:**
- Consumes: `d.groups`（后端 ConfirmCard）。
- Produces: 分组确认卡 UI（label 头 + icon + items 列表；`groups` 缺失时回退旧的 `items` 平铺）。

- [ ] **Step 1: 改存储**

`send()` 里第 147 行改为：
```js
store.chat.messages.push({ type: 'confirm', pendingId: d.pending_id, message: d.message, items: d.items, groups: d.groups || [], resolved: false });
```

- [ ] **Step 2: 改模板**

把第 381–384 行的确认卡模板改为分组渲染（保留 `items` 兜底）：
```html
<div v-if="m.type === 'confirm'" class="chat-confirm">
  <div class="chat-confirm-text">{{ m.message }}</div>
  <div v-if="m.groups && m.groups.length" class="confirm-groups">
    <div v-for="(g, gi) in m.groups" :key="gi" class="confirm-group">
      <div class="confirm-group-head">{{ g.icon }} {{ g.label }}</div>
      <ul><li v-for="(it, i) in g.items" :key="i">{{ it }}</li></ul>
    </div>
  </div>
  <ul v-else><li v-for="(it, i) in m.items" :key="i">{{ it }}</li></ul>
  <div class="chat-confirm-actions">
    <template v-if="!m.resolved">
      <button class="btn-primary btn-sm" @click="confirm(m, true)">确认全部</button>
      <button class="btn-ghost btn-sm" @click="confirm(m, false)">取消</button>
    </template>
    <span v-else class="muted">已处理</span>
  </div>
</div>
```

- [ ] **Step 3: 加分组样式 + 更新占位示例**

在 chat.js 的 `<style>` 加：
```css
.confirm-group { margin: 8px 0; }
.confirm-group-head { font-weight: 600; font-size: 13px; color: #4A443C; margin-bottom: 2px; }
```

把第 378 行占位示例改为多字段：
```html
试着告诉我你的家庭情况，例如：「我月收入 3.8 万，房贷 3000，房租 5000，车贷 3500，孩子学费 3000，生活费 5000」。
```

- [ ] **Step 4: DOM 自证（Playwright，不提交）**

写 `.verify/verify_nl_extract.py`：注册→升级→输入多字段一句→断言确认卡出现 6 项、分组含「收入/支出/负债」、点「确认全部」→ 断言 `/api/wealth/overview` 里 cashflow 出现 6 条（income 1 + expense 4 + liability 1 组）。

- [ ] **Step 5: Commit**

```bash
git add static/views/chat.js
git commit -m "feat(v27.1): grouped confirm card (frontend)"
```

---

## Scope Cuts（YAGNI，明确不在 V27.1）

- **「修改其中一项」内联编辑** → 推迟 P1。V27.1 用户可「取消」后重说，或确认后再补录。
- **「补充遗漏信息」按钮** → 聊天框本身即输入口，无需新按钮。
- **定性目标抽取（如「降低家庭风险」）** → 不含金额，交给七意图 Agent（CHECK_ISSUES/CHECK_ALLOCATION），不落 goal 表。
- **顾问五层回答结构** → 已存在（`AdvisorLayers` + `layers.py::attach_layers`），V27.1 只验收不新建。

## Self-Review

- **Spec 覆盖**：P0 五项中「多字段抽取 / LLM+Rule 兜底 / 批量确认卡 / 数据完整性校验」由 Task 1–4 覆盖；「顾问回答结构化」已存在，标注为验收项。
- **占位符**：无 TBD/TODO。
- **类型一致**：`extract_actions(message, llm)` 签名在 Task 2 定义，`entry.py` 调用处一致；`groups` 字段 Task 3 定义、Task 4 消费，字段名一致。
