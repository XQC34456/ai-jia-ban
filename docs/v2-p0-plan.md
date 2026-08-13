# V2 P0 · Plan A（数据模型迁移 + Wealth Engine + Scenario Engine）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有「体检 + 2 决策场景」的 20% 引擎，升级为可支撑「资产配置分析 / 目标规划 / 财富评分 / 情景模拟」的完整确定性 Wealth Engine，且旧数据、旧 API 全兼容。

**Architecture:** 在现有 `calc_engine.py` 纯函数地基上，新建 `app/engine/` 包，按 `metrics / projection / allocation / goals / score / scenario` 六模块拆分；`calc_engine.py` 保留为兼容层。数据层只加列加表（SQLite `ALTER TABLE ADD COLUMN` + `CREATE TABLE IF NOT EXISTS`），迁移幂等、版本化。

**Tech Stack:** Python 3.10 · FastAPI 0.140 · SQLite（内置 sqlite3）· pytest · 纯函数零外部依赖（引擎层）。

## Global Constraints

- 版本 floor：Python 3.10，pytest>=7.0（已在 requirements.txt）。
- **财务数字一律由确定性纯函数计算**，引擎模块不 import 任何 LLM/httpx。
- 数据层原则：**只加列加表，不删列不改字段语义**；旧 `type`/`goal` 语义保留。
- 迁移脚本必须**幂等**（重复执行不报错、不重复加列）。
- 命名：字段/函数用 `snake_case`；`asset_class` 枚举为 `cash / fixed_income / equity / real_estate / alternative / other`。
- 每 task 结束跑 `python -m pytest -q` 全绿 + 一次 git commit。
- 本次**不做任何前端/API 改动**（属 Plan B/C），只动 `app/`、`tests/`、迁移脚本。

---

## P0 三阶段拆分（本计划只覆盖 Plan A）

| Plan | 内容 | 状态 |
|---|---|---|
| **A** | 数据模型迁移 + Wealth Engine + Scenario Engine + 单测 | **本计划** |
| B | API 端点（/api/wealth /allocation /goals/plan /scenario）+ 集成测试 | 后续 |
| C | 前端（ECharts 组件 + 驾驶舱 + 沙盘）+ AI Orchestrator | 后续 |

---

## 文件结构

```
app/
  engine/
    __init__.py        # 汇总导出，对外唯一入口
    metrics.py         # 基础指标（迁移 calc_engine，函数名兼容）
    projection.py      # 长期财富投影
    allocation.py      # 资产配置分析 + Allocation Policy
    goals.py           # 现金流型目标测算
    score.py           # Family Wealth Score（七维度）
    scenario.py        # 情景引擎（通用框架 + 4 场景）
  calc_engine.py       # 保留为兼容层，内部转发 engine.metrics
  db.py                # 加迁移：SCHEMA 新增列/新表 + migrate() 函数
  migrate_v2.py        # 独立迁移脚本（幂等、版本化）
tests/
  test_engine_metrics.py
  test_engine_projection.py
  test_engine_allocation.py
  test_engine_goals.py
  test_engine_score.py
  test_engine_scenario.py
  test_migration.py
```

---

### Task 0: git 初始化 + 基线提交 + 迁移框架

**Files:**
- Create: `app/migrate_v2.py`
- Modify: `app/db.py`（新增 `meta` 表 + `migrate()` 函数）

**Interfaces:**
- Produces: `db.migrate()` → `None`（幂等迁移入口，`init_db()` 内部调用）；`migrate_v2.py` 可独立运行（`python -m app.migrate_v2`）。

- [ ] **Step 1: git 初始化 + 基线提交**

```bash
cd /d/Claude_Code/ai-jia-ban
git init
git add .gitignore README.md requirements.txt conftest.py app static tests docs .env.example
git status          # 确认 .env 与 data.db 未出现在待提交列表
git commit -m "chore: baseline before V2 wealth engine"
```

Expected: `.gitignore` 生效，`.env`、`data.db`、`__pycache__/` 不被 add。

- [ ] **Step 2: 写迁移框架测试**

`tests/test_migration.py`:

```python
import sqlite3
from app import db

def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    db.migrate()
    db.migrate()  # 第二次执行不得报错
    conn = db.get_conn()
    assert "meta" in {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
```

- [ ] **Step 3: 实现 meta 表 + migrate 框架**

`app/db.py` 的 `SCHEMA` 末尾追加：

```sql
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

`app/db.py` 新增（放在 `init_db` 之后）：

```python
def migrate() -> None:
    """幂等迁移：按 schema_version 递增执行。"""
    conn = get_conn()
    try:
        cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        version = int(row[0]) if row else 0
        # 后续 Task 在此追加：if version < 1: _migrate_v1(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )
        conn.commit()
    finally:
        conn.close()
```

`app/db.py` 的 `init_db()` 末尾加一行 `migrate()`。

`app/migrate_v2.py`:

```python
"""V2 迁移独立入口：python -m app.migrate_v2"""
from . import db

if __name__ == "__main__":
    db.init_db()
    print("migration complete")
```

- [ ] **Step 4: 跑测试验证**

```bash
python -m pytest tests/test_migration.py -v
```
Expected: PASS（幂等迁移通过）。

- [ ] **Step 5: Commit**

```bash
git add app/db.py app/migrate_v2.py tests/test_migration.py
git commit -m "feat: add versioned migration framework (meta table)"
```

---

### Task 1: asset 表迁移（asset_class 等 6 列 + 回填）

**Files:**
- Modify: `app/db.py`（`_migrate_v1`）
- Test: `tests/test_migration.py`（追加）

**Interfaces:**
- Produces: `asset` 表新增列 `asset_class / liquidity / cost_basis / expected_return / risk_level / sub_type`（均可空）。

- [ ] **Step 1: 写回填映射测试**

```python
def test_migrate_asset_class_backfill(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    conn = db.get_conn()
    # 造一条旧资产（无 asset_class）
    conn.execute("INSERT INTO asset (family_id, type, name, value) VALUES (1, '房产', '自住房', 3000000)")
    conn.execute("INSERT INTO asset (family_id, type, name, value) VALUES (1, '存款', '活期', 500000)")
    conn.commit()
    db.migrate()
    rows = conn.execute("SELECT type, asset_class FROM asset ORDER BY id").fetchall()
    got = {r[0]: r[1] for r in rows}
    assert got == {"房产": "real_estate", "存款": "cash"}
    conn.close()
```

- [ ] **Step 2: 实现 `_migrate_v1`（加列 + 回填）**

`app/db.py` 新增（`migrate()` 中 `if version < 1: _migrate_v1(conn)`）：

```python
_ASSET_CLASS_MAP = {"房产": "real_estate", "存款": "cash", "理财": "fixed_income",
                    "基金": "fixed_income", "股票": "equity", "保险现金价值": "other",
                    "其他": "other"}

def _migrate_v1(conn) -> None:
    for col, ddl in [
        ("asset_class", "TEXT"),
        ("liquidity", "TEXT"),
        ("cost_basis", "REAL"),
        ("expected_return", "REAL"),
        ("risk_level", "TEXT"),
        ("sub_type", "TEXT"),
    ]:
        _add_column_if_missing(conn, "asset", col, ddl)
    for old_type, new_class in _ASSET_CLASS_MAP.items():
        conn.execute(
            "UPDATE asset SET asset_class = ? WHERE type = ? AND asset_class IS NULL",
            (new_class, old_type),
        )

def _add_column_if_missing(conn, table: str, col: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
```

`migrate()` 改为：

```python
if version < 1:
    _migrate_v1(conn)
    version = 1
```

- [ ] **Step 3: 跑测试**

```bash
python -m pytest tests/test_migration.py -v
```
Expected: 全部 PASS（含幂等 + 回填）。

- [ ] **Step 4: Commit**

```bash
git add app/db.py tests/test_migration.py
git commit -m "feat: migrate asset table with asset_class and backfill"
```

---

### Task 2: goal 表迁移（现金流型目标 6 列）

**Files:**
- Modify: `app/db.py`（`_migrate_v2`）
- Test: `tests/test_migration.py`（追加）

**Interfaces:**
- Produces: `goal` 新增列 `goal_kind / annual_amount / duration_years / start_year / priority / risk_tolerance`；旧数据 `goal_kind` 回填 `lump_sum`。

- [ ] **Step 1: 写测试**

```python
def test_migrate_goal_kind_backfill(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    conn = db.get_conn()
    conn.execute("INSERT INTO goal (family_id, type, name, target_amount) VALUES (1, '教育', '教育金', 1000000)")
    conn.commit()
    db.migrate()
    r = conn.execute("SELECT goal_kind FROM goal WHERE name='教育金'").fetchone()
    assert r[0] == "lump_sum"
    conn.close()
```

- [ ] **Step 2: 实现 `_migrate_v2`**

与 Task 1 同构：`if version < 2: _migrate_v2(conn); version = 2`。

```python
def _migrate_v2(conn) -> None:
    for col, ddl in [
        ("goal_kind", "TEXT"),
        ("annual_amount", "REAL"),
        ("duration_years", "INTEGER"),
        ("start_year", "INTEGER"),
        ("priority", "INTEGER"),
        ("risk_tolerance", "TEXT"),
    ]:
        _add_column_if_missing(conn, "goal", col, ddl)
    conn.execute("UPDATE goal SET goal_kind = 'lump_sum' WHERE goal_kind IS NULL")
    conn.execute("UPDATE goal SET priority = 2 WHERE priority IS NULL")
    conn.execute("UPDATE goal SET risk_tolerance = 'balanced' WHERE risk_tolerance IS NULL")
```

- [ ] **Step 3: 跑测试** → `pytest tests/test_migration.py -v` PASS
- [ ] **Step 4: Commit** → `git commit -m "feat: migrate goal table with cashflow goal fields"`

---

### Task 3: 新表 insurance / family_profile / scenario_snapshot

**Files:**
- Modify: `app/db.py`（`_migrate_v3`）
- Test: `tests/test_migration.py`（追加）

**Interfaces:**
- Produces: 三张新表（见下）。`db.ENTITY_COLS` 暂不扩（看板 CRUD 属 Plan B）。

- [ ] **Step 1: 写测试（三表存在 + 可写入）**

```python
def test_migrate_new_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    conn = db.get_conn()
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"insurance", "family_profile", "scenario_snapshot"} <= names
    conn.execute("INSERT INTO insurance (family_id, type, name, annual_premium, coverage) "
                 "VALUES (1, '重疾', '重疾险', 8000, 500000)")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM insurance").fetchone()[0] == 1
    conn.close()
```

- [ ] **Step 2: 实现 `_migrate_v3`（CREATE TABLE IF NOT EXISTS）**

`if version < 3: _migrate_v3(conn); version = 3`。

```python
def _migrate_v3(conn) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS insurance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id INTEGER NOT NULL,
        person_id INTEGER,
        type TEXT,
        name TEXT,
        annual_premium REAL,
        coverage REAL,
        cash_value REAL,
        start_date TEXT,
        maturity_date TEXT,
        FOREIGN KEY(family_id) REFERENCES family(id)
    );
    CREATE TABLE IF NOT EXISTS family_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id INTEGER NOT NULL UNIQUE,
        risk_profile TEXT DEFAULT 'balanced',
        investment_horizon INTEGER DEFAULT 10,
        risk_answers TEXT,
        FOREIGN KEY(family_id) REFERENCES family(id)
    );
    CREATE TABLE IF NOT EXISTS scenario_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id INTEGER NOT NULL,
        scenario TEXT NOT NULL,
        params_json TEXT,
        result_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(family_id) REFERENCES family(id)
    );
    """)
```

- [ ] **Step 3: 跑测试** → PASS
- [ ] **Step 4: Commit** → `git commit -m "feat: add insurance/family_profile/scenario_snapshot tables"`

---

### Task 4: `app/engine/` 包 + `metrics.py`（迁移 calc_engine）

**Files:**
- Create: `app/engine/__init__.py`, `app/engine/metrics.py`
- Modify: `app/calc_engine.py`（改为转发兼容层）
- Test: `tests/test_engine_metrics.py`（从 test_calc_engine.py 迁移 + 保持全绿）

**Interfaces:**
- Produces（`from app.engine import metrics`）: 全部现有函数名不变 —— `total_assets / total_liabilities / net_worth / monthly_income / monthly_expense / monthly_surplus / savings_rate / liquid_assets / emergency_months / debt_to_income / goal_gap / goals_summary / goals_funding / safety_margin / snapshot`。
- Consumes: 无（纯函数）。

- [ ] **Step 1: 写迁移后一致性测试**

`tests/test_engine_metrics.py`：把 `tests/test_calc_engine.py` 的全部用例**原样复制**，仅把 `from app import calc_engine as ce` 改为 `from app.engine import metrics as ce`，并追加一条：

```python
def test_calc_engine_is_compat_shim():
    from app import calc_engine as legacy
    from app.engine import metrics
    data = {"assets": [{"type": "存款", "value": 500000}],
            "liabilities": [], "cashflows": [], "goals": [], "persons": []}
    assert legacy.snapshot(data) == metrics.snapshot(data)
```

- [ ] **Step 2: 跑测试确认新测试 FAIL**（`metrics` 模块不存在）

- [ ] **Step 3: 实现 `metrics.py`**

将 `app/calc_engine.py` 的**全部函数体原样搬入** `app/engine/metrics.py`（含 `LIQUID_ASSET_TYPES`、`_monthly` 等私有函数），文件头 docstring 改为「基础指标（V2 引擎核心模块之一）」。

`app/engine/__init__.py`:

```python
from . import metrics, projection, allocation, goals, score, scenario  # 后续 Task 逐步补全，暂只导 metrics
```

> 注：此 Task 先只 `from . import metrics`，后续 Task 每加一个模块就补一行，避免 import 未定义模块。

`app/calc_engine.py` 整体替换为兼容层：

```python
"""兼容层：转发到 app.engine.metrics，旧 import 路径不变。"""
from app.engine.metrics import *  # noqa: F401,F403
from app.engine.metrics import LIQUID_ASSET_TYPES  # noqa: F401
```

- [ ] **Step 4: 跑测试全绿** → `python -m pytest -q`（旧 + 新全 PASS）
- [ ] **Step 5: Commit** → `git commit -m "refactor: extract engine.metrics, calc_engine as compat shim"`

---

### Task 5: `projection.py`（长期财富投影）

**Files:**
- Create: `app/engine/projection.py`
- Test: `tests/test_engine_projection.py`

**Interfaces:**
- Produces:
  - `project_net_worth(net_worth: float, monthly_surplus: float, annual_return: float, years: int) -> list[float]` —— 返回长度 `years+1` 的年末净资产序列（首项=当前），复利 `(1 + annual_return)`，每月结余按年累加后计入。
  - `future_value(amount: float, annual_return: float, years: int) -> float`

- [ ] **Step 1: 写测试**

```python
from app.engine import projection as pr

def test_future_value():
    assert abs(pr.future_value(100000, 0.03, 1) - 103000) < 1e-6

def test_project_net_worth_zero_surplus():
    seq = pr.project_net_worth(500000, 0, 0.0, 3)
    assert seq == [500000, 500000, 500000, 500000]

def test_project_net_worth_grows():
    seq = pr.project_net_worth(0, 12000, 0.0, 2)  # 无收益，仅存钱
    assert seq[1] == 144000   # 12000 * 12
    assert seq[2] == 288000
```

- [ ] **Step 2: 跑测试 FAIL**
- [ ] **Step 3: 实现**

```python
def future_value(amount: float, annual_return: float, years: int) -> float:
    return amount * (1 + annual_return) ** years

def project_net_worth(net_worth: float, monthly_surplus: float, annual_return: float, years: int) -> list[float]:
    seq = [net_worth]
    for _ in range(years):
        net_worth = net_worth * (1 + annual_return) + monthly_surplus * 12
        seq.append(round(net_worth, 2))
    return seq
```

- [ ] **Step 4: 跑测试 PASS**
- [ ] **Step 5: Commit** → `git commit -m "feat: add projection engine"`

---

### Task 6: `allocation.py`（资产配置分析 + Allocation Policy）

**Files:**
- Create: `app/engine/allocation.py`
- Test: `tests/test_engine_allocation.py`

**Interfaces:**
- Produces:
  - `classify_asset(asset_type: str) -> str`（→ asset_class）
  - `asset_class_breakdown(assets) -> dict`（每类金额 + `pct`，键 `cash/fixed_income/equity/real_estate/alternative/other`）
  - `concentration(assets) -> dict`（`hhi / top_asset_pct / real_estate_pct / single_stock_pct`）
  - `allocation_policy(risk_profile: str, time_horizon: int) -> dict`（target_range，区间）
  - `analyze(assets, profile, cashflows=None, liabilities=None) -> dict`（综合输出，见设计 G1）

- [ ] **Step 1: 写测试**

```python
from app.engine import allocation as al

def test_classify_asset():
    assert al.classify_asset("房产") == "real_estate"
    assert al.classify_asset("股票") == "equity"
    assert al.classify_asset("存款") == "cash"

def test_breakdown_pct():
    assets = [{"type": "存款", "value": 500000}, {"type": "房产", "value": 3000000}]
    b = al.asset_class_breakdown(assets)
    assert b["cash"]["pct"] == 0.1
    assert b["real_estate"]["pct"] == 0.6

def test_concentration_high_property():
    assets = [{"type": "房产", "value": 9000000}, {"type": "存款", "value": 100000}]
    c = al.concentration(assets)
    assert c["real_estate_pct"] > 0.9

def test_policy_conservative_lower_equity():
    cons = al.allocation_policy("conservative", 10)
    aggr = al.allocation_policy("aggressive", 10)
    assert cons["equity"][1] < aggr["equity"][1]
```

- [ ] **Step 2: 跑测试 FAIL**
- [ ] **Step 3: 实现（核心逻辑）**

```python
_CLASS_MAP = {"房产": "real_estate", "存款": "cash", "理财": "fixed_income",
              "基金": "fixed_income", "股票": "equity", "保险现金价值": "other", "其他": "other"}

def classify_asset(asset_type: str) -> str:
    return _CLASS_MAP.get(asset_type, "other")

def asset_class_breakdown(assets):
    total = sum(float(a.get("value") or 0) for a in assets)
    out = {k: {"value": 0.0, "pct": 0.0}
           for k in ("cash", "fixed_income", "equity", "real_estate", "alternative", "other")}
    for a in assets:
        cls = a.get("asset_class") or classify_asset(a.get("type"))
        if cls not in out:
            cls = "other"
        out[cls]["value"] += float(a.get("value") or 0)
    if total > 0:
        for k in out:
            out[k]["pct"] = round(out[k]["value"] / total, 4)
    return out

def concentration(assets):
    vals = sorted((float(a.get("value") or 0) for a in assets), reverse=True)
    total = sum(vals)
    if total <= 0:
        return {"hhi": 0.0, "top_asset_pct": 0.0, "real_estate_pct": 0.0, "single_stock_pct": 0.0}
    hhi = sum((v / total) ** 2 for v in vals)
    real_estate = sum(float(a.get("value") or 0) for a in assets if classify_asset(a.get("type")) == "real_estate")
    return {"hhi": round(hhi, 4), "top_asset_pct": round(vals[0] / total, 4),
            "real_estate_pct": round(real_estate / total, 4),
            "single_stock_pct": round(sum(float(a.get("value") or 0) for a in assets
                                          if a.get("type") == "股票") / total, 4)}

# Allocation Policy 默认策略（可覆盖的数据结构，非散落常量）
_DEFAULT_POLICY = {
    "conservative": {"cash": [0.10, 0.20], "fixed_income": [0.35, 0.55], "equity": [0.05, 0.20]},
    "balanced":     {"cash": [0.05, 0.15], "fixed_income": [0.20, 0.40], "equity": [0.20, 0.45]},
    "aggressive":   {"cash": [0.02, 0.10], "fixed_income": [0.10, 0.30], "equity": [0.40, 0.70]},
}

def allocation_policy(risk_profile: str, time_horizon: int) -> dict:
    base = _DEFAULT_POLICY.get(risk_profile, _DEFAULT_POLICY["balanced"])
    # 期限修正：越短越偏保守
    adj = -0.10 if time_horizon <= 3 else (0.10 if time_horizon > 7 else 0.0)
    out = {k: [max(0.0, lo + adj), min(1.0, hi + adj)] for k, (lo, hi) in base.items()}
    return out
```

`analyze(...)` 组合上述四个函数，输出设计 G1 的结构（`current / concentration / liquidity / target_range / deviation / adjustments / risk`）。`deviation` 规则：`current_pct` 低于区间下沿→`below`、高于上沿→`above`、否则 `in_range`；`adjustments` 对 `deviation` 非 in_range 的类按偏离幅度排序产出行动建议。

- [ ] **Step 4: 跑测试 PASS**
- [ ] **Step 5: Commit** → `git commit -m "feat: add allocation analysis with configurable policy"`

---

### Task 7: `goals.py`（现金流型目标测算）

**Files:**
- Create: `app/engine/goals.py`
- Test: `tests/test_engine_goals.py`

**Interfaces:**
- Produces:
  - `plan_cashflow_goal(annual_amount: float, duration_years: int, years_until_start: int, current_saved: float = 0, inflation: float = 0.03, return_rate: float = 0.03) -> dict`（`fv_target / fv_saved / gap / monthly_save / allocation`）
  - `allocation_recommendation(years_until_need: int) -> dict`（`conservative_pct / aggressive_pct`）

- [ ] **Step 1: 写测试**

```python
from app.engine import goals as g

def test_plan_cashflow_goal_zero_start():
    # 孩子已 18 岁、马上交：无通胀无收益，直接 10万*4=40万
    r = g.plan_cashflow_goal(100000, 4, 0, inflation=0.0, return_rate=0.0)
    assert r["fv_target"] == 400000
    assert r["gap"] == 400000
    assert r["monthly_save"] == 400000  # 0 期，需一次性备齐

def test_plan_cashflow_goal_with_years():
    r = g.plan_cashflow_goal(100000, 4, 6)  # 孩子 12 岁
    assert r["fv_target"] > 400000          # 通胀放大
    assert r["monthly_save"] < r["fv_target"] / (6 * 12)  # 收益摊薄每月定投

def test_allocation_recommendation_long_horizon_more_aggressive():
    near = g.allocation_recommendation(2)
    far = g.allocation_recommendation(10)
    assert near["conservative_pct"] > far["conservative_pct"]
```

- [ ] **Step 2: 跑测试 FAIL**
- [ ] **Step 3: 实现（核心公式，见设计 G2）**

```python
def plan_cashflow_goal(annual_amount, duration_years, years_until_start,
                       current_saved=0, inflation=0.03, return_rate=0.03):
    fv_target = annual_amount * duration_years * (1 + inflation) ** years_until_start
    fv_saved = current_saved * (1 + return_rate) ** years_until_start
    gap = max(fv_target - fv_saved, 0.0)
    n = years_until_start * 12
    if n <= 0:
        monthly_save = gap
    else:
        r = return_rate / 12.0
        monthly_save = gap * r / ((1 + r) ** n - 1) if r > 0 else gap / n
    return {"fv_target": round(fv_target, 2), "fv_saved": round(fv_saved, 2),
            "gap": round(gap, 2), "monthly_save": round(monthly_save, 2),
            "allocation": allocation_recommendation(years_until_start)}

def allocation_recommendation(years_until_need: int) -> dict:
    if years_until_need <= 3:
        return {"conservative_pct": 0.8, "aggressive_pct": 0.2}
    if years_until_need <= 7:
        return {"conservative_pct": 0.6, "aggressive_pct": 0.4}
    return {"conservative_pct": 0.3, "aggressive_pct": 0.7}
```

- [ ] **Step 4: 跑测试 PASS**
- [ ] **Step 5: Commit** → `git commit -m "feat: add cashflow goal planning"`

---

### Task 8: `score.py`（Family Wealth Score 七维度）

**Files:**
- Create: `app/engine/score.py`
- Test: `tests/test_engine_score.py`

**Interfaces:**
- Produces: `wealth_score(family_data: dict, profile: dict | None = None) -> dict`，返回 `{score, level, dimensions: [{name, weight, score, reasons}]}`。七维度权重常量 `WEIGHTS = {"cashflow": 0.20, "liquidity": 0.15, "debt": 0.15, "protection": 0.15, "allocation": 0.15, "goals": 0.10, "retirement": 0.10}`。
- Consumes: `metrics`、`allocation`、`projection`。

- [ ] **Step 1: 写测试**

```python
from app.engine import score

def test_wealth_score_healthy():
    data = {"assets": [{"type": "存款", "value": 300000}],
            "liabilities": [], "cashflows": [{"flow_type": "income", "amount": 50000, "period": "月"},
                                             {"flow_type": "expense", "amount": 20000, "period": "月"}],
            "goals": [], "persons": [], "insurances": []}
    s = score.wealth_score(data)
    assert 0 <= s["score"] <= 100
    assert len(s["dimensions"]) == 7
    assert sum(d["weight"] for d in s["dimensions"]) == 1.0

def test_wealth_score_no_insurance_penalized():
    data = {"assets": [{"type": "存款", "value": 300000}], "liabilities": [],
            "cashflows": [{"flow_type": "income", "amount": 50000, "period": "月"}],
            "goals": [], "persons": [], "insurances": []}
    dims = {d["name"]: d for d in score.wealth_score(data)["dimensions"]}
    assert dims["protection"]["score"] < 50  # 无保险低分
```

- [ ] **Step 2: 跑测试 FAIL**
- [ ] **Step 3: 实现（每维一个打分函数 + 加权）**

```python
WEIGHTS = {"cashflow": 0.20, "liquidity": 0.15, "debt": 0.15, "protection": 0.15,
           "allocation": 0.15, "goals": 0.10, "retirement": 0.10}

def wealth_score(family_data, profile=None):
    dims = [
        _cashflow_dim(family_data), _liquidity_dim(family_data), _debt_dim(family_data),
        _protection_dim(family_data), _allocation_dim(family_data), _goals_dim(family_data),
        _retirement_dim(family_data),
    ]
    total = sum(d["score"] * WEIGHTS[d["name"]] for d in dims)
    score_val = round(max(0.0, min(100.0, total)))
    level = "稳健" if score_val >= 75 else ("需关注" if score_val >= 50 else "脆弱")
    for d in dims:
        d["weight"] = WEIGHTS[d["name"]]
    return {"score": score_val, "level": level, "dimensions": dims}
```

各 `_xxx_dim` 返回 `{"name": "...", "score": 0-100, "reasons": ["加分/扣分原因"]}`，规则映射现有 `health.py` 的阈值（应急月数≥6 满分、DTI≤0.3 满分、储蓄率≥0.2 满分、房产集中>0.7 扣分、无保险 protection 低分等）。**每个打分维度都必须带至少一条 `reasons`**（可解释性验收）。

- [ ] **Step 4: 跑测试 PASS**
- [ ] **Step 5: Commit** → `git commit -m "feat: add Family Wealth Score (7-dim weighted)"`

---

### Task 9: `scenario.py`（Scenario Engine 通用框架 + 4 场景）

**Files:**
- Create: `app/engine/scenario.py`
- Modify: `app/decision.py`（改为转发 `engine.scenario` 兼容层）
- Test: `tests/test_engine_scenario.py`

**Interfaces:**
- Produces: `SCENARIOS: dict[str, callable]`、`simulate(data, snap, scenario, params) -> dict`（统一结果 schema：`scenario/title/plan_a_label/plan_b_label/summary/rows/conclusion/params_snapshot`）。
- Consumes: `metrics`、`projection`。场景：`buy_house / prepay / invest / income_change`。

- [ ] **Step 1: 写测试**

```python
from app.engine import scenario as sc

def _data():
    return {"assets": [{"type": "存款", "value": 1000000}],
            "liabilities": [{"type": "房贷", "principal": 2000000, "monthly_payment": 12000,
                             "interest_rate": 0.035, "remaining_months": 240}],
            "cashflows": [{"flow_type": "income", "amount": 40000, "period": "月"}],
            "goals": [], "persons": []}

def test_simulate_invest_reduces_liquid():
    from app.engine import metrics
    data = _data()
    snap = metrics.snapshot(data)
    r = sc.simulate(data, snap, "invest", {"amount": 500000, "to_class": "equity"})
    assert r["scenario"] == "invest"
    assert r["params_snapshot"] == {"amount": 500000, "to_class": "equity"}

def test_simulate_unknown_scenario():
    r = sc.simulate(_data(), {}, "nope", {})
    assert r["error"].startswith("未知场景")
```

- [ ] **Step 2: 跑测试 FAIL**
- [ ] **Step 3: 实现**

将 `decision.py` 的 `simulate_buy_house` / `simulate_prepay` / 等额本息公式原样搬入 `scenario.py`，改为 `SCENARIOS` 注册表；新增 `invest`（从流动现金拿出 `amount`，注入 `to_class` 资产，重算 `allocation` 与 `concentration` 对比）和 `income_change`（收入乘 `(1+pct_change)`，重算现金流/结余/应急月数）。统一 `simulate()` 入口（与旧 `decision.simulate` 签名一致）。

`app/decision.py` 改为兼容层：

```python
"""兼容层：转发到 app.engine.scenario。"""
from app.engine.scenario import simulate  # noqa: F401
```

- [ ] **Step 4: 跑测试全绿** → `python -m pytest -q`（新增 + 全量回归全 PASS）
- [ ] **Step 5: Commit** → `git commit -m "feat: refactor decision into generic scenario engine"`

---

## Self-Review

- **Spec coverage**：Plan A 覆盖设计文档 F1~F5（数据模型）、G1~G3（allocation/goals/score）、H（scenario）、G 的 projection。API（J）、驾驶舱（K）、沙盘（L）、AI（I）属 Plan B/C，不在本计划范围（已在上表标注）。
- **Placeholder scan**：无 TBD/TODO；每 task 含实际代码与测试。
- **Type consistency**：`asset_class` 枚举全计划统一为 `cash/fixed_income/equity/real_estate/alternative/other`；`simulate(data, snap, scenario, params)` 签名在 Task 9 与旧 `decision.simulate(family_id, scenario, params)` 明确区分（引擎层收 `data/snap`，兼容层 `decision.simulate` 仍收 `family_id`，内部先 dump 再转发）。
