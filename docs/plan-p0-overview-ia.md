# P0 · Overview 信息架构归位 实施计划

> 上承 [ui-audit-2026-08-15.md](ui-audit-2026-08-15.md) 诊断 1（头重脚轻）。
> **目标**：Overview 首屏完成「财务现状 → 核心问题 → 下一步行动」三步闭环，顺序改为 ①财富数字 → ②最大问题 → ③财富结构 → ④最近变化 → ⑤下一步行动。
> **架构**：纯前端单文件改动（`static/views/overview.js`），只消费已存在的 `store.actionPlan` + 调用共享 `setActionStatus`，零新增 CSS、零后端改动、零业务逻辑复制。
> **技术栈**：Vue 3 CDN（hash 路由）+ 既有 style.css 类。

---

## Global Constraints（红线，本次改动一律遵守）

1. **铁律 P1**：财富数字零计算。本改动纯呈现/排序/消费现有数据，绝不新增任何数字计算。
2. **不复制 Action Plan 业务逻辑**：`adopt`（采纳去重）、建议匹配、计划生成逻辑**全部留在 `issues.js`**。Overview 只做两件事——读 `store.actionPlan.data.plans`、调共享 `setActionStatus(id, status)` 勾选完成。
3. **零新增 CSS**：复用既有类 `.plan-panel` `.plan-item` `.plan-check` `.plan-body` `.plan-action` `.plan-detail` `.empty-hint` `.err-box` `.card-link`。
4. **不动**：导航结构 / 配色 token / 组件库 / 动画 / 任何装饰性「高级感」（对齐 ui-audit 红线）。
5. **不改后端**：`/api/wealth/action-plan` 端点与 store 切片均已存在，无需动。
6. **④ 最近变化不制造空模块**：stale 横幅仅 `v-if="staleBanner"` 条件渲染，无变化时零占位。

---

## 现状 → 目标（Overview DOM 顺序）

| 现状（从上到下） | 目标（从上到下） |
|------------------|------------------|
| stale-banner（失效提醒） | loading / error |
| loading / error | **① kpi-grid**（财富数字） |
| report-banner（top3） | **② report-banner**（最大问题） |
| kpi-grid（财富数字） | **③ 7 维雷达**（财富结构） |
| 7 维雷达 | **④ stale-banner**（最近变化，条件） |
| goals-card + insight-panel | **⑤ plan-panel**（下一步行动，新增） |
| | goals-card + insight-panel（补充深度，末位保留） |

---

## 唯一改动文件：`static/views/overview.js`

### Step 1 · 改 import（加两个共享 store 函数）

**现状**（`overview.js:3`）：
```js
import { store, ensureOverview, loadReview, recordEvent } from '../store.js';
```

**改为**：
```js
import { store, ensureOverview, loadReview, loadActionPlan, setActionStatus, recordEvent } from '../store.js';
```

### Step 2 · Vue 解构加 `ref`

**现状**（`overview.js:9`）：
```js
const { onMounted, computed } = Vue;
```

**改为**：
```js
const { onMounted, computed, ref } = Vue;
```

### Step 3 · onMounted 加加载 actionPlan

**现状**（`overview.js:14-17`）：
```js
onMounted(() => {
  ensureOverview().catch(() => {});
  loadReview().catch(() => {});
});
```

**改为**：
```js
onMounted(() => {
  ensureOverview().catch(() => {});
  loadReview().catch(() => {});
  loadActionPlan().catch(() => {});
});
```

### Step 4 · setup() 末尾加 ⑤ 的 computed + toggle（消费共享数据，零业务复制）

在 `goReassess` 定义（`overview.js:51`）之后、`return`（`overview.js:53`）之前插入：

```js
  // —— ⑤ 下一步行动：只消费 store.actionPlan，调共享 setActionStatus，绝不复制采纳/去重逻辑 ——
  const todoPlans = computed(() => {
    const plans = (store.actionPlan.data && store.actionPlan.data.plans) || [];
    return plans.filter(p => p.status === 'todo');
  });
  const planError = ref(null);
  async function toggle(p) {
    planError.value = null;
    const next = p.status === 'done' ? 'todo' : 'done';
    try { await setActionStatus(p.id, next); }
    catch (e) { planError.value = e.message || '更新失败'; }
  }
```

### Step 5 · return 对象追加三个绑定

**现状**（`overview.js:53-54`）：
```js
  return { store, top3, bannerTone, LEVEL_CONCLUSION, sevTone,
           navigate, staleBanner, staleReasons, fmtChangeVal, goReassess };
```

**改为**：
```js
  return { store, top3, bannerTone, LEVEL_CONCLUSION, sevTone,
           navigate, staleBanner, staleReasons, fmtChangeVal, goReassess,
           todoPlans, planError, toggle };
```

### Step 6 · template 重排（核心）

**整段替换**（`overview.js:56-98` 的 `<template>` 块）为：

```html
  template: `
    <div class="view">
      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
      <template v-else-if="store.overview">
        <!-- ① 财富数字：净资产 / 月结余 / 健康评分 -->
        <div class="kpi-grid">
          <health-score-card :o="store.overview" />
          <net-worth-card :o="store.overview" />
          <cashflow-card :o="store.overview" />
          <debt-card :o="store.overview" />
        </div>

        <!-- ② 最大问题：Top 3 主要矛盾 -->
        <div class="report-banner" :class="bannerTone">
          <div class="report-label">家庭体检报告</div>
          <template v-if="top3.length">
            <div class="report-top3-title">你的家庭现在最值得关注的 {{ top3.length }} 件事</div>
            <div class="report-top3-item" v-for="(p, i) in top3" :key="i">
              <span class="sev" :class="sevTone(p.severity)">{{ p.severity }}</span>{{ p.title }}
            </div>
          </template>
          <div v-else class="report-no-issue">目前没有发现重大财富问题，家庭财务稳健 🎉</div>
          <div class="report-status">
            <span>{{ LEVEL_CONCLUSION[store.overview.wealth_level] || '这是你当前的家庭财务画像' }}</span>
            <span class="report-score-inline">财富评分 {{ store.overview.wealth_score }}</span>
          </div>
        </div>

        <!-- ③ 财富结构：7 维雷达 -->
        <section class="panel">
          <div class="card-title">财富健康 7 维雷达 <a href="#/health" class="card-link">查看各维下钻 →</a></div>
          <health-radar :data="store.overview.dimensions" />
        </section>

        <!-- ④ 最近变化：数据失效时才出现，不制造空模块 -->
        <div v-if="staleBanner" class="stale-banner">
          <div class="stale-title">⚠️ 你的家庭数据已变化，上次建议可能已过时</div>
          <div v-if="staleReasons.length" class="stale-chips">
            <span v-for="r in staleReasons" :key="r.key" class="stale-chip">{{ r.label }}：{{ fmtChangeVal(r) }}</span>
          </div>
          <div v-else class="stale-fallback">判断依赖的关键数据已变化，建议重新评估</div>
          <button class="btn-primary btn-sm" @click="goReassess">去 AI 顾问重新评估</button>
        </div>

        <!-- ⑤ 下一步行动：消费 store.actionPlan，提供 查看 / 完成 / 去顾问 -->
        <section class="panel plan-panel">
          <div class="card-title">下一步行动 <a href="#/issues" class="card-link">查看全部 →</a></div>
          <div v-if="planError" class="err-box"><span>{{ planError }}</span></div>
          <div v-if="!todoPlans.length" class="empty-hint">
            暂无待办行动 · <a href="#/issues" class="card-link">去风险问题采纳建议</a> · <a href="#/chat" class="card-link">问 AI 顾问 →</a>
          </div>
          <div v-for="p in todoPlans" :key="p.id" class="plan-item">
            <input type="checkbox" class="plan-check" :checked="p.status === 'done'" @change="toggle(p)" />
            <div class="plan-body">
              <div class="plan-action">{{ p.action }}</div>
              <div v-if="p.detail" class="plan-detail">{{ p.detail }}</div>
            </div>
          </div>
        </section>

        <!-- 补充：家庭目标 + AI 主动洞察（深度内容，保留末位） -->
        <div class="section-grid">
          <goals-card :o="store.overview" />
          <insight-panel :o="store.overview" />
        </div>
      </template>
    </div>`,
```

> **⑤ 三入口映射**：`查看` = 标题「查看全部 →」（#/issues）；`完成` = 每个待办前的勾选框（toggle → setActionStatus）；`去顾问` = 空态「问 AI 顾问 →」（#/chat）。有行动时「去顾问」由 ④ stale 横幅的「去重新评估」与洞察面板覆盖，不额外堆按钮。

---

## 验证（对齐你定的 4 条验收）

| 验收 | 验证方式 |
|------|----------|
| ① DOM 顺序 ①→⑤ | 改后读 `overview.js` 确认 template 顺序 = kpi → report-banner → 雷达 → stale → plan-panel；再部署后浏览器截图核对 |
| ② 数据一致性（与 Issues 同源） | 代码只读 `store.actionPlan`（同一切片）、只调 `setActionStatus`（同一端点），不建第二套状态；`loadActionPlan()` 在 toggle 后重新拉取，两页实时同步 |
| ③ 空状态不空白 | 空态渲染一行 `.empty-hint`「暂无待办行动 · 去风险问题采纳建议 · 问 AI 顾问 →」，无大空白区 |
| ④ 手机可读 / 行动可见 | 部署后 375px 视口截图，确认 ① 首屏 KPI 可读、⑤ 在正常流内不被挤到不可见位置 |

### 执行验证步骤

1. **回归**：`python -m pytest -q`（预期 539 passed）＋ `node --test tests/js/`（预期 12 passed）——本改动纯前端，应全绿无波动。
2. **结构核对**：读改后 `overview.js`，肉眼 + grep 确认 5 个区块顺序与 ⑤ 空态。
3. **部署**：`python D:\Claude_Code\deploy_update.py`（SFTP 直传 + 重启 + 健康检查 `{"ok":true}`）。
4. **视觉**：webapp-testing / 浏览器 375px + 桌面视口截图，核对 ①→⑤ 顺序、空态、有数据态（勾选框）。
5. **提交**：`git commit`（消息如 `feat(p0): Overview 信息架构归位 ①→⑤ + 下一步行动入口`）。

---

## 明确不做（本次范围外，回 ui-audit 清单 P1/P2/P3）

- ❌ Goals / Retirement / Sandbox 出口（P1）
- ❌ 颜色 token 收口 / 删死代码 AllocationCard（P2）
- ❌ 宽表滚动 / kv-grid 单列 / 点击目标 ≥44px（P3）
- ❌ 导航「AI 顾问」位置（单独产品决策，不绑定）
