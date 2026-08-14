# AI家办 V2 — 设计文档（F~O）

> 配套：`docs/v2-audit.md`（A~E 现状审计）。
> 设计原则（源自总方案 + 审计）：**不推翻现有** · **数字确定性计算，LLM 只做理解/解释** · **先完整闭环再扩展** · **区间导向、可追溯、可复算、可审计**。

---

## F. V2 新增数据模型

> 原则：在现有 8 表上**加列 / 加表**，不删列不改语义，旧数据默认值兜底，旧功能不破坏。

### F1. 扩展 `asset`（支撑资产配置分析 + Portfolio X-Ray）

新增列（`ALTER TABLE ADD COLUMN`，均可空）：

| 列 | 类型 | 说明 |
|---|---|---|
| `asset_class` | TEXT | 大类（**可扩展枚举**，非写死常量）：`cash` / `fixed_income` / `equity` / `real_estate` / `alternative` / `other` |
| `liquidity` | TEXT | `liquid` 流动 / `illiquid` 非流动（可为空，由 asset_class 兜底推断） |
| `cost_basis` | REAL | 成本（Portfolio X-Ray 收益/重叠用） |
| `expected_return` | REAL | 预期年化（%小数，用户填或默认） |
| `risk_level` | TEXT | `low` / `medium` / `high` |
| `sub_type` | TEXT | 子类标签（行业/地区/主题，Portfolio X-Ray 用，如「新能源」「美股」） |

迁移时按现有 `type` 回填 `asset_class`：`房产→real_estate`、`存款→cash`、`理财→fixed_income`、`基金→fixed_income`（默认，可改 equity）、`股票→equity`、`保险现金价值→other`、`其他→other`。B 端机构可扩展新分类。

### F2. 扩展 `goal`（支撑现金流型目标规划）

新增列：

| 列 | 类型 | 说明 |
|---|---|---|
| `goal_kind` | TEXT | `lump_sum` 一次性（默认，旧数据全归此）/ `cashflow` 现金流型 |
| `annual_amount` | REAL | 现金流型：每年/每月需多少（教育金=每年学费，养老金=每年支出） |
| `duration_years` | INTEGER | 现金流型：持续年限 |
| `start_year` | INTEGER | 现金流型：起始年（如孩子 18 岁那年） |
| `priority` | INTEGER | 优先级 1~3（默认 2） |
| `risk_tolerance` | TEXT | 允许波动 `conservative/balanced/aggressive`（默认 balanced） |

一次性目标仍用 `target_amount + target_date`；现金流型用 `annual_amount + duration_years + start_year`。

### F3. 新增 `insurance` 表（保险，独立实体）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` / `family_id` / `person_id` | — | 主键/归属/被保人 |
| `type` | TEXT | 寿险/重疾/医疗/意外/年金/其他 |
| `name` | TEXT | 保单名 |
| `annual_premium` | REAL | 年保费 |
| `coverage` | REAL | 保额 |
| `cash_value` | REAL | 现金价值（可选，供资产快照） |
| `start_date` / `maturity_date` | TEXT | 生效/到期 |

> 保单现金价值可选并入 `asset` 视图，但保障属性（保额/保费）独立存，供「保障维度」评分。

**⚠️ 保险定位**：保险是「家庭风险保障 / 风险转移」，**不作为投资资产处理**——不进入「权益/固收/现金」占比，不与股票/基金/现金做同维度收益率比较。它在 Wealth Engine 中只承担两个角色：(1) `score` 的「保障维度」打分（保额/保费覆盖率）；(2) 保障分析（风险缺口，如「重疾保额不足」）。

### F4. 新增 `family_profile` 表（家庭画像，1:1 family）

| 列 | 类型 | 说明 |
|---|---|---|
| `family_id` | INTEGER | 唯一 |
| `risk_profile` | TEXT | `conservative/balanced/aggressive` 风险承受（默认 balanced，可由问卷得出） |
| `investment_horizon` | INTEGER | 投资期限（年，默认 10） |
| `risk_answers` | TEXT | 风险测评问卷答案 JSON（可空，P1 问卷用） |

### F5. 新增 `scenario_snapshot` 表（情景快照，验收「参数可追溯」）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` / `family_id` | — | |
| `scenario` | TEXT | 场景类型 |
| `params_json` | TEXT | 入参快照 |
| `result_json` | TEXT | 结果快照 |
| `created_at` | TEXT | |

### F6. `reminder` 表（复用，V2 真正落地）

现有表不动。AI 主动管家写入、驾驶舱读取。P1 实现。

> **暂缓**：`event` 独立表。方案数据层列了「事件」，但「事件型目标」已由 `goal(goal_kind=cashflow)` 承载，独立 event 表放到 P1 避免过度设计。

---

## G. Wealth Engine 设计（V2 核心资产）

> 原则：**模块化纯函数**，零外部依赖、可单测、可审计。在 `calc_engine.py` 基础上拆分子模块（不推翻，原函数保留为兼容层）。

```
app/engine/
  __init__.py
  metrics.py      # 基础指标（现 calc_engine 迁移：总资产/负债/净资产/现金流/储蓄率/应急/负债率）
  allocation.py   # 资产配置分析：大类占比、集中度、流动性、目标区间、偏离、调整
  goals.py        # 目标规划：现金流型目标测算、缺口、每月定投、可行性
  score.py        # Family Wealth Score：七维度加权、可解释
  projection.py   # 长期财富投影：教育金终值、退休规划
  scenario.py     # 情景引擎（见 H）
```

### G1. 资产配置分析 `allocation.analyze(assets, goals, profile)`

输出结构（**区间导向，禁伪精确单点**）：

```jsonc
{
  "current": { "cash": 0.10, "fixed_income": 0.15, "equity": 0.05, "property": 0.70, "other": 0.0 },
  "concentration": {
    "hhi": 0.52,                 // 赫芬达尔指数（越接近 1 越集中）
    "top_asset_pct": 0.70,       // 最大单一资产占比
    "property_pct": 0.70,        // 房产占比
    "single_stock_pct": 0.0
  },
  "liquidity": {
    "liquid_amount": 250000,
    "liquid_pct": 0.10,
    "emergency_coverage_months": 4.2
  },
  "target_range": {               // 由 Allocation Policy 动态产出（见下）
    "cash": [0.05, 0.15],
    "fixed_income": [0.15, 0.35],
    "equity": [0.10, 0.40],
    "property": [0.40, 0.70]
  },
  "deviation": [                  // 每个大类 current vs target_range
    { "class": "equity", "current": 0.05, "range": [0.10, 0.40], "status": "below" }
  ],
  "adjustments": [                // 调整优先级（可执行行动）
    { "priority": 1, "action": "降低房产占比 / 增配金融资产", "reason": "房产占比 70% 过高，流动性弱" }
  ],
  "risk": { "concentration_risk": "high", "liquidity_risk": "high" }
}
```

**目标区间 = Allocation Policy 产出（不硬编码，可配置）**

配置区间不是写死的常量，而是由 **Allocation Policy 引擎**根据多维因子动态产出：

```
输入因子 → Allocation Policy → 目标区间（Target Range）
  · Risk Profile       风险承受
  · Goal               目标类型 + 期限
  · Time Horizon       投资期限
  · Liquidity Requirement  流动性需求
  · Family Stage       家庭阶段（积累期/子女教育期/退休期）
```

Policy 本身是**可配置的数据结构**（默认策略 + 可覆盖），核心逻辑仍用「资金分层」：

| 资金分层 | 来源 | 默认配置倾向 |
|---|---|---|
| 安全钱 | 应急金 + 未来 1~2 年刚性支出 | `cash` + 短 `fixed_income` 为主 |
| 稳定钱 | 教育/买房/中期目标/养老基础 | `fixed_income` + 部分 `equity` |
| 增长钱 | 长期财富增长/退休 | `equity` + `alternative` 为主 |

默认策略再叠加因子修正（如 `risk_profile=conservative` 权益上限 −10pt，`aggressive` +10pt；`liquidity_requirement` 高则 `cash` 下限抬高）。**未来 B 端机构可注入自己的 Policy 覆盖默认策略**——这是竞标级能力的落点。

### G2. 目标规划 `goals.plan_cashflow_goal(...)`

现金流型目标测算（教育金/养老金核心公式，纯函数）：

```python
def plan_cashflow_goal(annual_amount, duration_years, years_until_start,
                       current_saved=0, inflation=0.03, return_rate=0.03):
    # 1) 目标总需求（届时名义值）= A × N × (1+i)^Y
    fv_target = annual_amount * duration_years * (1 + inflation) ** years_until_start
    # 2) 已备终值 = S × (1+r)^Y
    fv_saved = current_saved * (1 + return_rate) ** years_until_start
    gap = max(fv_target - fv_saved, 0)
    # 3) 每月定投 = 缺口 × (r/12) / ((1+r/12)^(Y×12) - 1)
    n = years_until_start * 12
    monthly = gap * (return_rate/12) / ((1 + return_rate/12) ** n - 1) if n > 0 else gap
    return { "fv_target": fv_target, "gap": gap, "monthly_save": monthly,
             "allocation": allocation_recommendation(years_until_start) }
```

**配置建议 = 同上 Allocation Policy 的「目标维度」默认实现**

`allocation_recommendation(years_until_need)` 是 Policy 的默认落地，未来同样可被 B 端策略覆盖：

| 距用钱 | 稳健（现金/固收） | 进取（权益） |
|---|---|---|
| ≤ 3 年 | ≥ 80% | ≤ 20% |
| 3~7 年 | 60% | 40% |
| \> 7 年 | 30% | 70% |

### G3. Family Wealth Score `score.wealth_score(family_data)`

方案第六节七维度，**权重可配置**（放常量表，非硬编码散落）：

| 维度 | 权重 | 打分依据（0-100，每项可解释加减分） |
|---|---|---|
| 现金流 | 20% | 储蓄率、结余是否为正 |
| 流动性 | 15% | 应急月数（≥6 满分）、流动占比 |
| 负债 | 15% | 负债率 DTI（≤30% 满分） |
| 保障 | 15% | 保险覆盖（保额/保费缺口，无保险则低分） |
| 资产配置 | 15% | 集中度、大类偏离度 |
| 财富目标 | 10% | 目标完成度、缺口 |
| 养老准备 | 10% | 养老金测算缺口 |

输出：`{ score: 0-100, level, dimensions: [{name, weight, score, reasons[]}] }`。
**可解释**：每个维度带 `reasons`（加分/扣分来源），驾驶舱点总分展开明细。
现有 `safety_margin` 保留为「安全边际」兼容指标（融入现金流/流动性/负债三维的简化版）。

---

## H. Scenario Engine 设计

> 把 `decision.py` 的硬编码两场景，重构成**通用情景框架**。

### H1. 核心抽象

**情景 = 对家庭数据做假设性修改 → 重算 wealth snapshot → 对比 baseline**。

```python
def simulate(data, snap, scenario, params) -> dict:
    # 1) 施加假设（场景函数自定义）
    # 2) 重算 snapshot
    # 3) 输出统一结果 schema
    return {
      "scenario": scenario, "title": "…",
      "plan_a_label": "现状", "plan_b_label": "…",
      "summary": [{"label","value","money"}],
      "rows": [{"label","a","b","money","months","highlight"}],
      "projection": {"years": [...], "net_worth_a": [...], "net_worth_b": [...]},  # 长期投影（沙盘折线图）
      "conclusion": "…",
      "params_snapshot": params,   # 可追溯
    }
```

场景注册表 `SCENARIOS = { "buy_house": fn, "prepay": fn, "invest": fn, "income_change": fn, … }`。

### H2. P0 场景

| 场景 | 参数 | 说明 |
|---|---|---|
| `buy_house` | price/down_ratio/loan_rate/loan_years/house_growth/horizon | 迁移现有，加 `projection` |
| `prepay` | prepay_amount/method | 迁移现有，加 `projection` |
| `invest` | amount/from_liquid/to_class(equity|fixed_income) | 拿 N 万投资，重算配置与风险 |
| `income_change` | pct_change | 收入 ±X%，看现金流/目标影响 |

### H3. P1 场景（压力测试）

`stress_test(type)`：`income_down_30`、`unemployment_12m`、`equity_down_30`、`house_down_20`、`medical_expense`、`child_study_abroad`、`early_retire`。输出「安全边际变化 + 受影响目标 + 现金流缺口 + 缓冲资金 + 调整方向」。
Monte Carlo（长期财富分布）在 P1 用 `projection` + 随机收益路径实现，图表用 ECharts 分布。

### H4. 与 AI 的关系

场景**计算**全部在 `scenario.py` 纯函数；AI 只负责**解读结果**（见 I）。

---

## I. AI Agent / Tool 架构

> 方案列 7 个 Agent。落地策略：**不引入多 Agent 框架，用「单编排器 + 工具注册表（function calling）」实现 Agent 能力**——这正是现有 `LLMExtractor` 已用的机制，轻量、不推翻。

### I1. 工具注册表（Wealth Engine 能力 → LLM 可调用 tool）

| tool | 后端函数 | 说明 |
|---|---|---|
| `get_wealth_snapshot` | `engine.metrics.snapshot` | 财富画像 |
| `analyze_allocation` | `engine.allocation.analyze` | 资产配置分析 |
| `plan_goal` | `engine.goals.plan_cashflow_goal` | 目标规划测算 |
| `run_scenario` | `engine.scenario.simulate` | 情景模拟 |
| `explain_score` | `engine.score.wealth_score` | 财富分解释 |

### I2. 对话编排升级（`chat.py` 加「意图路由」）

```
用户消息
 ├─ 建档意图（有抽取动作）→ 确认 → 落地 → 重算（不变）
 ├─ 规划意图（教育金/养老/学费/存多少/怎么准备）→ plan_goal 工具 → 测算答复
 ├─ 分析意图（配置/风险/集中/怎么优化）→ analyze_allocation 工具 → 分析答复
 ├─ 模拟意图（如果…会怎样）→ run_scenario 工具 → 模拟答复
 └─ 其他 → 泛泛健康回答（不变）
```

**意图识别**：先用规则关键词（`学费/教育金/养老/退休/怎么准备/怎么配置/如果/假如`…）命中，未命中再交给 LLM 判断。**数字仍由工具返回，LLM 只复述 + 解释**，系统提示硬约束「只复述工具返回的数字，不自行计算」。

### I3. 7 个「能力域」= 逻辑分工（预留拆分，不做独立实例）

V2 架构是**一个 AI Orchestrator（主控）+ 专业能力域/工具 + Wealth Engine**：

```
用户 → AI Orchestrator（理解/追问/路由/解释/策略表达）
          ├─ Wealth Analyst 能力域     → get_wealth_snapshot
          ├─ Risk Analyst 能力域       → stress_test / 风险指标
          ├─ Goal Planner 能力域       → plan_goal
          ├─ Portfolio Analyst 能力域  → analyze_allocation / portfolio_xray
          ├─ Scenario Analyst 能力域   → run_scenario
          ├─ Financial Coach 能力域    → 结论解释（纯 LLM 解读）
          └─ Proactive Advisor 能力域  → 主动发现/提醒（P1）
                        ↓ 全部走 tool 调用
                    Wealth Engine（确定性计算）
```

- 第一阶段：这 7 个是**能力域（= 专属 system prompt + 专属工具子集）**，由同一个 Orchestrator 调度，**不是 7 个独立 Agent 实例**，不互相通信。
- 架构**预留拆分能力**：每个能力域已按「prompt + tool 集」边界封装，未来业务复杂度上来后可独立成 Agent，接口不变。

---

## J. API 设计

> 新增端点（P0）。保留全部现有端点，`/api/decision` 内部改为调 Scenario Engine（兼容旧前端）。

| 方法 | 路径 | 说明 | 归属 |
|---|---|---|---|
| GET | `/api/wealth` | 财富画像（指标 + wealth_score + allocation + 目标 + AI 发现） | 驾驶舱数据源 |
| GET | `/api/allocation` | 资产配置分析（当前/目标区间/偏离/调整） | 配置页/驾驶舱 |
| POST | `/api/goals/plan` | 目标规划测算（现金流型入参） | 目标页/对话 |
| POST | `/api/scenario/{type}` | 情景模拟（通用） | 沙盘 |
| GET | `/api/scenarios` | 可用场景列表 + 参数 schema | 沙盘前端动态渲染 |
| GET | `/api/insights` | AI 主动发现/提醒列表 | 驾驶舱 AI 发现 |
| POST | `/api/family/profile` | 保存/更新家庭画像（风险承受等） | 设置 |

统一鉴权：除注册/登录外全部 `Depends(get_current_user)` + `_require_vip`（驾驶舱/配置基础能力免费，沙盘/深度报告 VIP）。

---

## K. 财富驾驶舱页面结构

> 数据源 `/api/wealth`，沿用暖色设计系统 + ECharts。

```
┌─────────────────────────────────────────────────────────┐
│ 顶栏：净资产（大字）          Family Wealth Score（可点开七维明细）│
├──────────────┬──────────────────┬───────────────────────┤
│ 资产配置      │ 现金流            │ 目标                    │
│ donut(ECharts)│ 收入/支出/结余/储蓄率│ 各目标进度条 + 缺口      │
│ 权益/固收/现金 │ 负债率/月供        │ 养老/教育准备度          │
│ + 目标区间偏离  │                   │                       │
├──────────────┴──────────────────┴───────────────────────┤
│ AI 发现（主动提醒卡片：房产集中度高 / 教育金缺口 / 应急充足…） │
│ [每张卡可点 → 进对应详情或对话]                            │
└─────────────────────────────────────────────────────────┘
```

- 七维明细：点 Score 展开，每个维度显示「得分 + 加减分理由」（满足可解释验收）。
- AI 发现卡片：来自 `score` 各维度的 `reasons` + 体检问题，规则确定性生成，非营销式。

---

## L. 财富沙盘交互设计

> 现有「决策模拟」弹窗升级为全屏「沙盘」视图。

```
财富决策沙盘
├── 左侧：场景选择（买房/提前还贷/投资/收入变动） + 参数滑块
│         · 首付比例 / 投资金额 / 股票:固收:现金 配比 / 收入降幅
├── 右侧上：指标对比表（净资产/月结余/应急月数/安全边际/目标完成度  before vs after）
├── 右侧下：长期财富投影折线图（ECharts，10/20/30 年，A/B 两线）
├── 底部：AI 结论解释 + 下一步行动
└── 方案库：保存当前参数为 scenario_snapshot，可并排比较 A/B/C
```

关键技术点：
1. **实时更新**：滑块 `input` 事件 → 300ms debounce → 调 `/api/scenario/{type}` 重算 → 更新对比表与折线。
2. **图表**：引入 ECharts（本地静态文件，无构建；donut/折线/分布图都靠它）。
3. **可追溯**：每次保存写 `scenario_snapshot`，满足「每个模拟场景有参数快照」。

---

## M. P0 / P1 / P2 开发计划

> 原则：先完整闭环，再扩展。

### P0（第一迭代，交付「完整闭环」）

> 执行顺序铁律：**先引擎后页面、先测试后 UI**。真正的价值在财富决策引擎，不在漂亮 Dashboard。

1. 数据模型迁移（F1~F5）+ 迁移脚本 + 兼容回填
2. Wealth Engine 模块化（metrics / allocation / goals / score / projection 纯函数）
3. Scenario Engine 通用框架（迁移 buy_house/prepay + 新增 invest/income_change）
4. API 端点（/api/wealth、/api/allocation、/api/goals/plan、/api/scenario、/api/scenarios）
5. **测试**（引擎单测 + API 集成测 + 迁移测）
6. 财富驾驶舱（先封装统一 ECharts 图表组件，再拼驾驶舱）
7. AI 解释层（AI Orchestrator + 工具注册表）
8. 财富沙盘（实时 What-if，复用图表组件）

### P1
10. 压力测试（7 场景）· Monte Carlo
11. Portfolio X-Ray（行业/地区/重叠/成本）
12. AI 再平衡 · AI 主动管家（reminder 落地）

### P2
13. Advisor 客户经理工作台
14. 专业财富报告（三套方案对比）
15. B 端 API · 多机构接入

---

## N. 数据迁移与兼容方案

1. **加列**：SQLite `ALTER TABLE ADD COLUMN`（幂等，先查 `PRAGMA table_info` 是否存在）。
2. **建表**：`CREATE TABLE IF NOT EXISTS`（insurance/family_profile/scenario_snapshot）。
3. **回填**：`asset_class` 按 `type` 映射；旧 `goal` 全部 `goal_kind='lump_sum'`；新建 `family_profile` 默认 `balanced`。
4. **版本化**：新增 `meta` 表存 `schema_version`；`migrate_v2.py` 按版本递增执行，`db.init_db()` 启动时自动跑。
5. **兼容**：全部旧 API 路由、旧字段语义保留；前端旧功能（总览/看板/报告/决策）迁移期不破坏，驾驶舱/沙盘作为新增入口上线。

---

## O. 测试与验收标准

### 测试
- **单元**：`engine.*` 每个纯函数（allocation/score/goals/scenario/projection）单测，含边界（利率 0、负缺口、无保险、空数据）。
- **集成**：`/api/wealth`、`/api/allocation`、`/api/goals/plan`、`/api/scenario/*` 端点测试（TestClient + 临时 DB）。
- **迁移**：旧 `data.db` 升级后数据完整、可读、字段回填正确。
- **前端**：`node --check` + Playwright e2e（驾驶舱渲染、沙盘滑块实时更新）。

### 验收（对齐方案第二十二节）
- [ ] 用户从现有档案进入驾驶舱，看到 Wealth Score + 七维解释
- [ ] 看到资产配置当前 vs 目标区间 + 偏离问题
- [ ] 创建现金流型目标（教育金），得到「需求/缺口/每月存/配置建议」
- [ ] 创建 What-if 场景，拖动变量结果实时变化
- [ ] AI 能解释结果 + 给下一步行动
- [ ] 关键指标可复算；AI 不承担核心计算
- [ ] 每个模拟场景有参数快照；结论可追溯
- [ ] 旧数据兼容；关键模块有测试

**最终标准**：用户明显感受到系统不仅知道「我有什么」，还知道「我现在怎么样、未来可能发生什么、不同选择会带来什么后果」。
