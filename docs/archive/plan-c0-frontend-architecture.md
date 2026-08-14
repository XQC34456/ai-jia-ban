# Plan C0 — 前端架构与数据流设计

> **状态：待评审**。通过后进入 C1（Wealth Cockpit）。
>
> 本文回答：API v1 之后，前端如何组织状态、组件、交互，才能在不复制 Engine 的前提下，
> 支撑 Cockpit → X-Ray → Sandbox → Comparison 四个视图。

---

## 0. 已定决策（本轮拍板）

| 决策 | 结论 |
|------|------|
| 前端栈 | **Vue 3 CDN（全量版，无构建）**，本地 vendor，FastAPI 继续直接服务静态文件 |
| 模块化 | 原生 **ES modules**（`<script type="module">`），无 SFC、无 node_modules、无打包 |
| 单一事实源 | **`/api/wealth/overview` 是前端唯一数据源**；前端绝不复算财富数字 |
| 计算唯一路径 | 财富数字**只在 Engine 算**；前端/Sandbox/AI 都不算第二遍 |

---

## 1. 架构总览（单一事实源）

```
                    FastAPI（后端）
  /api/wealth/overview ──────────────┐
  /api/wealth/issues                 │
  /api/wealth/goals                  ├──▶ Frontend Store（Vue reactive 单例）
  /api/wealth/scenario/{name}        │        │
  /api/wealth/scenario/{name}/compare┘        │ computed（纯展示派生）
  （compare 为 C3/C4 新增）                    ▼
                                        Views（Cockpit / X-Ray / Sandbox / Comparison）
```

**铁律**：所有财富数值（wealth_score / RFR / NWC / DTI / 流动性 / 配置适配度）只从 API 响应读，
前端任何 `computed` 只能做**格式化、排序、筛选、阈值着色**，绝不产生新的财富结论。

---

## 2. 数据流

```
组件事件 ──▶ store.action ──▶ api.js fetch ──▶ 后端 ──▶ store.state 更新 ──▶ computed ──▶ 组件自动重渲染
```

三层职责：
- **`api.js`**：唯一发 `fetch` 的地方。只做请求/鉴权头/`{detail}` 错误解析，返回原始 JSON，**零计算**。
- **`store.js`**：Vue `reactive` 单例，持状态 + 动作。组件**从不直接 fetch**。
- **组件**：只读 `store` + 派发动作，模板渲染 `computed`。

---

## 3. 目录结构（无构建 ES modules）

```
static/
├── index.html                 # 根模板：vendor vue + <script type="module" src="app.js">
├── vendor/vue.global.prod.js  # Vue 3 全量版（含 template 编译器），本地 vendor
├── app.js                     # 入口：createApp + 根组件 + 视图切换（Cockpit/X-Ray/Sandbox/Comparison）
├── api.js                     # fetch 封装（唯一发请求处）
├── store.js                   # reactive store + actions
├── components/
│   ├── cockpit/               # HealthScoreCard / NetWorthCard / CashflowCard /
│   │                          #   AllocationCard / RetirementCard / DebtCard / GoalsCard / TopIssuesCard
│   ├── xray/                  # AllocationDeviation / Concentration / Liquidity / AdjustmentActions
│   ├── sandbox/               # ScenarioSelector / ParamSlider / BeforeAfterPanel / AiExplanation
│   └── comparison/            # ComparisonTable / OptionColumn / Verdict
└── style.css
```

> Vue 全量版（`vue.global.prod.js`）内置 template 编译器，组件可用 `template:` 字符串；
> 无需 `.vue` 单文件组件、无需预编译。

---

## 4. 状态管理（`store.js`）

```js
const { reactive, computed } = Vue;

export const store = reactive({
  auth: { token: null, username: '', tier: 'free' },

  // ★ 单一事实源：全量驾驶舱状态（/api/wealth/overview）
  overview: null,

  // 沙盘局部状态（C3）
  sandbox: { scenario: 'invest', params: {}, result: null, loading: false, error: null },

  // 方案比较（C4）
  comparison: { options: [], data: null, loading: false },
});

// 派生只做「展示」，不做财富计算：
export const topIssues = computed(() => (store.overview?.issues ?? []).slice(0, 3));
export const cashflowHealthy = computed(() => (store.overview?.cashflow?.surplus ?? 0) >= 0);

export async function loadOverview() { store.overview = await api('/api/wealth/overview'); }
export async function runScenario(name, params) { /* 见 §6 */ }
```

---

## 5. 组件结构（按视图）

### C1 Cockpit（100% 消费 overview，无任何计算）
```
CockpitView
├── HealthScoreCard     wealth_score + wealth_level（仪表/大数字）
├── NetWorthCard        net_worth = total_assets - total_liabilities（直接读三个字段，前端只做展示）
├── CashflowCard        cashflow.income/expense/surplus/savings_rate
├── AllocationCard      六大类占比（asset_allocation.classes）环形图 + allocation_target 对照
├── RetirementCard      retirement.rfr/nwc/quadrant + known_limitations（如实标注）
├── DebtCard            debt.total_debt/monthly_payment/dti
├── GoalsCard           goals[]（GoalOut）
└── TopIssuesCard       priorities 前 3，可点击 → 跳 X-Ray / Sandbox
```

### C2 X-Ray（读 overview 的配置相关块，仍无计算）
```
XRayView
├── AllocationDeviation   当前 classes vs allocation_target 点目标 → 每类偏离（超配/低配）
├── Concentration         集中度（real_estate_pct / other_pct）
├── Liquidity             流动性（liquidity.emergency_months + 安全线阈值着色）
├── Protection            保障（protection）
└── AdjustmentActions     「调整我的资产配置」→ 携带目标参数跳转 Sandbox（scenario=invest）
```

### C3 Sandbox（交互式，左右对比 + 滑杆）
```
SandboxView
├── ScenarioSelector       buy_house / prepay / invest / income_change
├── ParamSlider            滑杆（房价/投入额/还贷额…），防抖 300ms
├── BeforeAfterPanel       「现在 vs 调整后」两列指标
└── AiExplanation          系统/AI 生成结论（数字来自 API，见 §8）
```

### C4 Comparison（多方案对比表 + 综合判断）
```
ComparisonView
├── OptionColumn           A/B/C 方案（保持现状 = baseline）
├── ComparisonTable        九维度：财富评分/净资产/现金流/流动性/DTI/RFR/NWC/配置/目标影响
└── Verdict                综合判断（模板或 AI，见 §8）
```

---

## 6. 交互协议（关键：**绝不复制 Engine 逻辑**）

### 普通视图
登录成功 → `loadOverview()` → 所有卡片从 `store.overview` 渲染。数据变更后重新 `loadOverview()`。

### Sandbox 滑杆（C3）
```
用户拖滑杆
  → store.sandbox.params 更新（本地，仅 UI 状态）
  → debounce 300ms
  → runScenario(name, params)
  → POST /api/wealth/scenario/{name}  body: {"params": {...}}
  → store.sandbox.result = 响应（impacts/rows）
  → BeforeAfterPanel 重渲染
```

**「调整后」数字的两种来源（必须区分，否则就会复制 Engine）：**

| 指标 | 当前 scenario 接口是否已给 | C3 如何处理 |
|------|--------------------------|-------------|
| 净资产 / 现金流 / 流动性 / DTI / 负债率 | ✅ `impacts` 已含增量 | 前端 `baseline + delta` **展示拼接**（无计算） |
| **财富评分 / RFR / NWC（全局重算）** | ❌ 单次接口只给增量，不给重算 | 需 §7 的 **apply 原语**，C3 后半段实现 |

> 规则：前端可以 `baseline + delta`（两个都是 API 给的数）拼出展示值，但**绝不能用前端代码复现 RFR/NWC 的计算公式**。

---

## 7. Scenario State → Projection State（最小 Engine 原语，C3/C4 实现）

这是 Plan C 唯一的 Engine Extension，**最小原语、非重写模型**。

### 7.1 原语签名
```python
# app/engine/scenario.py（新增一个返回副产物，不改现有计算逻辑）
def apply_scenario(data: dict, name: str, params: dict) -> dict:
    """返回「应用情景后的家庭数据副本」modified_data。

    simulate_* 内部本就知道情景如何改变资产/负债/现金流，
    这里只把改变后的数据作为副产物返回，不重算任何数字。
    """
```

### 7.2 投影（重算，复用既有 build_overview，非复制）
```python
# app/services/scenario.py（编排层，C3/C4 新增）
def compare_scenarios(data, name, options):
    baseline = build_overview(data)                      # 现状
    results = []
    for opt in options:
        modified = scenario.apply_scenario(data, name, opt["params"])
        results.append({"id": opt["id"], "name": opt["name"],
                        "overview": build_overview(modified)})   # 完整重算
    return {"scenario": name, "baseline": baseline, "options": results}
```

### 7.3 端点
```
POST /api/wealth/scenario/{name}/compare   (VIP)
body: { "options": [ {"id":"A","params":{...}}, {"id":"B","params":{...}} ] }
```
返回 §8 冻结契约里的 `baseline + options[] + comparison{}` 结构。

### 7.4 为什么这是「最小原语」而非「重写」
- 每条情景的 `simulate_*` **已经算过** before/after，只需多返回一个 `modified_data`（数据补丁）。
- 重算全局指标复用**已存在**的 `build_overview`，**不新增任何财富公式**。
- 计算路径仍只有一条：`Engine.apply → build_overview`，前端/Service 不复制。

---

## 8. AI 集成原则（AI 不负责算钱）

```
用户 → AI（理解/识别问题）→ 调用 Wealth API → Engine → Decision Layer → Scenario
    → 结构化结果 → AI 解释 → 用户行动
```

- AI 收到的永远是 **API 返回的结构化 JSON**（Overview / Issue / comparison）。
- AI 只负责：**理解人、调用接口、解释结果、推动决策**。
- AI **绝不**凭经验产出财务数字；数字只能来自 Engine。
- Sandbox/Comparison 的「结论文案」两种实现：
  - **确定性模板**（规则）：根据 comparison 的 delta 区间套话术（可离线、可测试）。
  - **AI 解释**（可选增强）：把 comparison JSON 喂给 AI，由 AI 组织语言，**数字仍来自 JSON**。

> 此原则写入项目根 `ARCHITECTURE.md`，作为长期铁律。

---

## 9. C1–C4 依赖与实施顺序

```
C0 设计（本文）─────────────── 本轮
  ↓ 通过
C1 Cockpit     依赖 overview（已就绪，零后端改动）
  ↓
C2 X-Ray       依赖 overview 配置块（已就绪，零后端改动）
  ↓
C3 Sandbox     依赖 scenario 单次接口（已就绪）→ 后半段加 §7 apply 原语
  ↓
C4 Comparison  依赖 §7 compare 端点 + apply 原语
```

- **C1/C2 零后端改动**，纯前端，可立即开工。
- **C3 前半段**（现金流/流动性/DTI 的左右对比）用现接口即可；**C3 后半段 + C4** 需要 §7 原语。

---

## 10. 风险与边界

| 风险 | 对策 |
|------|------|
| 前端偷偷复算财富 → 数字不一致 | 契约测试 + 组件只能读 store.overview，评审盯「computed 是否产生财富结论」 |
| 无构建的 Vue 组件膨胀 | 按视图拆分 ES module；C1 只做 Cockpit，不一次写完四视图 |
| CDN 依赖网络 | **本地 vendor** Vue 文件，离线可用 |
| 旧 vanilla 前端共存 | 新视图独立挂载，旧 MVP 界面保留到 Cockpit 稳定后再切 |
