# 4.1 人性化收尾：AI 顾问对话入口 + 沙盘决策历史 — 工作计划

> 阶段 4.1 · 第 3 波。补完剩下 3 个铁律 UI 缺口：④ 给下一步（按钮化）、⑩ 数字可追溯（依据）、
> ⑥ 撤销回退（决策历史）。全部「前端 + 文案 + 展示」，**0 动 Engine / Decision / Schema 冻结契约**。

## 现状（已实机确认）

| 铁律 | 现状 | 缺口 |
|------|------|------|
| ④ 给下一步 | `next_actions` 封闭集，当前仅 `"upgrade"`（`errors.py` 门禁产出） | 渲染成 `chip` 纯文本，非按钮 |
| ⑩ 数字可追溯 | `MetricRef.source` 是字段路径，chat 已渲染 | 没加「依据：」前缀，像裸路径 |
| ⑥ 撤销回退 | `compare_scenario` 只读不写库（引擎已做到） | 沙盘无决策历史，无法回退 |

关键事实：
- `AgentResponse.next_actions: list[str]`，后端确定性只产出 `["upgrade"]`（VIP 门禁 forbidden）。
- `MetricRef` = `{key,label,unit,value,source}`；`source` 是字段路径（如 `overview.retirement.rfr`），
  `label` 已是人话（如「养老可投资覆盖 RFR」）。
- 意图路由有确定性关键词（`退休`→CHECK_RETIREMENT、`风险`→CHECK_ISSUES…），命中即不调 LLM。

## 边界铁律（本波绝不触碰）

- 不改 `app/` 任何文件（Engine / Decision / Schema / DB / Agent Runtime 全部不动）。
- 「依据」只加前缀展示，**不改写 source 路径**（那是可追溯凭证，不是给用户看的名字，人话名在 label）。
- 决策历史是**前端会话态**（`store` 内存），不落库、不 localstorage——历史绑定当次数据快照，
  跨会话可能失效，故不做持久化（避免误导用户拿旧结论当新结论）。

## 文件清单

- 改 `static/format.js` — 加 `NEXT_ACTION_LABELS`
- 改 `static/views/chat.js` — 铁律⑩「依据：」+ 铁律④ 下一步按钮
- 改 `static/store.js` — `sandbox` 切片加 `history: []`
- 改 `static/views/sandbox.js` — 铁律⑥ 决策历史（push / restore / clear）
- 改 `static/style.css` — 新增样式
- 测 `tests/js/humanize.test.js` — 扩展 NEXT_ACTION_LABELS 断言
- 测 `tests/e2e/test_advisor_humanize.py` — 新增 Playwright 冒烟

---

## Task 1：NEXT_ACTION_LABELS 纯映射（format.js）

**改 `static/format.js`**（追加到末尾，紧邻 `SCENARIO_LABELS`）：

```js
// 对话「下一步」动作键 → 按钮文案（纯展示映射；键与后端 next_actions 封闭集对齐）
export const NEXT_ACTION_LABELS = {
  upgrade: '一键升级 VIP',
};
```

**测 `tests/js/humanize.test.js`**（追加一个 test）：

```js
test('NEXT_ACTION_LABELS 覆盖已知下一步动作键', () => {
  assert.ok(src.includes("upgrade: '一键升级 VIP'"), 'format.js 缺 NEXT_ACTION_LABELS.upgrade');
});
```

**验证**：`node --test tests/js/humanize.test.js` → 先 fail（缺映射），实现后 3/3 通过。

---

## Task 2：对话「依据」+「下一步」按钮（chat.js）

**改 `static/views/chat.js`**：

import（第 8 行）：

```js
import { fmtMoney, NEXT_ACTION_LABELS } from '../format.js';
```

setup 里 `doUpgrade` 之后加两个方法，并在 return 里带上：

```js
    function nextActionLabel(a) { return NEXT_ACTION_LABELS[a] || a; }
    // 下一步按钮：仅已知动作键可点击（当前仅 upgrade → 一键升级），未知键不越权
    function runNextAction(a) { if (a === 'upgrade') doUpgrade(); }
```

return 里加 `nextActionLabel, runNextAction`。

**template 两处改动**：

① 铁律⑩（metrics 的 source 加「依据：」前缀）：

```html
            <li v-for="(x, i) in m.agent.metrics" :key="i">
              <b>{{ x.label }}</b> {{ fmtMetric(x) }}
              <span class="src">依据：{{ x.source }}</span>
            </li>
```

② 铁律④（next_actions 从 chip 改为按钮）：

```html
          <div v-if="m.agent.next_actions && m.agent.next_actions.length" class="agent-next">
            <button v-for="(a, i) in m.agent.next_actions" :key="i" class="btn-mini rec-sim" @click="runNextAction(a)">
              {{ nextActionLabel(a) }} →
            </button>
          </div>
```

> 「依据：」只加前缀；source 路径保持原样（可追溯凭证）。label 已是人话，故不重复翻译。

---

## Task 3：sandbox 切片加 history（store.js）

**改 `static/store.js:28`**：

```js
  // —— 切片：情景沙盘（单次模拟 + 多方案对比 + 决策历史）——
  // history：会话内决策历史（每次对比快照），供撤销/回退；不落库、不持久化。
  sandbox: { result: null, comparison: null, loading: false, error: null, preset: null, history: [] },
```

---

## Task 4：沙盘决策历史（sandbox.js）

**改 `static/views/sandbox.js`**：

① `runCompare()` 成功后压入历史（在 `st.result = await api(...)` 之后、`catch` 之前）：

```js
        st.result = await api(`/api/wealth/scenario/${st.scenario}/compare`, {
          method: 'POST', body, token: store.auth.token,
        });
        // 决策历史：把本次对比（场景 + 参数 + 结果）快照压入会话内历史，供回退
        store.sandbox.history.unshift({
          id: Date.now(),
          scenario: st.scenario,
          label: SCENARIOS[st.scenario].label,
          options: st.options.map(o => ({ id: o.id, params: { ...o.params } })),
          result: st.result,
        });
        if (store.sandbox.history.length > 10) store.sandbox.history.length = 10;
```

② 加 restore / clear 方法（在 `resetToBaseline` 旁）：

```js
    function restoreHistory(h) {
      st.scenario = h.scenario;
      st.options = h.options.map(o => ({ id: o.id, params: { ...o.params } }));
      st.result = h.result;
    }
    function clearHistory() { store.sandbox.history.length = 0; }
```

③ return 里加 `restoreHistory, clearHistory`。

**template**（在「开始对比」按钮的 `.actions` 之后、`.result` 之前插入）：

```html
    <div v-if="store.sandbox.history.length" class="history">
      <div class="history-title">决策历史 · 点击回退到该次对比</div>
      <button v-for="h in store.sandbox.history" :key="h.id" class="history-item" @click="restoreHistory(h)">
        {{ h.label }} · {{ h.options.length }} 个方案
      </button>
      <button class="btn-mini" @click="clearHistory">清空</button>
    </div>
```

> 历史只存当次 `{scenario, label, options, result}` 快照；回退即恢复这三个字段，不重算、不请求后端。

---

## Task 5：样式（style.css）

**改 `static/style.css`**（追加到末尾）：

```css
/* ===== 4.1 人性化：对话依据 / 下一步按钮 / 决策历史 ===== */

.agent-next { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.agent-next .rec-sim { margin-left: 0; }

.src { margin-left: 8px; font-size: 11px; color: var(--muted); }
.src::before { content: '⚓ '; }

.history { margin: 14px 0; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--bg-soft); }
.history-title { font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 8px; }
.history-item {
  display: block; width: 100%; text-align: left; margin: 4px 0;
  padding: 6px 10px; border: 1px solid var(--line); border-radius: var(--radius-sm);
  background: var(--card); color: var(--text); font-size: 13px; cursor: pointer;
}
.history-item:hover { border-color: var(--brand); color: var(--brand-dark); }
```

> `.agent-next` 之前是 `.chip` 的父容器，这里改为按钮容器；`.src` 加 `⚓` 图标强化「出处」语义。

---

## Task 6：headless 冒烟（tests/e2e/test_advisor_humanize.py）

**新建 `tests/e2e/test_advisor_humanize.py`**（复用 `test_real_data_humanize.py` 的 server fixture + seed，全部走确定性路径、0 LLM）：

```python
"""4.1 人性化·顾问对话 + 决策历史 headless 冒烟：依据 / 下一步按钮 / 决策历史 + 0 error。

覆盖：
  ⑩ 对话数字渲染「依据：<source>」
  ⑥ 沙盘对比后生成决策历史，点击可回退
  0 console error / pageerror

确定性：意图用关键词消息（「退休」→ CHECK_RETIREMENT），不依赖真实 LLM。
"""
from __future__ import annotations
import json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx, pytest

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts"

def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("e2e_advisor") / "test.db"
    port = _free_port()
    env = dict(os.environ, AIJIABAN_DB=str(db_path), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(base + "/api/health", timeout=1).status_code == 200: break
            except Exception: time.sleep(0.2)
        else: raise RuntimeError("uvicorn 启动超时")
        yield base
    finally:
        proc.terminate(); proc.wait(timeout=5)

def _seed(base):
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/register", json={"username": "advisor", "password": "secret123"})
        assert r.status_code == 200, r.text
        token = r.json()["token"]; h = {"Authorization": "Bearer " + token}
        assert c.post("/api/upgrade", headers=h).status_code == 200
        entities = [
            ("person", {"name": "本人", "relation": "本人", "birth_year": 1988}),
            ("cashflow", {"flow_type": "income", "category": "工资", "amount": 30000, "period": "月"}),
            ("cashflow", {"flow_type": "expense", "category": "日常", "amount": 28000, "period": "月"}),
            ("asset", {"type": "房产", "name": "自住房", "value": 3000000}),
            ("asset", {"type": "存款", "name": "活期", "value": 2000000}),
        ]
        for table, payload in entities:
            rr = c.post(f"/api/family/entity/{table}", headers=h, json=payload)
            assert rr.status_code == 200, f"{table} 建档失败: {rr.text}"
        return token

def test_advisor_humanize(server):
    from playwright.sync_api import sync_playwright
    token = _seed(server); errors: list[str] = []
    ARTIFACTS.mkdir(exist_ok=True)
    shot = ARTIFACTS / "advisor_humanize.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.add_init_script(f"localStorage.setItem('token', {json.dumps(token)})")

        # ⑩ 对话「依据：」
        page.goto(server + "/#/chat")
        page.wait_for_selector(".chat-input", timeout=10000)
        page.fill(".chat-input", "我的退休准备怎么样")
        page.click(".chat-input-row .btn-primary")
        page.wait_for_selector(".agent-metrics", timeout=10000)
        assert "依据：" in page.inner_text(".agent-metrics"), "对话指标应渲染「依据：<source>」"

        # ⑥ 沙盘决策历史：对比 → 生成历史 → 点击回退恢复
        page.goto(server + "/#/sandbox")
        page.wait_for_selector(".actions .btn-primary", timeout=10000)
        page.click(".actions .btn-primary")
        page.wait_for_selector(".history-item", timeout=15000)
        assert page.locator(".history-item").count() >= 1, "对比后应生成决策历史"
        page.locator(".history-item").first.click()
        page.wait_for_selector(".result", timeout=10000)

        page.screenshot(path=str(shot)); browser.close()

    assert errors == [], f"浏览器 0 error 未满足: {errors}"
    assert shot.exists(), "截图未生成"
```

**验证**：`PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/e2e/test_advisor_humanize.py -v` → 1 passed。

> 铁律④「一键升级 VIP」按钮的**后端路径**已由 `test_agent_chat_scenario_free_user_refused`（FakeLLMProvider）
> 覆盖，且「upgrade → 按钮」映射由 Task 1 的 node 单测覆盖；e2e 不重复触发真实 LLM 的 forbidden 路径。

---

## 全量回归

- `node --test tests/js/humanize.test.js tests/js/scenario-interpret.test.js` → 12+1=13 通过
- `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest -q` → 261+1=262 全绿（新增 1 e2e）

## 提交（3 个 commit）

1. `feat(humanize): 对话数字可追溯「依据」+ 下一步按钮化`
2. `feat(humanize): 沙盘决策历史（撤销/回退）`
3. `feat(humanize): 顾问对话 + 决策历史 headless 冒烟`

## 边界自检

- [ ] 未改 `app/` 任何文件（Engine/Decision/Schema/Agent Runtime 全未动）
- [ ] 「依据：」只加前缀，未改写 source 路径
- [ ] next_actions 只对已知键 `upgrade` 触达动作，未知键不越权
- [ ] 决策历史仅前端会话态，不落库、不持久化
