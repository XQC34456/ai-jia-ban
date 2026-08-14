# C5 统一 App Shell · 实施计划

> 依赖 spec：[plan-c5-unified-app-shell.md](plan-c5-unified-app-shell.md)
> 约束：仅前端/UI 层；不改 A1~A4 / Wealth Engine / Decision / API Schema / Agent Runtime；
> 保持 API 返回契约不变；Store 模块化（不把所有数据塞进 overview）；AI 洞察用确定性 build_issues 不扩大 LLM；
> 旧页面在所有迁移完成 + 回归通过后才退役。

## 验证基线（每个 Phase 完成后执行）

1. `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m pytest -q` → **全绿**（当前 237）
2. 浏览器人工冒烟：该 Phase 涉及视图可导航、登录态正常、数据渲染、VIP 门、错误兜底
3. `git commit`（每 Phase 一次）

## Phase 0 — 建立 App Shell（地基）

**Files：**
- 改 `static/index.html` — 唯一壳：`<div id="app">` + vendor vue + `<script type="module" src="shell.js">`
- 建 `static/router.js` — 依赖-free hash 路由（`#/overview`…），视图注册表 + `navigate` + `currentRoute`
- 建 `static/shell.js` — 壳入口：`createApp`，根组件（Topbar + Sidebar + `<component :is>` + 登录门）
- 改 `static/store.js` — 模块化切片（auth/overview/goals/issues/sandbox/chat），统一 `token` key，保留旧导出以兼容未迁移的 cockpit/sandbox/xray
- 建 `static/views/index.js` — 8 视图占位注册（先渲染「建设中」）
- 改 `static/style.css` — 统一 design tokens（§5 三轴）+ shell 布局 + Sidebar/Topbar 样式

**验收：** 启动后登录 → 左侧 8 项可切换、当前项高亮、面包屑变化、登录态统一（跳转不掉登录）；`pytest -q` 全绿。

## Phase 1 — 迁移 cockpit → overview / allocation / retirement

**Files：** 建 `static/views/overview.js`（含 allocation/retirement 子区块，或拆三视图）
- 迁移 `cockpit.js` 的 `template`/逻辑到视图组件，读 `store.overview`
- 在 `views/index.js` 注册 3 个路由；overview 加「AI 家办顾问主动洞察」（确定性 build_issues，P0 优先）

**验收：** 总览 KPI（净资产/健康度）+ 资产配置 + 退休规划渲染正确；洞察引用真实 issue；`pytest -q` 全绿。

## Phase 2 — 迁移 xray → health

**Files：** 建 `static/views/health.js`，迁移 `xray.js`，注册 `#/health`。

**验收：** 体检视图（配置偏离/集中度/流动性/保障）正常；`pytest -q` 全绿。

## Phase 3 — 迁移 sandbox → sandbox

**Files：** 建 `static/views/sandbox.js`，迁移 `sandbox.js`（情景选择/参数/前后对比/compare），注册 `#/sandbox`。

**验收：** 沙盘情景对比（VIP 门、9 指标顺序）正常；`pytest -q` 全绿。

## Phase 4 — 迁移 vanilla app.js → chat / goals / issues / decision / report

**Files：** 建 `static/views/chat.js`（对话+决策+报告）+ `static/views/goals.js` + `static/views/issues.js`
- 把 `app.js` 原生逻辑 Vue 化，改走 `store` + `api.js`，删 `aijiaban_token` 读写
- goals 用 `/api/wealth/goals`、issues 用 `/api/wealth/issues`（独立切片 lazy load）

**验收：** 对话建档、决策模拟、报告导出、目标/问题列表在壳内正常；登录态统一；`pytest -q` 全绿。

## Phase 5 — 退役旧页面 + 清理

**Files：** 删 `static/cockpit.html/js/css`、`static/sandbox.html/js/css`、`static/xray.html/js/css`、`static/app.js`
- 确认 8 视图全在壳内可用后删除；更新 `README.md` 前端入口说明

**验收：** 删除后全量 `pytest -q` 全绿 + 8 视图人工走查全通。

---

## 铁律（每阶段自查）

- [ ] 未改任何 `.py`（`git status` 只看 `static/` + `docs/`）
- [ ] Store 切片分离，数据不硬塞 overview
- [ ] 组件 `computed` 只做格式化/着色，不产财富结论
- [ ] 图标用 SVG，不用 emoji（品牌 🏠 除外）
- [ ] 对比度 / focus / 44px 目标可达性达标
