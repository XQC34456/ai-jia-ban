# C3 Wealth Sandbox 实施计划（财富决策沙盘 · 决策体验层）

> 定位：把「已冻结的对比引擎」升级成「让普通家庭能做决定的沙盘」。**只出方案，不写实现代码**，待用户确认后再开工。
>
> 依赖文档：`docs/api-contract-v1.md`（§8 契约已冻结）· `docs/spec-ux-humanization.md`（10 铁律）· `docs/plan-master-roadmap.md`（总纲）。

---

## 0. 阶段编号对齐（先于一切）

**产品线（canonical，以此为准）：**

```text
C0 架构 → C1 Wealth Cockpit → C2 Allocation X-Ray → C3 Wealth Sandbox
      → C3.5 人性化 / 冷启动 / 行动闭环 → A1 AI Agent
```

**澄清 MEMORY / roadmap 旧编号的误导：** `plan-master-roadmap.md` 当前基线表写的「C3/C3.5 ✅」是**过宽表述**——它实际冻结的是「场景契约（§8）+ 引擎原语（apply_scenario / build_overview / compare_scenarios）+ 基础沙盘页」。§8 原文即写明「契约已冻结，**实现归 Plan C**」。因此：

| 已冻结（勿动） | 本计划交付（缺失） |
|---|---|
| §8 契约、`apply_scenario`、`build_overview`、`compare_scenarios`、9 指标、4 场景、3 养老 limitation、基础对比表 | **决策体验层**：人性化叙事、风险变化、状态设计、行动闭环、headless 验收 |

> 结论：**C3 的机械内核已完成；本计划只做「呈现层 + 体验层 + 验收基建」，不重算、不重写任何财富公式。**

---

## 1. C3 用户流程（7 步）

```text
① 当前财务状态（baseline 概览）
   ↓
② 选择决策类型（4 场景：买房 / 提前还贷 / 投资 / 收入变化）
   ↓
③ 输入方案参数（自然语言解释，非裸字段）
   ↓
④ 生成 A/B/C 方案（1~3 个，每个独立 apply 自同一 baseline）
   ↓
⑤ 与 Baseline 对比（9 指标 + 资产配置 + 问题变化）
   ↓
⑥ 查看风险变化（每个方案「发生了什么 / 为什么 / 风险是什么」）
   ↓
⑦ 选择下一步行动（倾向方案 → 下一步行动建议）
```

---

## 2. 核心指标（分两类）

**A. 冻结 9 维（`SCENARIO_METRICS`，已实现，禁止增删改）：**
净资产 / 财富评分 / RFR / NWC / 月度现金流结余 / 应急资金（月）/ DTI / 房产占比 / 目标完成度。

**B. 补充呈现（前端现取，不改 9 维契约，数据已在 `Overview` 里）：**

| 指标 | 来源 | 说明 |
|---|---|---|
| 资产配置 | `baseline.asset_allocation` vs `option.overview.asset_allocation` | 六大类占比 + `financial_pct` + `concentration`（房产集中度） |
| 财富问题 / 风险变化 | `baseline.issues` vs `option.overview.issues` | 方案消除 / 新增了哪些 P0/P1/P2 问题 |

> B 类**只是呈现** `Overview` 已返回的字段，零新计算、零契约改动。

---

## 3. 单一计算路径（铁律，逐条断言）

- 前端**不计算**任何财富指标（wealth_score / RFR / NWC / DTI / net_worth / 配置占比）。
- AI **不计算**任何数字（C3 阶段不接 LLM，叙事用确定性模板）。
- Scenario **不复制** Engine 公式（`apply_scenario` 只做数据补丁，重算统一走 `build_overview`）。
- 调整后指标必须 `apply_scenario → build_overview`（现有 `compare_scenarios` 已保证）。
- Baseline 与所有方案来自**同一套 Engine**（`build_overview(data)` 同源）。

**守门测试（新增，见 §12）：** 断言解释层模块「只读 comparison/Overview 字段 + 布尔/字符串分类」，不含任何财富算式（乘法/幂/折现等）。用一条「解释层输出 == 纯字段读取 + 符号判断」的契约测试锁死。

---

## 4. Scenario 类型（冻结，只有 4 个）

`buy_house` / `prepay` / `invest` / `income_change`。

- 禁止新增 `allocation_rebalance` 等幽灵场景。
- 禁止改动 `SCENARIO_NAMES` / `SCENARIO_PARAM_MODELS` / `SCENARIO_METRICS`（`tests/test_scenario_contract.py` 已守门）。

---

## 5. A/B/C 对比（按 §8 冻结契约，不修改）

- 请求：`POST /api/wealth/scenario/{name}/compare`，body `{options:[{id,name,params}]}`。
- 响应：`{scenario, baseline, options[], comparison{}}`，形状不变。
- 每个 option 独立 `apply_scenario` 深拷贝，绝不链式 apply（现有 `test_options_independent_not_chained` 已守门）。
- 本计划**不新增 / 不删改** CompareResponse 的任何字段。叙事层、风险变化、分类全部由前端从**已有响应**现取。

---

## 6. 人性化设计（新增交互，对应 `spec-ux-humanization.md` 铁律）

| # | 要求 | 现状 | C3 改动 |
|---|---|---|---|
| ① | 不显示复杂公式 | 已是金额/百分比 | 参数说明用「人话」替换裸字段名（如 `down_payment_ratio` →「首付几成」） |
| ② | 参数有自然语言解释 | 仅一行 desc | 每个字段旁加「这是什么 / 影响什么」提示 |
| ③ | 结果回答「发生了什么/为什么/风险」 | 只有差值表 | 每方案新增**叙事卡**（summary/why/risk 三段） |
| ④ | 区分「更有钱」vs「更安全」 | 只有红绿差值 | 每方案加**定位徽标**：`更有钱` / `更安全` / `均衡` / `无明显差异` |
| ⑤ | 支持返回基线 | 无显式入口 | 「重置为当前」按钮（一键清空结果回到 baseline） |
| ⑥ | 支持改参数重算 | 已可重算 | 保留参数 + 「重新模拟」；改参数不丢已有方案 |
| ⑦ | 不因一次输入错误丢方案 | 报错后 `st.result` 清空但 `st.options` 保留 | 显式保证：报错不清 `st.options`，并给出可复用的「修正后重试」 |
| ⑧ | loading / 空状态 / 错误 / 无明显差异 | 有 loading + error，缺空/无差异 | 补：0 数据→「先建档」引导；全 delta≈0→「各方案差异不大」友好提示 |

**叙事层实现（确定性，纯前端，无 LLM）：**
新增 `static/lib/scenario-interpret.js`（纯函数，无 DOM / 无 Vue 依赖，可 Node 单测）：

```
interpret(scenario, baselineOverview, optionOverview, comparisonRow)
  → { summary, why[], risk, position, issueDelta }
```

- `summary`：一句话「发生了什么」（场景 + 参数 → 人话，如「把 30 万现金投入权益类资产」）。
- `why`：驱动变化的 top 维度（取 `comparisonRow` 中 |delta| 最大者 → 人话）。
- `risk`：最险维度（应急资金跌破 3 月 / DTI 升破 30% / 现金流转负 → 提示）。
- `position`：`更有钱`（净资产↑/财富分↑ 且安全指标未显著恶化）/ `更安全`（DTI↓/流动性↑/RFR↑ 且未显著变穷）/ `均衡` / `无明显差异`。
- `issueDelta`：`baseline.issues` vs `option.issues` → `{resolved:[], new:[]}`（用 `issue_id` 对齐）。

> 铁律：`interpret` **只读** `comparisonRow` 里后端已算好的 `baseline/option/delta`，**只做**「取符号 + 字符串模板」，**绝不**出现 `(1+r)^n`、折现、占比重算等财富算式。

**顾问感（不排名，新增强制要求）：**

- **不生成「最佳方案」**：C3 全程不按总分/单指标给方案排名，绝不出现「方案 A 明显更优」这类结论。
- **差异有限态**：当所有维度变化低于阈值 → 明确输出「变化有限 / 两方案差异不大」，绝不强行制造优劣。
- **trade-off 多维展示**：当方案存在取舍（如财富↑但流动性↓）→ 必须同时展示「更有钱 / 更安全 / 流动性 / 风险问题变化」等维度，并给「没有绝对更优，A 偏向 X、B 偏向 Y」的顾问式提示。

---

## 7. Known Limitations（继续展示，不得暗示边界不存在）

- 继续注入并渲染 3 项养老 limitation（已实现：`build_overview.retirement.known_limitations` + `format.js LIMITATION_LABELS`）。
- 叙事层文案**不得**暗示「模型能消除这些假设」；相反，当方案改变养老指标时，提示「本测算仍受既有三项边界约束」。
- 守门测试已存在：`test_compare_passthrough_known_limitations`。新增断言：叙事层输出引用 limitation 时用原 label，不新增第 4 项。

---

## 8. 验收标准（8 项，全部落地到测试）

| # | 验收 | 落地 |
|---|---|---|
| 1 | API 契约测试 | 已有 `test_frontend_contract.py` + `test_scenario_contract.py`；**不变**，全量回归须仍绿 |
| 2 | Scenario apply 测试 | 已有 `test_apply_scenario.py`（不 mutate / 返回 data 非 metric / 4 场景 / 校验错误） |
| 3 | Baseline/方案一致性 | 已有 `test_compare_scenarios.py`（baseline==build_overview、不链式、九指标）；新增**解释层一致性**：`interpret` 输出字段全部能从 comparison+overview 复现 |
| 4 | A/B/C 对比测试 | 已有；新增「问题变化」对齐测试：`issueDelta` 与 `issues` 差集严格一致 |
| 5 | 前端 headless 验收 | **新增**：Playwright（Python，已装）沙盘页 smoke——建档→跑 compare→断言 9 行渲染 + 叙事卡渲染 + `position` 徽标存在 |
| 6 | JS 0 error | headless 用例收集 `page.on('console')` / `page.on('pageerror')`，断言 0 error |
| 7 | 全量 pytest 不回归 | `251 passed`（现状）→ 新增后 ≥251，0 失败 |
| 8 | 顾问感（不排名） | 差异有限→「变化有限」态；trade-off→多维展示 + 「无绝对更优」提示；全程无「最佳方案」结论（Node 单测断言） |

---

## 9. 冻结边界（本轮可改 / 禁止改）

**禁止修改（冻结契约，动了就是违约）：**

- `app/engine/**`（Wealth Engine 核心计算，含 `scenario.py` 的 `run_scenario`/`apply_scenario`/4 个 simulate）
- `app/services/overview.py` 的 `build_overview`（Overview 形状）
- `app/services/scenario.py` 的 `compare_scenarios`（编排层）
- `app/schemas/scenario.py`（SCENARIO_NAMES / SCENARIO_METRICS / PARAM_MODELS / CompareResponse）
- `app/decision/**`（Decision Layer，问题真相源）
- `docs/api-contract-v1.md`（契约文档）
- `app/api/scenario.py`（/compare 端点契约）

**本轮可修改（呈现/体验/验收基建）：**

- `static/views/sandbox.js`（沙盘页改造）
- `static/lib/scenario-interpret.js`（**新增**，纯函数叙事层）
- `static/style.css`（叙事卡 / 徽标 / 状态样式）
- `static/format.js`（如需要，仅加格式化辅助，不碰 LIMITATION_LABELS 语义）
- `tests/`（**新增** `test_scenario_interpret.py`〔Python 侧复现解释层契约〕、`test_sandbox_interpret.py` 或 Node 单测、`tests/e2e/` Playwright 冒烟）
- `docs/testing-guide.md`（补 headless 跑法，可选）

> **关键原则：解释层「可读不可算」**——它消费的每一个数字都必须已经存在于后端返回的 `comparison` / `Overview` 中，代码评审第一眼查这一条。

---

## 10. 范围决策（已定）

### D1：行动闭环 —— ✅ 只读建议

- 沙盘内「倾向方案」选择 + **只读展示**该方案 `overview.recommendations` 的下一步行动建议。
- **不写库、不动 DB**，符合「确认前绝不写库」。
- 「生成行动计划 / 价值发生指标埋点」留给 C3.5（新编号里「行动闭环」属 C3.5）。

### D2：headless 底座 —— ✅ Node 单测 + Playwright 冒烟（两者都做）

- **Node 单测**（`node --test`，Node v24 已装）覆盖 `scenario-interpret.js` 纯函数逻辑——快、稳。
- **Playwright 冒烟**（Python 包已装）覆盖真实 DOM 渲染 + 0 console/pageerror——验收⑤⑥。
- 前提：确认 `playwright install chromium` 浏览器二进制就绪；未就绪则加一次性安装步骤（约 150MB）。

---

## 11. TDD 顺序（实施阶段，本轮不执行）

> 每步 red→green→refactor，独立可测。**本计划阶段只确认顺序，不写代码。**

1. **解释层契约测试（红）**：`test_scenario_interpret.py` 用固定 fixture（baseline + 3 options 的 comparison/overview）断言 `interpret` 的 5 个输出字段与「纯字段读取」一致，且模块源码不含财富算式（AST/正则扫 `**`/`(1+`/`pow` 等）。
2. **`scenario-interpret.js` 纯函数（绿）**：实现 `interpret`，Node 单测对齐。
3. **问题变化对齐测试（红→绿）**：`issueDelta` 与 `baseline.issues`/`option.issues` 差集严格一致（含 P0 消除、新增）。
4. **sandbox.js 叙事卡 + 定位徽标 + 风险变化区块（红→绿）**：渲染 summary/why/risk/position + issueDelta。
5. **状态设计（红→绿）**：空状态（0 数据→建档引导）、无明显差异（全 |delta|<阈值→友好文案）、loading/error 保持。
6. **返回基线 + 改参重算 + 报错不丢方案（红→绿）**。
7. **Playwright 冒烟（红→绿）**：建档→compare→断言 9 行 + 叙事卡 + 0 console/pageerror。
8. **全量回归**：`pytest` 251→≥251 全绿；node 单测绿；headless 绿。

---

## 12. 验收矩阵（可勾选）

| 验收项 | 测试文件 / 手段 | 状态 |
|---|---|---|
| API 契约不破 | `test_frontend_contract.py` `test_scenario_contract.py` | 已有，须仍绿 |
| apply 原语 | `test_apply_scenario.py` | 已有 |
| baseline/方案一致 + 不链式 + 九指标 | `test_compare_scenarios.py` | 已有 |
| 解释层可读不可算 | `test_scenario_interpret.py`（新） | 待建 |
| 解释层输出可复现 | Node 单测（新） | 待建 |
| 问题变化差集一致 | `test_scenario_interpret.py`（新） | 待建 |
| 前端 headless 渲染 + 0 error | `tests/e2e/test_sandbox_smoke.py`（新，Playwright） | 待建 |
| 全量不回归 | `pytest -q` ≥251 | 待验 |

---

## 13. Commit 拆分方案

```text
1. test(scenario): 解释层「可读不可算」契约测试 + Node 单测脚手架
2. feat(sandbox): 新增 scenario-interpret 纯函数（summary/why/risk/position/issueDelta）
3. feat(sandbox): 叙事卡 + 定位徽标 + 风险变化区块渲染
4. feat(sandbox): 状态设计（空态/无差异/报错保参）+ 返回基线/改参重算
5. test(e2e): Playwright 沙盘冒烟（9 行 + 叙事卡 + 0 error）
6. docs: testing-guide 补 headless 跑法（可选）
```

> 每 commit 独立绿、可回滚；**不出现**一个 commit 同时改前端与契约。

---

## 14. 风险与自检

- **最大风险 = 解释层悄悄算数字** → 用「可读不可算」契约测试 + 源码扫描双重锁死。
- **次要风险 = 契约被顺手改** → 冻结边界 §9 明确白名单，评审第一眼查 diff 是否越界。
- **headless 底座引入成本** → D2 待你拍板；未拍板前所有 headless 相关任务冻结。
