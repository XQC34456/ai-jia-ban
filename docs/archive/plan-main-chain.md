# 主链收口实现计划（家庭驾驶舱 + 风险地图 + 行动计划 + 动态重评估）

> 目标：把「数据变化 → 重新评估」串上 UI、补上「行动计划」、把「风险列表」升级为「风险地图」。
> 铁律不变：财富数字一律确定性计算（Engine/Decision），LLM 绝不计算/编造；本计划零改动 Engine/Decision 核心逻辑。

## 现状与断点（诊断结论）

| 主链环节 | 落点 | 状态 |
|---|---|---|
| 家庭驾驶舱 | overview.js + overview.py | ✅ 完整 |
| 风险地图 | detect.py（7 维）+ issues.js | 🟡 前端是平铺列表，非「地图」 |
| 行动计划 | — | 🔴 缺失（建议是一次性文字，无采纳/跟踪） |
| 动态重评估 | memory.py `detect_invalidation` | 🟡 后端完整，但仅在 AI 对话触发、用户不可见 |

**两个真断点 + 一个打磨点：**
- **断点 A**：数据变了 → 用户没感觉，只有下次问 AI 才知道「上次判断失效了」。
- **断点 B**：方案建议（⑤）→ 没有可跟踪的「计划」，闭环断在建议，走不到「行动计划 → 数据变化 → 重新评估」。
- **打磨点 C**：issues.js 平铺，缺「地图」视角（7 维已有，象限未接前端）。

---

## 动作 1：重评估可视化（数据变化 → 重新评估）

### Task 1（后端）：`review-status` 端点

**文件：**
- 修改 `app/agent/memory.py`
- 修改 `app/api/wealth.py`
- 测试 `tests/test_review_status.py`（新建）

**改动：**
1. `memory.py` 把私有 `_INVALIDATION_LABELS` 暴露为 `INVALIDATION_LABELS`（保留原名引用，避免破坏现有 `build_memory_context`）。
2. 抽公共 diff 函数，让「失效检测」与「状态查询」共用同一套取数口径：
   ```python
   def _diff_conditions(conds: dict, current: dict) -> list[dict]:
       """逐 key 对比有效性条件 vs 当前值，返回 [{key, before, after}]。"""
       out = []
       for k, before in (conds or {}).items():
           after = current.get(k)
           if after is not None and after != before:
               out.append({"key": k, "before": before, "after": after})
       return out
   ```
   `detect_invalidation` 内部改用 `_diff_conditions`（行为不变，仍会 invalidate）。
3. 新增 `build_review_status(family_id) -> dict`（纯函数，只读 + 触发失效标记）：
   ```python
   def build_review_status(family_id: int) -> dict:
       j = db.latest_judgment(family_id)
       if j is None:
           return {"has_judgment": False, "status": None, "stale_reasons": []}
       detect_invalidation(family_id)            # active 且变化 → 标记 stale
       data = db.dump_family(family_id)
       current = build_validity_conditions(build_overview(data))
       reasons = [{"key": c["key"], "label": INVALIDATION_LABELS.get(c["key"], c["key"]),
                   "before": c["before"], "after": c["after"]}
                  for c in _diff_conditions(j["validity_conditions"], current)]
       j2 = db.latest_judgment(family_id)         # 取 invalidate 后的最新 status
       return {"has_judgment": True, "status": j2["status"], "stale_reasons": reasons}
   ```
   要点：`stale_reasons` 独立于 `detect_invalidation` 的一次性返回值计算，**即使判断早已 stale，也能持续显示「哪些维度变了」**（对比 validity_conditions 与当前值）。
4. `wealth.py` 加端点：
   ```python
   from ..agent.memory import build_review_status

   @router.get("/review-status")
   def wealth_review_status(user: dict = Depends(get_current_user)):
       return build_review_status(user["family_id"])
   ```

**测试（`tests/test_review_status.py`）：**
- `test_no_judgment`：无判断家庭 → `has_judgment is False, status is None, stale_reasons == []`。
- `test_stale_after_data_change`：先 `save_judgment`（active），改现金流使 `cashflow_surplus` 变化 → `build_review_status` 返回 `status == "stale"` 且 `stale_reasons` 含 `cashflow_surplus` 项（before/after 正确）。
- `test_stale_reasons_persist`：失效后再次调用 → `status == "stale"` 且 `stale_reasons` 仍含变化项（证明原因不丢）。
- `test_no_change_stays_active`：不改数据 → `status == "active"`、`stale_reasons == []`。

**验证：** `pytest tests/test_review_status.py -v` 全绿 + `pytest -q` 全量回归无红。

---

### Task 2（前端）：overview 重评估横幅

**文件：**
- 修改 `static/store.js`
- 修改 `static/views/overview.js`

**改动：**
1. `store.js`：
   - 切片加 `review: { data: null, loading: false, error: null }`。
   - 加 `loadReview()`：GET `/api/wealth/review-status`。
   - `logout()` 里清 `store.review.data = null`。
2. `overview.js`：
   - `onMounted` 里 `ensureOverview()` 之外加 `loadReview()`。
   - 模板顶部（`report-banner` 之前）加横幅：
     ```html
     <div v-if="store.review.data && store.review.data.status === 'stale'" class="stale-banner">
       ⚠️ 你的家庭数据已变化，上次建议可能过时：
       <span v-for="r in store.review.data.stale_reasons" :key="r.key" class="stale-chip">
         {{ r.label }} {{ $money(r.before) }} → {{ $money(r.after) }}
       </span>
       <button class="btn-primary btn-sm" @click="navigate('chat')">去 AI 顾问重新评估</button>
     </div>
     ```
   - setup 里引入 `navigate`。
   - 无 `stale_reasons` 时退化为一条「上次判断已失效，请重新评估」提示（文案兜底）。

**验证：** 本地起服务，登录一个「已问过 AI 顾问 → 改数据」的测试家庭，确认 overview 顶部出现失效横幅、维度前后值正确、按钮跳转 chat。

---

## 动作 2：行动计划落地

### Task 3（后端）：`action_plan` 表 + CRUD + API

**文件：**
- 修改 `app/db.py`
- 修改 `app/api/wealth.py`
- 测试 `tests/test_action_plan.py`（新建）

**改动：**
1. `db.py` 加 `_migrate_v6`（在 `init_db` 里追加调用）：
   ```sql
   CREATE TABLE IF NOT EXISTS action_plan (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       family_id INTEGER NOT NULL,
       issue_id TEXT,
       action TEXT NOT NULL,
       detail TEXT,
       status TEXT NOT NULL DEFAULT 'todo',
       created_at TEXT NOT NULL,
       updated_at TEXT NOT NULL,
       FOREIGN KEY(family_id) REFERENCES family(id)
   )
   ```
2. CRUD（沿用 `_insert` / `_rows` / `_now` 既有 helper）：
   ```python
   def create_action_plan(family_id, issue_id, action, detail) -> int | None:
       # 去重：同 family + issue_id + action 且 status='todo' 已存在 → 返回 None（不重复采纳）
   def list_action_plan(family_id) -> list[dict]:      # 按 id 正序，含 issue_id/action/detail/status
   def update_action_plan_status(plan_id, status) -> None:  # status ∈ {todo, done, skipped}
   ```
3. `wealth.py` 加端点（复用 `get_current_user`）：
   - `GET  /api/wealth/action-plan` → `{"plans": [...]}`
   - `POST /api/wealth/action-plan` body `{issue_id, action, detail}` → `{"id": int}` 或 `{"id": None}`（已存在）
   - `PUT  /api/wealth/action-plan/{plan_id}` body `{status}` → 更新（校验 status 白名单）

**测试（`tests/test_action_plan.py`）：**
- `test_create_and_list`：采纳两条 → 列表长度 2，字段正确。
- `test_dedup`：同 issue_id+action 采纳两次 → 只 1 条，第二次返回 `id is None`。
- `test_update_status`：创建后 `update_action_plan_status(id, "done")` → 列表里 status 变 done。
- `test_status_whitelist`：非法 status → 不落库（或抛错）。

**验证：** `pytest tests/test_action_plan.py -v` 全绿 + 全量回归。

---

### Task 4（前端）：风险地图 + 行动计划（issues 视图升级）

**文件：**
- 修改 `static/store.js`
- 修改 `static/views/issues.js`
- 修改 `static/format.js`（加维度标签常量，可选）

**改动：**
1. `format.js` 加维度标签（与 detect.py 的 7 个 type 对齐）：
   ```js
   export const ISSUE_DIM_LABELS = {
     cashflow: '现金流', liquidity: '流动性', debt: '负债',
     allocation: '资产配置', retirement: '养老', goals: '目标', decision: '闲置资金',
   };
   export const ISSUE_DIM_ORDER = ['cashflow', 'liquidity', 'debt', 'allocation', 'retirement', 'goals', 'decision'];
   ```
2. `store.js` 加切片 `actionPlan: { data: null, loading: false, error: null }` + `loadActionPlan()` / `adoptAction(payload)` / `setActionStatus(id, status)`。
3. `issues.js` 重构为「风险地图 + 行动计划」合一视图（**不新增 nav 项**）：
   - 上半「风险地图」：按 `ISSUE_DIM_ORDER` 把 `store.issues.data.issues` 分组，每组显示维度标签 + 该维度问题数 + 问题列表（复用现有 `sevTone`/`scenarioLabel`/`simulate`）。无问题的维度显示「健康」灰态。
   - 每条 issue 的 `recommendations` 加「采纳」按钮：
     - 已采纳（actionPlan 里已有同 issue_id+action 的 todo 项）→ 显示「已加入计划」灰态。
     - 否则点击 → `adoptAction({issue_id, action, detail})` → 刷新 actionPlan。
   - 下半「我的行动计划」：`store.actionPlan.data.plans` 列表，每条可勾选完成（`setActionStatus(id, 'done')`）/ 恢复待办，状态着色（todo/done/skipped）。
4. 复用现有 CSS 类（`panel`/`insight-item`/`rec-item`/`chip`），新增少量样式走项目现有 style 约定（不引入新依赖）。

**验证：** 本地起服务截图验证：风险地图按 7 维分组显示、采纳按钮入库、行动计划勾选完成状态切换、空数据/全健康态展示正常。

---

## 执行顺序与依赖

```
Task 1（后端 review-status） ──► Task 2（前端横幅）
Task 3（后端 action-plan）  ──► Task 4（前端风险地图+计划）
```

- Task 1、Task 3 相互独立，可并行；Task 2 依赖 1，Task 4 依赖 3。
- 建议按 1→2→3→4 顺序执行（后端先行，前端随后验证）。

## 全局约束

- 零改动 Engine/Decision 核心逻辑（`engine/*`、`decision/detect.py`、`decision/issue.py` 的检测/排序/建议生成不动）。
- 财富数字一律确定性计算；新增的 `stale_reasons`（before/after）来自确定性 diff，LLM 不参与。
- 不自动 commit（除非你明确要求）。
- 产出在 `D:\Claude_Code\ai-jia-ban`，测试用项目现有 `pytest` 体系。
