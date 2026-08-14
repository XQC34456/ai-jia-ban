# 人性化落地到真实数据页 — 工作计划

> 阶段 4.1 人性化 · 第 2 波。承接冷启动（onboarding）已完成，把 10 铁律落地到「真实数据页」：
> 家庭总览（overview）、风险问题（issues）、情景沙盘（sandbox）。
>
> **边界铁律（本波绝不触碰）**：财富数字一律由 Engine/Decision 后端实算；本波只做
> 「前端 + 文案 + 布局」——不改 Engine、不改 Decision、不改 API Schema、不改数据库。
> 「下一步」按钮只负责**切换沙盘场景（默认参数）**，绝不根据 recommendation.target
> 反推任何金额（反推是财富计算，属 Engine，前端不做）。

## 现状缺口（对照 10 铁律）

| 铁律 | 缺口 | 落点 |
|------|------|------|
| ① 先结论后数字 | overview 第一个视觉是 `wealth_score` 大数字 | overview 顶部加「体检报告」横幅 |
| ③ 为什么 | overview 的 InsightPanel 只渲染 title/finding，不渲染 `reason` | InsightPanel 补 reason 列表 |
| ④ 给下一步 | recommendation 有 `scenario`/`actionable` 字段但未按钮化 | rec 渲染「模拟「场景」→」跳沙盘预填场景 |
| ⑤ 模拟不改数据 | sandbox 无「沙盘模式」提示 | sandbox 顶部常驻沙盘模式横幅 |
| 体检报告形态 | overview 无「今日最重要的 3 件事」 | 横幅内取 priorities 前 3 |

> 铁律⑩（数字可追溯 source/MetricRef）**本波不做**：overview 无 source 字段，需要改
> 后端 Schema（属冻结契约 A1–A4）。留到下一波「数据治理」阶段与 MetricRef 一起处理。

## 数据事实（已实机确认）

- `overview.wealth_level` ∈ `{稳健(≥75), 需关注(≥50), 脆弱(<50)}`；`wealth_score` 数字。
- `overview.priorities` = `[{severity:'P0', title:'…'}, …]`（P0→P2 已排序）。
- `overview.recommendations[i].scenario` ∈ `{income_change, prepay, invest}` 或 `null`；
  `actionable` = scenario 非空。**无 `buy_house`**（探测器不推荐买房，正常）。
- 沙盘 `SCENARIOS` 键 ∈ `{buy_house, prepay, invest, income_change}`（与 scenario 对齐）。

## 文件清单

- 改 `static/format.js` — 加 `SCENARIO_LABELS` + `LEVEL_CONCLUSION`（纯展示映射）
- 改 `static/store.js` — `sandbox` 切片加 `preset` 字段
- 改 `static/views/sandbox.js` — 读/清 `preset` 预填场景 + 顶部「沙盘模式」横幅
- 改 `static/views/cards.js` — InsightPanel 补 reason + 「模拟」按钮
- 改 `static/views/issues.js` — rec 补「模拟」按钮
- 改 `static/views/overview.js` — 顶部「体检报告」横幅
- 改 `static/style.css` — 新增横幅/按钮样式（追加到文件末尾）
- 测 `tests/e2e/test_real_data_humanize.py` — 新增 headless 冒烟
- 测 `tests/js/humanize.test.js` — 新增纯映射单测（LEVEL_CONCLUSION/SCENARIO_LABELS 完整性）

---

## Task 1：纯展示映射（format.js）

**改 `static/format.js`**（追加到文件末尾）：

```js
// 情景 → 中文标签（下一步按钮 / 沙盘跳转，纯展示映射，非财富计算）
export const SCENARIO_LABELS = {
  buy_house: '买房',
  prepay: '提前还贷',
  invest: '投资',
  income_change: '收入变化',
};

// 财富健康度等级 → 一句人话结论（体检报告横幅，先结论后数字）
export const LEVEL_CONCLUSION = {
  稳健: '你的家庭财务整体稳健，继续保持。',
  需关注: '你的家庭财务有几个需要关注的地方。',
  脆弱: '你的家庭财务比较脆弱，建议尽快调整。',
};
```

**测 `tests/js/humanize.test.js`**（新建）：

```js
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const src = readFileSync(join(ROOT, 'static', 'format.js'), 'utf8');

test('SCENARIO_LABELS 覆盖沙盘 4 场景', () => {
  for (const k of ['buy_house', 'prepay', 'invest', 'income_change']) {
    assert.ok(src.includes(`${k}:`), `format.js 缺 SCENARIO_LABELS.${k}`);
  }
});

test('LEVEL_CONCLUSION 覆盖 3 个等级', () => {
  for (const k of ['稳健', '需关注', '脆弱']) {
    assert.ok(src.includes(`  ${k}: '`), `format.js 缺 LEVEL_CONCLUSION.${k}`);
  }
});
```

**验证**：`node --test tests/js/humanize.test.js` → 2/2 通过。

---

## Task 2：sandbox 切片加 preset（store.js）

**改 `static/store.js:28`**：

```js
  // —— 切片：情景沙盘（单次模拟 + 多方案对比）——
  sandbox: { result: null, comparison: null, loading: false, error: null, preset: null },
```

> `preset` 是「跳转前预选场景」的跨视图信号：推荐按钮写入，沙盘 setup 读取并清空。
> 仅前端状态，不落库。

---

## Task 3：沙盘预填场景 + 沙盘模式横幅（sandbox.js）

**改 `static/views/sandbox.js`** 的 `setup()` 开头：

```js
    // 预选场景（来自「下一步」按钮跨视图信号），只切换场景 + 默认参数，绝不反推金额
    const preset = store.sandbox.preset;
    store.sandbox.preset = null;
    const initial = (preset && SCENARIOS[preset]) ? preset : 'buy_house';
    const st = reactive({
      scenario: initial,
      options: [{ id: 'A', params: defaultParams(initial) }],
      comparing: false,
      error: null,
      result: null,      // 后端 compare 原始返回 {baseline, options, comparison}
    });
```

**改 template**（`<div class="view">` 内、`<p class="lead">` 之前插入）：

```html
    <div class="sandbox-banner">
      <span class="sandbox-badge">沙盘模式</span>
      <span>下面的模拟只用于对比决策，<b>不会改动你的真实家庭数据</b>。</span>
    </div>
```

---

## Task 4：InsightPanel 补 reason + 「模拟」按钮（cards.js）

**改 `static/views/cards.js`** 顶部 import：

```js
import { store } from '../store.js';
import { navigate } from '../router.js';
import { fmtRatio, CLASS_ORDER, CLASS_LABELS, CLASS_COLORS, FINANCIAL_CLASSES, SEV_TONE, SCENARIO_LABELS } from '../format.js';
```

**改 `InsightPanel`** 的 issue 项（补 reason）与 rec 项（补按钮）：

```html
        <div v-for="i in issues" :key="i.issue_id" class="insight-item">
          <span class="sev" :class="sevTone(i.severity)">{{ i.severity }}</span>
          <div class="insight-body">
            <div class="insight-title">{{ i.title }}</div>
            <div class="insight-finding" v-if="i.finding">{{ i.finding }}</div>
            <ul v-if="i.reason && i.reason.length" class="reason-list">
              <li v-for="(r, idx) in i.reason" :key="idx">{{ r }}</li>
            </ul>
          </div>
        </div>
        <div v-if="recommendations.length" class="insight-recs">
          <div class="insight-recs-title">建议动作</div>
          <div v-for="r in recommendations" :key="r.recommendation_id || r.action" class="rec-item">
            <span class="rec-action">{{ r.action }}</span>
            <span class="rec-detail">{{ r.detail }}</span>
            <button v-if="r.scenario" class="btn-mini rec-sim" @click="simulate(r)">
              模拟「{{ scenarioLabel(r) }}」→
            </button>
          </div>
        </div>
```

**改 `InsightPanel` 的 methods**（在 `sevTone` 旁加两个方法）：

```js
  methods: {
    sevTone: (s) => SEV_TONE[s] || '',
    scenarioLabel: (r) => SCENARIO_LABELS[r.scenario] || '调整',
    // 下一步：切换沙盘场景（默认参数），不反推金额
    simulate(r) { store.sandbox.preset = r.scenario; navigate('sandbox'); },
  },
```

---

## Task 5：风险问题页 rec 补「模拟」按钮（issues.js）

**改 `static/views/issues.js`**：

import 加 `store` 已存在，补 `navigate` + `SCENARIO_LABELS`：

```js
import { store, loadIssues } from '../store.js';
import { navigate } from '../router.js';
import { SEV_TONE, SCENARIO_LABELS } from '../format.js';
```

setup 加方法并 return：

```js
    function simulate(r) { store.sandbox.preset = r.scenario; navigate('sandbox'); }
    function scenarioLabel(r) { return SCENARIO_LABELS[r.scenario] || '调整'; }
    return { store, issues, counts, sevTone, simulate, scenarioLabel };
```

rec 项加按钮（与 cards.js 同构）：

```html
            <div v-for="r in i.recommendations" :key="r.recommendation_id || r.action" class="rec-item">
              <span class="rec-action">{{ r.action }}</span>
              <span class="rec-detail">{{ r.detail }}</span>
              <button v-if="r.scenario" class="btn-mini rec-sim" @click="simulate(r)">
                模拟「{{ scenarioLabel(r) }}」→
              </button>
            </div>
```

---

## Task 6：overview 顶部「体检报告」横幅（overview.js）

**改 `static/views/overview.js`**：

import：

```js
import { store, ensureOverview } from '../store.js';
import { SEV_TONE, LEVEL_CONCLUSION } from '../format.js';
import { HealthScoreCard, NetWorthCard, CashflowCard, DebtCard, GoalsCard, InsightPanel } from './cards.js';

const { onMounted, computed } = Vue;
```

setup 加 `top3` + 工具，return：

```js
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });
    const top3 = computed(() => ((store.overview && store.overview.priorities) || []).slice(0, 3));
    function sevTone(s) { return SEV_TONE[s] || ''; }
    return { store, top3, LEVEL_CONCLUSION, sevTone };
  },
```

template 在 `<template v-else-if="store.overview">` 内、`.kpi-grid` 之前插入：

```html
        <div class="report-banner" :class="store.overview.wealth_score >= 80 ? 'lv-good' : store.overview.wealth_score >= 60 ? 'lv-warn' : 'lv-bad'">
          <div class="report-verdict">
            <span class="report-label">家庭体检报告</span>
            <div class="report-conclusion">{{ LEVEL_CONCLUSION[store.overview.wealth_level] || '这是你当前的家庭财务画像' }}</div>
          </div>
          <div class="report-top3" v-if="top3.length">
            <div class="report-top3-title">今日最重要的 {{ top3.length }} 件事</div>
            <div v-for="(p, i) in top3" :key="i" class="report-top3-item">
              <span class="sev" :class="sevTone(p.severity)">{{ p.severity }}</span>{{ p.title }}
            </div>
          </div>
          <div class="report-score">{{ store.overview.wealth_score }}<span>财富评分</span></div>
        </div>
```

> 铁律①：横幅把「人话结论 + 今日最重要的 3 件事」放到最前，`wealth_score` 降为横幅
> 右侧的小字评分（不再是第一个视觉）。KPI 卡网格仍在下方，数字照常可查。

---

## Task 7：样式（style.css）

**改 `static/style.css`**（追加到文件末尾，使用现有 CSS 变量）：

```css
/* ===== 4.1 人性化：体检报告横幅 / 沙盘模式提示 / 下一步按钮 ===== */

.report-banner {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 24px;
  padding: 18px 20px;
  margin-bottom: 16px;
  border: 1px solid var(--line);
  border-left: 4px solid var(--brand);
  border-radius: var(--radius);
  background: var(--card);
  box-shadow: var(--shadow-sm);
}
.report-banner.lv-warn { border-left-color: var(--score-caution); }
.report-banner.lv-bad { border-left-color: var(--score-bad); }
.report-verdict .report-label { font-size: 12px; color: var(--muted); letter-spacing: .04em; }
.report-conclusion { font-size: 17px; font-weight: 700; color: var(--text); margin-top: 4px; }
.report-top3 { display: flex; flex-direction: column; gap: 6px; min-width: 260px; }
.report-top3-title { font-size: 12px; color: var(--muted); }
.report-top3-item { font-size: 13px; color: var(--text); display: flex; align-items: center; gap: 8px; }
.report-top3-item .sev { margin: 0; }
.report-score { text-align: right; }
.report-score { font-size: 32px; font-weight: 800; color: var(--text); line-height: 1; }
.report-score span { display: block; font-size: 12px; font-weight: 400; color: var(--muted); margin-top: 4px; }

.sandbox-banner {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; margin-bottom: 14px;
  border: 1px solid var(--brand-line); border-radius: var(--radius-sm);
  background: var(--brand-soft); color: var(--text); font-size: 13px;
}
.sandbox-badge {
  flex-shrink: 0; padding: 2px 10px; border-radius: 999px;
  background: var(--brand); color: #fff; font-size: 12px; font-weight: 600;
}

.rec-sim { margin-left: auto; white-space: nowrap; color: var(--brand-dark); border-color: var(--brand-line); }
.rec-sim:hover { color: #fff; background: var(--brand); border-color: var(--brand); }
```

---

## Task 8：headless 冒烟（tests/e2e/test_real_data_humanize.py）

**新建 `tests/e2e/test_real_data_humanize.py`**（复用 sandbox_smoke 的 server fixture + seed 模式）：

```python
"""4.1 人性化·真实数据页 headless 冒烟：体检报告横幅 + 下一步按钮 + 沙盘模式提示 + 0 error。"""
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
    db_path = tmp_path_factory.mktemp("e2e_humanize") / "test.db"
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
        r = c.post("/api/register", json={"username": "humanize", "password": "secret123"})
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

def test_real_data_humanize(server):
    from playwright.sync_api import sync_playwright
    token = _seed(server); errors: list[str] = []
    ARTIFACTS.mkdir(exist_ok=True)
    shot = ARTIFACTS / "real_data_humanize.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.add_init_script(f"localStorage.setItem('token', {json.dumps(token)})")
        page.goto(server + "/#/overview")
        page.wait_for_selector(".report-banner", timeout=10000)

        # ① 体检报告横幅：先结论后数字 + 今日最重要的 3 件事
        banner = page.inner_text(".report-banner")
        assert "家庭体检报告" in banner
        assert "今日最重要的" in banner, "横幅应显示「今日最重要的 N 件事」"

        # ④ 下一步按钮：推荐带 scenario → 「模拟」按钮存在
        sim_btns = page.locator(".rec-sim").count()
        assert sim_btns > 0, "应有「模拟」按钮渲染"

        # 点击第一个「模拟」→ 跳到沙盘并预选场景（默认参数，不反推金额）
        page.locator(".rec-sim").first.click()
        page.wait_for_selector(".sandbox-banner", timeout=10000)
        assert "沙盘模式" in page.inner_text(".sandbox-banner"), "沙盘应有常驻沙盘模式提示"
        assert "不会改动你的真实家庭数据" in page.inner_text(".sandbox-banner")
        page.screenshot(path=str(shot)); browser.close()

    assert errors == [], f"浏览器 0 error 未满足: {errors}"
    assert shot.exists(), "截图未生成"
```

**验证**：`PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/e2e/test_real_data_humanize.py -v` → 1 passed。

---

## 全量回归

- `node --test tests/js/humanize.test.js` → 2/2
- `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest -q` → 260+1 全绿（新增 1 个 e2e）
- `node --test tests/js/scenario-interpret.test.js` → 10/10（确认未破坏 C3）

## 提交（3 个 commit）

1. `feat(humanize): overview 顶部体检报告横幅，先结论后数字`
2. `feat(humanize): 推荐「下一步」按钮化，跳沙盘预选场景`
3. `feat(humanize): 沙盘常驻沙盘模式提示 + 补 reason 渲染`

## 边界自检

- [ ] 未改 `app/` 任何文件（Engine/Decision/Schema/DB 全部未动）
- [ ] 「模拟」按钮只 `store.sandbox.preset = r.scenario`，未根据 `target` 反推金额
- [ ] 新增纯映射仅展示用途，无财富结论
- [ ] 铁律⑩（source/MetricRef）显式留到「数据治理」阶段，不硬塞
