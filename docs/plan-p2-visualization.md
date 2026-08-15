# P2 可视化补全 · 实施计划（health 下钻三个明细证据块 + schema 修复）

> **Goal:** 把 health 页的现金流/负债/保障三个下钻区块从「聚合数字」补成「明细证据块」——支出去向瀑布、逐笔负债利率期限、家庭成员保障覆盖。全部确定性，前端只读不计算。
> **铁律:** 数字一律确定性计算；分类/归组/join 全部在后端 `overview.py` 完成；LLM 绝不参与；不碰 Engine/Decision 核心。
> **前置:** 依赖已完成 V2.6（charts.js 工厂 + health 三区块 + `dimensions` 已由 Task 1.1 暴露）。

---

## 全局约束（与 V2.6 一致）

1. 数字一律确定性计算，前端零新增财富计算。
2. 三块明细数据全部由 `build_overview` 确定性产出（分组/归一化/join 都在后端），前端只 `props.data` 读取。
3. 不碰 `app/engine/*`、`app/decision/*` 任何核心逻辑；唯一后端改动是 `overview.py` 多暴露已存在明细 + `schemas/wealth.py` 补声明。
4. **「提前还款节省利息」等模拟计算不在本次范围**（那是沙盘/Decision 的职责），负债明细只展示已有字段（利率/剩余期限/月供/本金）。
5. 每步完成后自我验证：`pytest` + `node --check` + 浏览器截图审查。

---

## ⚠️ Task 0（先修 live bug）：Overview schema 补 `dimensions`

**现象:** Task 1.1 在 `overview.py` 返回了 `dimensions`，但 `schemas/wealth.py` 的 `Overview` 未声明该字段 → `response_model=Overview` 把 `dimensions` 剥掉 → health 雷达在真机显示「暂无数据」。

**文件:**
- 修改 `app/schemas/wealth.py`
- 测试 `tests/test_overview_schema.py`（新建）

**改动:**
1. `Overview` 增加字段（放在 `wealth_level` 之后、`net_worth` 之前，与 `overview.py` 返回顺序对齐）：
   ```python
   dimensions: list[dict] = Field(default_factory=list)   # 7 维健康评分（含 protection），Task 1.1 暴露
   ```

**测试（`tests/test_overview_schema.py`，防再次被 response_model 剥掉）:**
```python
from app.services import build_overview
from app.schemas.wealth import Overview

def _data():
    return {
        "family": {}, "persons": [{"name": "本人", "relation": "本人", "birth_year": 1990}],
        "assets": [{"type": "存款", "name": "活期", "value": 300000}],
        "liabilities": [{"type": "房贷", "name": "房贷", "principal": 500000,
                         "monthly_payment": 4000, "interest_rate": 0.04, "remaining_months": 240}],
        "cashflows": [{"flow_type": "income", "category": "工资", "amount": 25000, "period": "月"},
                      {"flow_type": "expense", "category": "生活", "amount": 15000, "period": "月"}],
        "goals": [], "reminders": [],
        "insurance": [{"person_id": None, "type": "重疾", "name": "重疾险",
                       "annual_premium": 5000, "coverage": 500000}],
        "family_profile": {},
    }

def test_overview_schema_keeps_dimensions():
    o = build_overview(_data())
    assert len(o["dimensions"]) == 7                 # build_overview 有 7 维
    m = Overview.model_validate(o)                    # 模拟 response_model
    assert len(m.dimensions) == 7                     # 不被剥掉（回归 Task 1.1 漏声明）
```

**验证:** `pytest tests/test_overview_schema.py -v` 全绿（修复前该断言 FAIL）。

---

## Task 1：现金流「固定/弹性」细分瀑布

### Task 1.1（后端）：`cashflow.breakdown` 确定性分组

**文件:** `app/services/overview.py`（`build_overview` 的 `cashflow` 块处）

**改动:** 新增 `_cashflow_breakdown(cashflows)`，按 `category` 分组、`period` 归一化到月（复用 Engine 口径：`年` ÷12），支出按关键字映射「固定/弹性」：

```python
_FIXED_KEYWORDS = ("贷", "租", "物业", "保险", "学费", "教育", "社保", "养老",
                   "水电", "燃气", "通信", "话费", "宽带", "月供")

def _expense_kind(category: str) -> str:
    """支出分类：固定/弹性。纯展示分类（关键字映射），不改变任何金额。"""
    return "fixed" if any(k in (category or "") for k in _FIXED_KEYWORDS) else "elastic"

def _monthly(amount: float, period: str) -> float:
    return amount / 12.0 if period == "年" else amount

def _cashflow_breakdown(cashflows: list[dict]) -> dict:
    incomes, expenses = {}, {}
    for c in cashflows:
        amt = _monthly(float(c.get("amount") or 0), c.get("period", "月"))
        cat = c.get("category") or "其他"
        if c.get("flow_type") == "income":
            incomes[cat] = incomes.get(cat, 0) + amt
        else:
            expenses[cat] = expenses.get(cat, 0) + amt
    return {
        "incomes": [{"category": k, "amount": round(v, 2)} for k, v in incomes.items()],
        "expenses": [{"category": k, "amount": round(v, 2), "kind": _expense_kind(k)}
                     for k, v in expenses.items()],
    }
```

`build_overview` 的 `cashflow` 块追加一行：
```python
"cashflow": {
    ...,
    "breakdown": _cashflow_breakdown(cashflows),
},
```

**文件:** `app/schemas/wealth.py` — `CashflowBlock` 增加：
```python
breakdown: dict = Field(default_factory=dict)   # {incomes:[{category,amount}], expenses:[{category,amount,kind}]}
```

### Task 1.2（图表）：`CashflowBreakdown` 瀑布组件

**文件:** `static/charts.js`

**内容:** 新增导出 `CashflowBreakdown`（复用 `defineChart`）。数据 `data` 是 `cashflow.breakdown`，但瀑布需要总金额，故由 `health.js` 传入「组好的四段」而非原始 breakdown。为保持「图表只读 props」，**把四段拆解逻辑放在 health.js 的 computed**（纯展示、不涉财富计算），组件只画：

```js
export const CashflowBreakdown = defineChart((data) => {
  // data: [{name:'月收入', value:+, kind:'in'}, {name:'固定支出', value:-, kind:'out'}, {name:'弹性支出', value:-, kind:'out'}, {name:'月结余', value:±, kind:'surplus'}]
  const rows = data || [];
  if (!rows.length) return null;
  // 瀑布：透明基座 + 可见柱，展示「收入 → 减去支出 → 结余」的累积流
  ...
});
```

**说明:** 瀑布图实现用 ECharts 堆叠柱 + 透明 base（`stack: 'total'` 下一层 `itemStyle.opacity: 0`），纯确定性数字。固定/弹性两段的值分别由 breakdown.expenses 中 `kind==='fixed'/'elastic'` 求和得到（**求和是展示聚合，不改任何财富数字，铁律允许**）。

### Task 1.3（归位）：health 现金流区块接入

**文件:** `static/views/health.js`

**改动:**
1. import `CashflowBreakdown`，注册到 `components`。
2. 加 computed `cashflowWaterfall`：由 `o.cashflow.breakdown` 组四段（收入 / 固定支出 / 弹性支出 / 结余，结余复用 `o.cashflow.surplus`）。
3. 现金流 section 在 `<cashflow-chart>` 之后插入 `<cashflow-breakdown :data="cashflowWaterfall" />`。

**验证:** `node --check static/charts.js static/views/health.js`；浏览器截图：有固定/弹性支出的家庭 → 瀑布四段正确、颜色区分、结余与 KV 一致。

---

## Task 2：负债明细（逐笔利率/期限）

### Task 2.1（后端）：`debt.items` 明细透传

**文件:** `app/services/overview.py` — `debt` 块追加：
```python
"debt": {
    ...,
    "items": [
        {"type": l.get("type"), "name": l.get("name"),
         "principal": float(l.get("principal") or 0),
         "monthly_payment": float(l.get("monthly_payment") or 0),
         "interest_rate": l.get("interest_rate"),
         "remaining_months": l.get("remaining_months")}
        for l in liabilities
    ],
},
```

**文件:** `app/schemas/wealth.py` — `DebtBlock` 增加：
```python
items: list[dict] = Field(default_factory=list)   # 逐笔负债明细（利率/剩余期限/月供/本金）
```

### Task 2.2（图表）：`DebtDetail` 组件

**文件:** `static/charts.js`

**内容:** 导出 `DebtDetail`（`defineChart`）。数据 `data = debt.items`，水平条形展示每笔「剩余期限（月）」+ 右侧标签标利率；无利率/期限的负债降级为「本金」条形。纯只读，`interest_rate` 显示时 ×100 为百分数（展示换算，非财富计算）。

```js
export const DebtDetail = defineChart((data) => {
  const items = data || [];
  if (!items.length) return null;
  // yAxis: 负债名；series: 剩余期限（月），label 显示利率%
  ...
});
```

### Task 2.3（归位）：health 负债区块接入

**文件:** `static/views/health.js`

**改动:** import + 注册 `DebtDetail`；负债 section 在 `<debt-gauge>` 后、KV 前插入 `<debt-detail :data="o.debt.items" />`（仅当 `o.debt.items` 非空渲染，用 `v-if`）。

**验证:** `node --check`；截图：有多笔负债的家庭 → 逐笔名称 + 剩余期限 + 利率显示正确。

---

## Task 3：保障成员覆盖

### Task 3.1（后端）：`protection.members` 按成员归组

**文件:** `app/services/overview.py` — `_protection` 增加成员维度（join persons）：

```python
def _protection(insurance: list[dict], cashflows: list[dict], persons: list[dict]) -> dict:
    ...  # 现有聚合不变
    by_person = {}
    for i in insurance:
        pid = i.get("person_id")
        by_person.setdefault(pid, {"coverage": 0.0, "premium": 0.0, "count": 0})
        by_person[pid]["coverage"] += float(i.get("coverage") or 0)
        by_person[pid]["premium"] += float(i.get("annual_premium") or 0)
        by_person[pid]["count"] += 1
    pname = {p.get("id"): p.get("name") or "未命名" for p in persons}
    members = [
        {"name": pname.get(pid, "家庭/未指定"), "relation": (pname.get(pid) and
            next((p.get("relation") for p in persons if p.get("id") == pid), None)) or "",
         "coverage": round(v["coverage"], 2), "premium": round(v["premium"], 2),
         "policy_count": v["count"]}
        for pid, v in by_person.items()
    ]
    return {..., "members": members}
```

`build_overview` 调用处同步改：`"protection": _protection(family_data.get("insurance", []), cashflows, family_data.get("persons", []))`。

**文件:** `app/schemas/wealth.py` — `ProtectionBlock` 增加：
```python
members: list[dict] = Field(default_factory=list)   # 每成员保额/保费/保单数
```

### Task 3.2（图表）：`ProtectionMembers` 组件

**文件:** `static/charts.js`

**内容:** 导出 `ProtectionMembers`（`defineChart`）。数据 `data = protection.members`，水平条形展示每成员保额，标签标「保额」。纯只读。

```js
export const ProtectionMembers = defineChart((data) => {
  const members = data || [];
  if (!members.length) return null;
  // yAxis: 成员名；series: 保额
  ...
});
```

### Task 3.3（归位）：health 保障区块接入

**文件:** `static/views/health.js`

**改动:** import + 注册 `ProtectionMembers`；保障 section 在 `<protection-gap>` 后插入 `<protection-members :data="o.protection.members" />`（`v-if` 非空）。

**验证:** `node --check`；截图：多成员 + 关联保险 → 每成员保额正确；未关联保险的保单归「家庭/未指定」。

---

## 建议执行顺序与依赖

```
Task 0（schema 修 dimensions）──► 必须最先（否则 Task 1~3 新增字段也会被剥掉）
Task 1（现金流瀑布） ──► Task 2（负债明细） ──► Task 3（保障成员）
```

- Task 0 是硬前置（修 live bug）。
- Task 1/2/3 相互独立，可任意顺序；建议 0→1→2→3（每个都是「后端 → schema → 图表 → 归位 → 验证」完整小闭环）。

## 验证汇总（每步完成跑一次）

```bash
python -m pytest -q                         # 全量回归（现 464，新增 ~5 条）
node --check static/charts.js static/views/health.js
# 浏览器截图审查 health 页三个下钻区块
```

## 交付后

- 手机端：`python deploy_update.py`（沿用既有一键更新，app/+static/ 全量，不碰 data.db/.env）。
- 不自动 commit（等你确认后按「P2 可视化补全」单独或合并提交）。
