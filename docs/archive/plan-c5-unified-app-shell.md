# Plan C5 — 统一 App Shell（专业财富管理 × 家庭温度）

> **状态：待评审**。通过后进入实施计划（writing-plans）。
>
> 本文回答：如何把当前「原生 JS 首页 + 3 个独立 Vue 子页」收敛为**一个 Vue 应用壳**
> （Sidebar + Topbar + Main + 视图路由），在**不改后端/API/Agent/Engine** 的前提下，
> 落地「成熟 AI 办公平台」的布局，同时保留「家庭温度」品牌记忆点。
>
> 前置文档：`plan-c0-frontend-architecture.md`（Vue 3 CDN + ES modules + 单一事实源）。

---

## 0. 现状问题（为什么做）

| # | 问题 | 影响 |
|---|------|------|
| P1 | 两套前端栈并存：`index.html+app.js`（原生 JS）vs `cockpit/sandbox/xray`（Vue 3） | 结构割裂，导航靠跳页 |
| P2 | 认证 key 不统一：原生用 `localStorage['aijiaban_token']`，Vue 用 `localStorage['token']` | 首页登录后跳驾驶舱掉登录 |
| P3 | 4 个独立 `.html` 页面，无统一壳/侧边栏 | 不像成熟办公平台，信息层级弱 |
| P4 | 视觉是「奶油暖白」工具感不足 | 不够「专业财富管理」 |

---

## 1. 已定决策（用户拍板，不可改）

| 决策 | 结论 |
|------|------|
| 落地方式 | **统一单页壳 + 渐进式迁移**：先建壳，业务页面不推倒，逐个迁移，每步可回归 |
| 视觉方向 | **专业财富管理 × 家庭温度**；不做纯 ChatGPT/Linear 暗色风 |
| 布局 | Sidebar（8 项）+ Topbar（面包屑）+ Main（视图容器）+ hash 路由 |
| 总览页 AI 洞察 | **确定性规则**从 `build_issues` 取最高优先级问题生成，**不接 LLM、不扩大 LLM 权限** |
| 红线 | 后端 / API / Agent / 财富 Engine / 数据库 / **A1~A4 / Decision / API Schema / Agent Runtime 一律不动** |
| Store 结构 | **模块化**：`auth / overview / goals / issues / sandbox / chat` 独立切片，各自 lazy load，**不把所有数据塞进 overview** |
| 依赖 | 不引入构建工具、不引入 vue-router/pinia 等新依赖 |

---

## 2. 架构总览

```
                FastAPI（后端，零改动）
   /api/wealth/overview ────┐
   /api/wealth/issues        │
   /api/wealth/goals         ├──▶ store.js（Vue reactive 单例 + 统一认证）
   /api/wealth/scenario/*    │         │
   /api/agent/chat / chat 等 │         │ computed（纯展示派生）
                             │         ▼
   index.html（唯一壳）─ shell.js（createApp + Sidebar + Topbar + 视图路由）
                             │
                             ▼
        8 个视图：overview / health / allocation / retirement / goals /
                  issues / sandbox / chat
```

**铁律（沿用 C0）**：所有财富数值只从 API 响应读；前端 `computed` 只做格式化/排序/筛选/阈值着色，
**绝不复算财富数字**。AI 洞察只引用 `build_issues` 已产出的问题，不新生成结论。

---

## 3. 壳结构

```
index.html
├─ Topbar
│   ├─ 左：品牌 logo（🏠 渐变琥珀）+「AI 家办」+ 面包屑「首页 / <当前视图>」
│   └─ 右：用户区（用户名 + VIP/免费标签 + 升级 + 退出）+ AI 引擎徽章
├─ Sidebar（左侧固定宽，8 项）
│   家庭总览 · 财富健康 · 资产配置 · 退休规划 · 家庭目标 · 风险问题 · 情景沙盘 · AI 顾问
│   （SVG 线性图标 + 文字，当前项高亮 + 左侧 3px 品牌色指示条）
└─ Main（滚动容器）
    └─ 视图容器（hash 切换渲染）
```

- 路由：自写 **hash 路由**（`#/overview`、`#/health`…），监听 `hashchange`，视图注册表映射
  `hash → Vue 组件`。无 vue-router。
- 认证门：未登录 → 整壳替换为登录卡片（复用现有登录/注册逻辑，改为 Vue 化）。

---

## 4. 8 视图 → 功能 / 数据源映射

| 侧边栏 | 路由 | 数据源 | 来源 |
|--------|------|--------|------|
| 家庭总览 | `#/overview` | `store.overview` + `build_issues`（经 `/api/wealth/issues`） | **新做** landing：净资产+财富健康度 KPI、资产配置卡、退休规划卡、AI 顾问主动洞察 |
| 财富健康 | `#/health` | `store.overview` 配置块 | 迁移 `xray.js` |
| 资产配置 | `#/allocation` | `store.overview.asset_allocation` | 从 cockpit 拆出 donut + 明细 |
| 退休规划 | `#/retirement` | `store.overview.retirement` | 从 cockpit 拆出四象限 + 预测 |
| 家庭目标 | `#/goals` | `/api/wealth/goals` | 从 cockpit/旧看板拆出目标测算 |
| 风险问题 | `#/issues` | `/api/wealth/issues` | 迁移旧看板问题列表 |
| 情景沙盘 | `#/sandbox` | `/api/wealth/scenario/*` | 迁移 `sandbox.js` |
| AI 顾问 | `#/chat` | `/api/chat` + `/api/agent/chat` | 迁移 `app.js` 对话 + 决策 + 报告 |

> 说明：`overview/health/allocation/retirement` 四个视图都读同一份 `store.overview`
> （单一事实源），只是渲染不同子区块——**不是四份数据，是四个视角**。

---

## 5. 视觉系统 tokens（专业 × 温度）

来源：`ui-ux-pro-max`（finance/wealth → primary #2563EB + accent #D97706）与现有暖色品牌取交集。

```css
:root {
  /* 中性暖底（专业：比奶油更中性，保留暖调） */
  --bg:         #F7F6F3;   /* 暖灰白底 */
  --bg-soft:    #EFECE6;   /* 侧栏/输入框浅底 */
  --card:       #FFFFFF;
  --text:       #23201D;   /* 深暖墨 */
  --muted:      #6B6560;   /* 暖灰次要 */
  --line:       #E7E2DA;   /* 暖边框 */
  --line-strong:#D8D1C6;

  /* 品牌（家庭温度记忆点，保留琥珀橙） */
  --brand:      #D97706;
  --brand-dark: #B45309;
  --brand-soft: #FEF3E2;
  --brand-line: #F2DDB8;

  /* 数据色（金融信任 / 信息 / 告警） */
  --positive:   #059669;   /* 正向 */
  --positive-soft:#ECFDF5;
  --info:       #2563EB;   /* 图表数据色，非主色 */
  --warn:       #DC2626;
  --warn-soft:  #FEF2F2;

  /* 阴影 / 圆角 / 间距（更克制、更工具化） */
  --shadow-sm: 0 1px 2px rgba(30,26,22,.04);
  --shadow-md: 0 1px 3px rgba(30,26,22,.06), 0 8px 24px rgba(30,26,22,.06);
  --shadow-lg: 0 16px 48px rgba(30,26,22,.12);
  --radius-sm: 6px;  --radius: 10px;  --radius-lg: 14px;
}
```

- **字体**：沿用系统中文栈 `-apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI"` +
  `font-variant-numeric: tabular-nums`（数字对齐）。不引入 Google Fonts（保持离线可用）。
- **图标**：SVG 线性图标（Lucide 风格路径），**不用 emoji 当图标**（品牌 logo 的 🏠 除外）。
- **可达性**：文字对比 ≥ 4.5:1、focus ring 3px、点击目标 ≥ 44×44、尊重 `prefers-reduced-motion`。
- 具体色值在实施时以本节为基线微调，不偏离「琥珀品牌 + 暖中性底 + 青绿正反馈」三轴。

---

## 6. 认证统一（修复 P2）

- `store.js` 统一为**单一 key `token`**；`applySession` / `logout` 只读写 `token`。
- 迁移后的 `chat` 视图（原 vanilla）改用同一 `store`，删除 `aijiaban_token` 读写。
- 结果：登录一次，全局 8 视图共享会话；跳驾驶舱不再掉登录。

---

## 7. AI 家办顾问「主动洞察」（总览页，无 LLM）

- 数据源：`GET /api/wealth/issues`（确定性规则 `build_issues` 输出，含 severity/优先级）。
- 渲染：取**最高优先级问题**（P0 优先）的第一条，套确定性话术模板：
  `「我发现你的<资产配置/现金流/退休…>有一个值得关注的问题：<title>。建议：<recommendation>」`
- 点击 → 跳转对应视图（如 `#/issues` 或 `#/allocation`）。
- **不接 LLM、不新生成财务结论**（守住「AI 不算钱、洞察不编造」）。后续若要 LLM 润色，
  也只在「引用既有 Issue」的框架内做文案组织，数字仍来自 API。

---

## 8. 渐进式迁移（每阶段可回归）

| 阶段 | 内容 | 完成后回归 |
|------|------|-----------|
| **Phase 0** | 建壳：`index.html` + `shell.js`（Sidebar/Topbar/路由）+ `style.css` tokens + 统一认证；8 视图先挂占位「建设中」 | 壳可导航、登录态统一、`pytest -q` 全绿 |
| **Phase 1** | 迁移 `cockpit.js` → `overview`（+拆 `allocation`/`retirement`） | 驾驶舱数据在壳内正常渲染 |
| **Phase 2** | 迁移 `xray.js` → `health` | 体检视图正常 |
| **Phase 3** | 迁移 `sandbox.js` → `sandbox` | 沙盘情景对比正常 |
| **Phase 4** | 迁移 `app.js`（vanilla）→ `chat`（+`goals`/`issues`/`decision`/`report`） | 对话+决策+报告正常 |
| **Phase 5** | 退役旧 `cockpit.html/sandbox.html/xray.html/app.js`，清理冗余 CSS | 全量回归 + 人工走查 |

- 每阶段迁移一个视图 → 手动 + `tests/test_frontend_contract.py` 等回归 → 提交。
- 「业务页面不推倒」：迁移是把现有 JS 的 `template`/逻辑搬进视图组件，**不改其业务逻辑**。

---

## 9. 数据流与铁律（模块化 Store）

```
组件事件 → store.<slice>.action → api.js fetch → 后端 → store.<slice> 更新 → computed → 组件重渲染
```

**Store 模块化（不把所有数据塞进 overview）：**

| 切片 | 数据 | 数据源 | 何时加载 |
|------|------|--------|----------|
| `auth` | token / username / tier | 登录/注册 | 启动 |
| `overview` | 驾驶舱核心（wealth_score / net_worth / allocation / retirement / cashflow） | `/api/wealth/overview` | 进入总览/资产/退休时 lazy load |
| `goals` | 目标列表 + 测算 | `/api/wealth/goals` | 进入「家庭目标」时 lazy load |
| `issues` | 问题/告警/优先级/建议 | `/api/wealth/issues` | 进入「风险问题」或总览洞察时 lazy load |
| `sandbox` | 情景 + 参数 + 结果 + 对比 | `/api/wealth/scenario/*` | 进入「情景沙盘」时 |
| `chat` | 对话消息 / 决策 / 报告 | `/api/chat`（+ 决策/报告端点） | 进入「AI 顾问」时 |

- `api.js`：唯一 `fetch` 处，零计算（已满足）。
- `store.js`：`reactive` 单例，**按切片组织**，每切片独立 `loading/error/data` + action；组件从不直接 fetch。
- 组件：只读 store + 派发动作，模板渲染 computed。**computed 只做格式化/排序/筛选/阈值着色，绝不产财富结论。**

---

## 10. 测试与验收

- **自动化**：现有 `tests/test_frontend_contract.py`（前端契约）+ 全量 `pytest -q` 必须保持全绿。
- **前端回归**：迁移每阶段后，人工走查该视图（登录态 / 数据渲染 / VIP 门 / 错误兜底）。
- **视觉验收**：`visual_review` 或浏览器截图，核对「专业 + 温度」三轴（琥珀品牌、暖中性底、青绿正反馈）。
- **可达性**：对比度 / focus / 键盘导航 / 44px 目标自查。

---

## 11. 非目标（红线）

- 不改后端、API、Agent、财富 Engine、数据库、任何 `.py`。
- 不引入构建工具（vite/webpack）、不引入 vue-router/pinia 等新依赖。
- 不改变任何 API 契约、不改变任何财富计算路径。

---

## 12. 风险与边界

| 风险 | 对策 |
|------|------|
| 迁移中破坏现有 Vue 视图 | 渐进式 + 每阶段回归；旧文件保留到该视图稳定后再删 |
| 前端偷偷复算财富 | 沿用「组件只读 store.overview」+ 契约测试盯「computed 是否产结论」 |
| 无构建下组件膨胀 | 每视图一个 ES module，按 C0 目录组织，不做巨型单文件 |
| 图标/字体依赖网络 | SVG 内联 + 系统字体栈，离线可用 |
| 两套 token 残留 | 迁移完成后删旧 CSS，只保留统一 `style.css` |
