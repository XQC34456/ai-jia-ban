# AI家办 · Wealth API Contract v1

> **状态：API v1 CONTRACT FROZEN**（2026-08-13 冻结）
>
> 本文档是四层架构（Family Data → Wealth Engine → Decision Layer → API）对外暴露的**唯一 JSON 契约**，
> 前端 / AI Agent / 财富驾驶舱 / 财富沙盘 / 报告 / 提醒系统**全部只读本文档定义的响应结构**。
> 任何字段变更需走「契约变更评审」，不得单方面破坏。

---

## 1. 分层与边界（铁律）

```
Family Data ──▶ Wealth Engine ──▶ Decision Layer ──▶ Services/Orchestration ──▶ API Schema ──▶ 前端/Agent
   (数据)        (算，纯函数)        (判，规则)            (编排)                 (契约)          (展示/解释)
```

- **Wealth Engine**（`app/engine/`）：确定性纯函数，**只计算，不判断、不解释、零 LLM**。已验收，冻结。
- **Decision Layer**（`app/decision/`）：只做「判断」，7 类问题 + 四象限 + 优先级。**不计算任何财务数字**。
- **AI Agent**：只做「理解用户 + 调用接口 + 解释结果 + 提出可执行计划」，**绝不替 Engine 算账**。
- **前端**：只读 API 响应，**绝不 import `app/engine/`，绝不自行计算财富逻辑**。

---

## 2. 通用约定

| 约定 | 规则 |
|------|------|
| **货币** | 所有金额字段默认 **CNY（人民币），单位元**。`Overview.currency` 显式声明 `"CNY"`。 |
| **百分比** | 一律用 **ratio（0~1 的小数）**，`0.30 = 30%`。字段命名：配置类用 `*_pct`（如 `financial_pct`、`real_estate_pct`），指标类用 `*_rate`（`savings_rate`）、`*_ratio`（`coverage_ratio`、`funding_ratio`）、`dti`。**绝不出现 `30` 这种整数值百分比**。 |
| **日期** | ISO 格式 `YYYY-MM-DD`（如 `2030-08-01`）。无日期字段为空字符串或缺省。 |
| **null 行为** | 无法计算的指标（缺年龄/支出/收入）**返回 `null`**，不是 0。例如 `retirement` 整块、`rfr`、`nwc`、`savings_rate`、`dti`、`emergency_months`、`coverage_ratio`。前端据此区分「值为 0」与「无法计算」。 |
| **枚举** | 用字符串 + 本文档约定的取值集合（见各节）。`severity` ∈ {P0, P1, P2}；`type` ∈ 7 类；`quadrant` ∈ 4+1；`scenario` ∈ 4 类。 |
| **金额精度** | 元，保留 2 位小数（`round(x, 2)`）；ratio 保留 3 位（`round(x, 3)`）。 |

---

## 3. 鉴权分级（已定）

| 能力 | Tier | 说明 |
|------|------|------|
| `GET /api/wealth/overview` | 免费 | 驾驶舱总览 |
| `GET /api/wealth/issues` | 免费 | 财富问题集合 |
| `GET /api/wealth/goals` | 免费 | 统一目标对象 |
| `POST /api/wealth/scenario/{name}` | **VIP** | 情景模拟（决策模拟） |

- 请求头：`Authorization: Bearer <token>`。
- 未登录 → `401`；免费用户访问 VIP 接口 → `403`（文案：`深度报告和决策模拟是 VIP 专属功能，升级后即可使用`）。

---

## 4. Endpoint 清单

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| `GET` | `/api/health` | 无 | 健康检查 |
| `POST` | `/api/register` | 无 | 注册，返回 `{token, username, tier}` |
| `POST` | `/api/login` | 无 | 登录，返回 `{token, username, tier}` |
| `GET` | `/api/me` | 登录 | 当前用户 |
| `POST` | `/api/upgrade` | 登录 | 模拟开通 VIP（`tier→vip`） |
| `GET` | `/api/family` | 登录 | 旧接口（data + snapshot + problems）**保留** |
| `POST` | `/api/chat` | 登录 | 对话 |
| `POST` | `/api/confirm` | 登录 | 确认待办 |
| `GET` | `/api/report` | VIP | 旧报告接口**保留** |
| `POST` | `/api/decision` | VIP | 旧决策接口**保留** |
| `POST` | `/api/family/entity/{table}` | 登录 | 建实体（person/asset/liability/cashflow/goal/insurance/reminder） |
| `PUT` | `/api/entity/{table}/{id}` | 登录 | 改实体（校验属主） |
| `DELETE` | `/api/entity/{table}/{id}` | 登录 | 删实体（校验属主） |
| **`GET`** | **`/api/wealth/overview`** | 登录 | **财富驾驶舱总览（新）** |
| **`GET`** | **`/api/wealth/issues`** | 登录 | **财富问题集合（新）** |
| **`GET`** | **`/api/wealth/goals`** | 登录 | **统一目标对象（新）** |
| **`POST`** | **`/api/wealth/scenario/{name}`** | VIP | **情景模拟（新）** |

> 接口策略（已定）：**新增独立 + 旧接口保留**。旧 `/api/family`、`/api/report`、`/api/decision` 不删除，但新前端只消费 `/api/wealth/*`。

---

## 5. Overview 契约（`GET /api/wealth/overview`）

响应是「一次返回驾驶舱所需全部状态」，前端**零二次计算**。

```json
{
  "currency": "CNY",
  "wealth_score": 81,
  "wealth_level": "稳健",
  "net_worth": 5000000,
  "total_assets": 6000000,
  "total_liabilities": 1000000,
  "liquid_assets": 300000,
  "asset_allocation": {
    "classes": {"cash": 0.10, "fixed_income": 0.20, "equity": 0.30,
                "real_estate": 0.30, "alternative": 0.05, "other": 0.05},
    "financial_pct": 0.60,
    "concentration": {"real_estate_pct": 0.30, "other_pct": 0.05}
  },
  "allocation_fitness": 78,
  "allocation_target": {"cash": 0.10, "fixed_income": 0.25, "equity": 0.30,
                        "real_estate": 0.25, "alternative": 0.05, "other": 0.05},
  "cashflow": {"income": 50000, "expense": 20000, "surplus": 30000, "savings_rate": 0.60},
  "liquidity": {"liquid_assets": 300000, "emergency_months": 15.0},
  "debt": {"total_debt": 1000000, "monthly_payment": 8000, "dti": 0.16},
  "protection": {"insurance_count": 2, "total_coverage": 10000000,
                 "total_premium": 100000, "coverage_ratio": 16.67},
  "goals": [ { /* GoalOut，见 §7 */ } ],
  "retirement": {
    "rfr": 2.21, "nwc": 2.61, "quadrant": "养老健康",
    "investable_at_retirement": 5500000, "net_worth_at_retirement": 6000000,
    "retirement_need_pv": 2500000,
    "known_limitations": [
      "retirement_debt_service_not_included",
      "goal_retirement_semantic_overlap",
      "other_asset_liquidity_assumption"
    ]
  },
  "issues": [ { /* Issue，见 §6 */ } ],
  "alerts": ["退休流动资金不足"],
  "priorities": [{"issue_id": "...", "type": "retirement", "severity": "P0", "title": "..."}],
  "recommendations": [ { /* Recommendation，见 §6 */ } ]
}
```

### 字段要点
- `wealth_score`：0~100 整数；`wealth_level` ∈ 脆弱/谨慎/稳健/良好/卓越。
- `asset_allocation.classes`：六大类（cash/fixed_income/equity/real_estate/alternative/other）占比，Σ≈1，ratio。
- `allocation_target`：Σ=100% 的**点目标**（已按风险偏好/久期/DTI 归一化）。
- `retirement`：**无年龄或无支出时整块为 `null`**。RFR（可投资资产口径）与 NWC（净资产口径）双指标，`quadrant` 四象限映射。
- `known_limitations`：模型能力边界，前端/Agent 必须**如实呈现**，不得夸大。

---

## 6. Issue / Recommendation 契约 + Severity 语义

### Issue（财富问题对象，统一语言）
```json
{
  "issue_id": "RETIREMENT_LIQUIDITY_001",
  "type": "retirement",
  "severity": "P0",
  "title": "退休流动资金不足",
  "finding": "RFR 仅 0.48，但 NWC 达 2.49",
  "reason": ["房产等低流动性资产占比过高", "退休时可投资（金融）资产不足"],
  "metric": {"rfr": 0.48, "nwc": 2.49},
  "target": {"rfr": 1.0},
  "recommendations": [ { /* Recommendation */ } ],
  "scenarios": ["invest"]
}
```

- `type` ∈ {cashflow, liquidity, debt, allocation, retirement, goals, decision}（7 类）。
- `metric` / `target`：支撑指标与目标指标 dict。`issue.target` 为**目标描述**（人类可读，可带 `≥`/`≤`）。
- `scenarios`：该问题可触发的已实现情景名列表。

### Severity 语义（全契约一致）
| severity | 业务含义 |
|----------|----------|
| **P0** | 若不处理将**立即/近期危害财富安全**（负现金流、应急金<3 月、DTI>0.5、退休流动资金不足） |
| **P1** | 影响**长期目标达成**（储蓄率<20%、应急金<6 月、DTI>0.3、配置适配度<60、目标超支、高杠杆资产结构） |
| **P2** | **优化项**——不紧急但建议行动（现金闲置、目标缺口） |

### Recommendation（动作化建议，只到资产类别/行为层，绝不推荐具体产品）
```json
{
  "recommendation_id": "RETIREMENT_LIQUIDITY_001-R1",
  "action": "增加金融资产",
  "detail": "未来新增资金优先配置现金/固收，降低新增资金进入房产的比例",
  "reason": "房产等低流动性资产占比过高，退休可投资资产不足",
  "priority": "P0",
  "current": {"rfr": 0.48, "nwc": 2.49},
  "target": {"rfr": 1.0},
  "expected_effect": {},
  "actionable": true,
  "scenario": "invest"
}
```

- `recommendation_id`：`<issue_id>-R<n>`，稳定。
- `priority`：继承所属 issue 的 severity。
- `current`：当前状态支撑指标（继承 issue.metric）。
- `target`：**量化目标（数值 dict）**，供场景参数化。
- `expected_effect`：预期效果，**V1 预留为空**；运行场景后由编排层回填。
- `actionable`：`scenario` 非空即为 `true`。
- `scenario`：可触发的已实现情景名 ∈ {buy_house, prepay, invest, income_change}；无对应情景为 `null`（`actionable=false`）。

### Decision → Recommendation → Scenario → Action 链
```
Issue ──▶ recommendations[].scenario ──▶ POST /api/wealth/scenario/{name} ──▶ 结果(impacts/rows)
```
- 链上的 `scenario` **必须是 `SCENARIO_NAMES` 中已实现的情景名**（契约测试强制）。
- 未实现的情景（如「资产再平衡」`allocation_rebalance`）**不得**出现在链上；规划为 Plan C 新增情景，届时更新 `SCENARIO_NAMES` 并冻结。

---

## 7. Goal 契约（`GET /api/wealth/goals`）
```json
{
  "goals": [
    {"goal_id": 1, "type": "教育", "name": "孩子大学", "goal_kind": "lump_sum",
     "target_amount": 500000, "target_date": "2030-08-01", "current_saved": 100000,
     "monthly_needed": null, "gap": 400000, "coverage": 0.2, "priority": 1}
  ]
}
```
- `goal_kind` ∈ {lump_sum（一次性）, cashflow（现金流型）}；两种口径统一成一个对象。
- `coverage`：当前资金 / 目标金额（0~1，确定性测算，**非概率**）。
- 无目标时 `{"goals": []}`。

---

## 8. Scenario 契约（`POST /api/wealth/scenario/{name}`，VIP）

### 输入
```json
{ "params": { /* 场景参数，见下表 */ } }
```

| name | 关键参数 | 输出要点 |
|------|----------|----------|
| `buy_house` | 房价、首付、贷款等 | 净资产、金融资产、流动性、月供、负债率、房产占比、目标资金影响 |
| `prepay` | 提前还贷金额/来源 | 负债下降、现金流、净资产 |
| `invest` | `amount`（金额）、`to_class`（目标大类） | 金融资产、资产类别占比、收益率/波动、久期、期末资产、目标完成度、流动性 |
| `income_change` | 收入/支出变化 | 现金流、结余、储蓄率 |

### 输出（单次模拟）
```json
{
  "scenario": "invest",
  "title": "投资模拟",
  "impacts": [ { /* key + delta/前后值，随场景不同 */ } ],
  "rows": [ {"a": "...", "b": "..."} ],
  "params_snapshot": { /* 参数快照 */ }
}
```
- 单次模拟返回**前后对比**（`impacts` = 各维度增量；`rows` = 前后对照表）。

### 基线 / A-B-C 对比（**契约已冻结，实现归 Plan C**）
财富沙盘需要「基线 + 多方案 + 逐维度对比」。当前 engine 的 `run_scenario` 返回**增量**，不返回「情景后完整数据」，
因此**同一次对比里重算 wealth_score / RFR / NWC 等全局指标，需要 engine 暴露「场景 → 数据 apply」原语**。

冻结的目标契约（Plan C 按此实现，不改 Engine 核心计算）：
```json
{
  "scenario": "invest",
  "baseline": { /* 当前 Overview（现状） */ },
  "options": [
    {"id": "A", "name": "投入 30 万权益", "params": {"amount": 300000, "to_class": "equity"},
     "result": { /* 单次模拟结果 */ }},
    {"id": "B", "name": "投入 30 万固收", "params": {"amount": 300000, "to_class": "fixed_income"},
     "result": { /* ... */ }}
  ],
  "comparison": {
    "net_worth":   {"baseline": 5000000, "A": 5000000, "B": 5000000},
    "cashflow":    {"baseline": 30000,    "A": 30000,    "B": 30000},
    "liquidity":   {"baseline": 15.0,     "A": 14.0,     "B": 14.5},
    "debt":        {"baseline": 0.16,     "A": 0.16,     "B": 0.16},
    "allocation":  {"baseline": {...},    "A": {...},    "B": {...}},
    "rfr":         {"baseline": 2.21,     "A": 2.24,     "B": 2.22},
    "wealth_score": {"baseline": 81,      "A": 82,       "B": 81}
  }
}
```
对比维度覆盖：**净资产 / 现金流 / 流动性 / 负债 / 配置 / RFR / NWC / 财富分 / 目标影响**。

---

## 9. Error 契约（统一）

所有错误返回统一形态，前端无需区分错误来源：

| 情况 | HTTP | 响应体 |
|------|------|--------|
| 未登录 / token 失效 | 401 | `{"detail": "未登录"}` / `{"detail": "登录已失效，请重新登录"}` |
| 免费用户访问 VIP | 403 | `{"detail": "深度报告和决策模拟是 VIP 专属功能，升级后即可使用"}` |
| 未知情景名 | 400 | `{"detail": "未知场景: <name>"}` |
| **情景参数校验错误** | **400** | **`{"detail": "请填写房价"}`（engine 内联错误已转为 HTTP 400）** |
| 未知实体类型 | 400 | `{"detail": "未知实体类型: <table>"}` |
| 记录不存在 / 无权操作 | 404 / 403 | `{"detail": "记录不存在"}` / `{"detail": "无权操作该记录"}` |
| 参数校验失败（pydantic） | 422 | FastAPI 默认 `{"detail": [...]}` |

> 统一原则：**业务错误一律 `{"detail": "<人类可读文案>"}` + 恰当 4xx 状态码**。
> 已修复：scenario 的 engine 内联 `{"error": ...}`（HTTP 200）已统一转为 `400 + {"detail": ...}`。

---

## 10. Known Limitations（如实声明）

当前模型能力边界，注入 `retirement.known_limitations`，前端/Agent 必须如实呈现：

- `retirement_debt_service_not_included`：养老测算未计入退休期仍需偿还的负债服务。
- `goal_retirement_semantic_overlap`：养老目标与退休测算存在语义重叠。
- `other_asset_liquidity_assumption`：`other` 类资产的流动性按假设处理。

---

## 11. 冻结与变更

- **本契约自 2026-08-13 起冻结（API v1 CONTRACT FROZEN）**，由 `tests/test_frontend_contract.py` 守门。
- 变更流程：任何字段增删改 → 先改本文档 → 更新 Schema + 契约测试 → 全量回归（137+ green）→ 重新冻结。
- **铁律不变**：`app/engine/` 核心计算逻辑冻结，不改 Wealth Engine 的确定性财务模型。
