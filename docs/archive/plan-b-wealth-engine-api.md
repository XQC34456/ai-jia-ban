# Plan B：Wealth Engine API + Decision Layer 实现计划

> 目标：把已验收的确定性 Wealth Engine 封装成「前端 / AI Agent / 驾驶舱 / 财富沙盘」共同调用的标准 API 层，并新增 Decision Layer（判断层）。四层彻底解耦：Engine 算 → Decision 判 → API 供 → AI 解释。

**核心约束**（延续验收结论，不推翻现有架构）：
- Engine（`app/engine/`）零改动，94 个测试保持通过。
- Schema 只包 API 边界：engine 内部继续用 dict，pydantic 只做请求/响应契约。
- 旧接口 `/api/family`、`/api/decision`、`/api/report` 全部保留，新增 `/api/wealth/*` 独立。
- 鉴权：`/api/wealth/overview`、`/api/wealth/issues`、`/api/wealth/goals` 免费；`/api/wealth/scenario/*` VIP。
- 建议只到「资产类别/动作」层，绝不推荐具体产品。

---

## 一、目标文件结构（新增三层，不动 engine）

```
app/schemas/__init__.py        # 统一 I/O Schema（pydantic v2）
app/schemas/family.py          #   FamilyData 输入模型（校验+归一化）
app/schemas/wealth.py          #   Overview / RetirementBlock 等输出模型
app/schemas/issue.py           #   Issue / Recommendation 对象
app/schemas/scenario.py        #   Scenario 请求/响应
app/schemas/goal.py            #   GoalOut 统一目标对象

app/services/__init__.py
app/services/overview.py       #   build_overview(family_data) -> dict（纯编排，可测）

app/decision/__init__.py
app/decision/detect.py         #   7 类问题检测器（cashflow/liquidity/debt/allocation/retirement/goals/decision）
app/decision/issue.py          #   build_issues(family_data) -> list[Issue]（统一财富问题对象）
app/decision/priority.py       #   severity(P0/P1/P2) 映射 + 排序
app/decision/recommend.py      #   建议模板（动作化，不推荐产品）

app/api/__init__.py
app/api/wealth.py              #   GET /api/wealth/overview, GET /api/wealth/issues
app/api/scenario.py            #   POST /api/wealth/scenario/{name}（VIP）
app/api/goal.py                #   GET /api/wealth/goals

tests/test_schemas.py
tests/test_decision.py
tests/test_services_overview.py
tests/test_api_wealth.py
tests/test_api_scenario.py
tests/test_api_goal.py
```

`app/main.py` 仅追加三行 `include_router`，不改现有路由。

---

## 二、数据契约（JSON Contract）

### 2.1 `/api/wealth/overview` 响应

```jsonc
{
  "wealth_score": 81, "wealth_level": "稳健",
  "net_worth": 5000000, "total_assets": 5800000, "total_liabilities": 800000,
  "liquid_assets": 1800000,
  "asset_allocation": { "classes": {...}, "concentration": {...}, "financial_pct": {...} },
  "allocation_fitness": 88, "allocation_target": {"cash":0.16,"fixed_income":0.5,"equity":0.34},
  "cashflow": { "income":..., "expense":..., "surplus":..., "savings_rate":... },
  "liquidity": { "emergency_months":... },
  "debt": { "dti":..., "total_debt":..., "monthly_payment":... },
  "protection": { "insurance_count":..., "coverage":..., "premium":..., "ratio":... },
  "goals": [ /* GoalOut[] */ ],
  "retirement": {
    "rfr": 2.21, "nwc": 2.61, "quadrant": "养老健康",
    "investable_at_retirement":..., "net_worth_at_retirement":..., "retirement_need_pv":...,
    "known_limitations": ["retirement_debt_service_not_included", "goal_retirement_semantic_overlap", "other_asset_liquidity_assumption"]
  },
  "issues": [ /* Issue[]，Decision Layer 输出 */ ],
  "alerts": [ "退休流动资金不足", "应急资金仅覆盖 1.8 个月" ],
  "priorities": [ {"issue_id":..., "type":..., "severity":"P0", "title":...} ],
  "recommendations": [ /* Recommendation[]，动作化 */ ]
}
```

### 2.2 Issue 对象（Step 4 统一结构）

```jsonc
{
  "issue_id": "RETIREMENT_LIQUIDITY_001",
  "type": "retirement", "severity": "P0",
  "title": "退休流动资金不足", "finding": "RFR 仅为 0.48",
  "reason": ["房产占比过高", "可投资资产不足"],
  "metric": { "rfr": 0.48, "nwc": 2.49 },
  "target": { "rfr": 1.0 },
  "recommendations": [ { "action": "增加金融资产", "detail": "...", "target": "RFR 0.48 → ≥1.0" } ],
  "scenarios": ["allocation_rebalance"]
}
```

### 2.3 GoalOut（Step 6 统一目标）

```jsonc
{
  "goal_id": 1, "type": "教育", "name": "...",
  "goal_kind": "lump_sum" | "cashflow",
  "target_amount":..., "target_date":"..."|null, "current_saved":...,
  "monthly_needed":..., "gap":..., "coverage":0.0..1.0, "priority":1|2|3
}
```

### 2.4 Scenario（Step 5 统一入口）

`POST /api/wealth/scenario/{name}`，`name ∈ {buy_house, prepay, invest, income_change}`，body `{"params": {...}}` → 转发 `engine.scenario.run_scenario(data, snapshot, name, params)`。

---

## 三、关键函数签名

```python
# services/overview.py
def build_overview(family_data: dict) -> dict: ...
    # 内部组合：metrics.snapshot + score.wealth_score + allocation.analyze
    #        + projection.retirement_funding_ratio + decision.build_issues

# decision/issue.py
def build_issues(family_data: dict) -> list[dict]: ...   # 调用 detect.py 7 检测器 + priority 排序

# decision/detect.py —— 每个返回 None 或 issue dict
def detect_cashflow(fd, snap) -> dict | None
def detect_liquidity(fd, snap) -> dict | None
def detect_debt(fd, snap) -> dict | None
def detect_allocation(fd, snap, ws) -> dict | None
def detect_retirement(fd, snap, rfr) -> dict | None   # 四象限：RFR/NWC 交叉
def detect_goals(fd, snap) -> dict | None
def detect_decision(fd, snap) -> dict | None

# decision/priority.py
SEVERITY_MAP = {5:"P0", 4:"P0", 3:"P1", 2:"P2", 1:"P2"}
def rank(issues: list[dict]) -> list[dict]
```

---

## 四、实现步骤（TDD，每步独立可测 + commit）

1. **Schema**：`schemas/family.py`（FamilyData.from_dict 校验）、`wealth/issue/scenario/goal` 输出模型。测试：`test_schemas.py`。
2. **编排层**：`services/overview.py::build_overview` 聚合 engine，返回契约字典。测试：`test_services_overview.py`（用 8 组案例断言 rfr/nwc/quadrant/wealth_score）。
3. **Decision Layer**：`decision/detect.py` 7 检测器 + `priority.py`。测试：`test_decision.py`（四象限、P0 排序、房产集中识别）。
4. **Issue 对象**：`decision/issue.py::build_issues` + `recommend.py` 动作化建议。并入 test_decision。
5. **Scenario API**：`api/scenario.py` 统一包装 run_scenario。测试：`test_api_scenario.py`。
6. **Goal Engine**：`schemas/goal.py` + `services` 内 goal 统一测算（复用 metrics.goal_gap + goals.plan_cashflow_goal）。测试：`test_api_goal.py`。
7. **Overview API**：`api/wealth.py` 两路由（overview/issues），main.py 挂载。测试：`test_api_wealth.py`（httpx TestClient）。
8. **收尾**：全量 pytest + 8 组验收案例回归 + known_limitations 注入确认。

**验收门**：94 旧测试全绿 + 新增测试全绿；8 组案例（C1 高房产集中、C2 负资产、C3 高现金、C4 高负债、C5 临近退休、C6 现金流养老目标、C7a/C7b 对照组、C8 超高净值）在 overview 中输出正确；「高净资产但低退休流动资金」能被 issue 对象识别。
