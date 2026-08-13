# AI家办 V2 — 现有系统审计（A~E）

> 审计日期：2026-08-13 · 审计范围：`app/`（8 模块）+ `static/`（3 文件）+ `tests/`（5 文件）+ 配置。
> 结论用途：为 V2「财富智能决策平台」升级提供现状基线，支撑 F~O 设计。

---

## A. 系统架构审计

现有系统是「单进程 FastAPI + SQLite + 无构建原生前端」的 MVP，分层已经清晰，且**已遵守 V2 最核心的技术原则**——确定性计算与 LLM 严格分离。

```
接入层    static/index.html + app.js + style.css      原生 JS SPA，无构建、无框架
   ↓  HTTP JSON（Authorization: Bearer <token>）
API 层    app/main.py（FastAPI 0.140）                 鉴权 + 路由 + 静态服务
   ↓
编排层    app/chat.py                                  抽取 → 确认 → 落地 → 重算 → 反馈（状态机）
   ↓
抽取层    app/extraction.py                            RuleExtractor / LLMExtractor 可插拔
   ↓
计算层    app/calc_engine.py（纯函数，零依赖）          资产负债 / 现金流 / 储蓄率 / 应急月数 / 安全边际
   ├── app/health.py       体检规则引擎 → 3 个问题
   ├── app/decision.py     买房 / 提前还贷 决策模拟
   └── app/report.py       深度报告（数据 + LLM 建议）
   ↓
数据层    app/db.py（SQLite）                          users/family/person/asset/liability/cashflow/goal/reminder
```

**优点（可直接继承到 V2）**
1. 计算引擎 `calc_engine.py` 是纯函数、零依赖、可单测、可审计——正是方案「Wealth Engine」要求的正确地基。
2. LLM 只出现在两处：`extraction`（听懂）和 `chat`/`report` 的回答生成（说人话），从不计算数字。
3. 鉴权 + 数据隔离已落地（`users.family_id` 绑定 + 实体 owner 校验）。
4. 模块职责单一，边界清楚（编排/抽取/计算/体检/模拟/报告/数据七层分离）。

**与 V2 的差距（关键）**
1. **没有 Wealth Engine 的广度**：现只有「体检 + 2 个决策场景」，缺资产配置分析、现金流模型、风险评估、目标测算、情景模拟、压力测试、Monte Carlo、退休规划、再平衡。
2. **没有 Scenario Engine**：`decision.py` 是硬编码的 `buy_house`/`prepay` 两个函数，不是通用情景框架。
3. **没有 AI Agent 层**：只有一个 `chat` 编排 + 一个 `LLMExtractor`，无多 Agent 分工（Wealth Analyst / Risk / Goal Planner / Scenario…）。
4. **没有财富驾驶舱**：现在「总览」只是指标卡 + 资产 donut + 3 问题，不是「我家现在怎么样」的一屏决策视图。
5. **没有财富决策沙盘**：现在「决策模拟」是弹窗表单点一次算一次，不是「拖动变量实时更新的 What-if」。

---

## B. 数据库 / 数据模型审计

现有 8 张表。对照方案数据层要求（家庭成员、资产、负债、收入、支出、**保险、教育、养老、投资、目标、事件**）：

| 方案要求 | 现状 | 差距 |
|---|---|---|
| 家庭成员 | `person` ✓ | name / relation / birth_year / monthly_income / job |
| 资产 | `asset` ✓ | type / name / value（**无流动性、风险等级、大类、成本、收益字段**） |
| 负债 | `liability` ✓ | principal / monthly_payment / interest_rate / remaining_months |
| 收入 | `cashflow`(income) ✓ | |
| 支出 | `cashflow`(expense) ✓ | |
| 保险 | ✗ 无独立表 | 仅 `asset.type="保险现金价值"` 占位，无法存保额/保费/保障责任 |
| 教育 | ✗ 无独立表 | 仅 `goal.type="教育"`，无「年度费用/持续年限/起始年」 |
| 养老 | ✗ 无独立表 | 仅 `goal.type="养老"` |
| 投资 | ✗ 无独立表 | 基金/股票混在 `asset`，无持仓/成本/收益/风险等级/行业地区 |
| 目标 | `goal` ✓ | type / target_amount / target_date / current_saved / monthly_contribution（**一次性目标，无现金流型、优先级、波动容忍**） |
| 事件 | ✗ 无 | 方案「事件驱动主动提醒」无落点 |

**关键问题**
1. **资产表缺 V2 必需字段**：没有 `liquidity`（流动/非流动）、`risk_level`（权益/固收/现金大类）、`cost_basis`、`expected_return`。导致「权益/固收/现金占比、集中度、Portfolio X-Ray」全部算不出。
2. **目标模型过简**：只有「金额 + 日期」一次性目标，不支持方案要求的「现金流型目标」（教育金每年 N 万 × M 年、养老金每月 N 元）与「优先级、允许波动范围」。
3. **缺保险、投资、事件三类实体**——方案明确列出，现状完全没有。

**⚠️ 重要偏差（须澄清）**：方案第二节称「已有：对话、房产、保险、存款、教育、健康、提醒」。实际代码审计发现，这些「已有」中大部分只是**概念占位、功能未落地**：
- **保险**：无实体，仅 `asset` 的一个 `type` 枚举值（"保险现金价值"），把它当普通资产存。
- **教育**：无实体，仅 `goal` 的一个 `type` 值。
- **健康**：代码中**不存在任何健康档案实体**——唯一带「健康」字样的是 `health.py`（财务体检），与「家庭健康档案」不是一回事。
- **提醒**：`reminder` 表 + `get_reminders` 查询存在，但**没有任何路由、UI 页签、写入逻辑**使用它（半成品/死代码）。

---

## C. 页面与功能审计

**现有功能清单（已落地、可用）**
1. 账号：注册 / 登录 / 退出 / 升级 VIP（模拟）
2. 对话建档：收入 / 支出 / 资产 / 负债 / 成员 / 目标（含「确认后落地」防幻觉）
3. 对话提问：基于家庭快照 + 3 体检问题回答（LLM 或规则兜底）
4. 看板 CRUD：6 类实体（资产/负债/现金流/成员/目标），通用表格 + 弹窗
5. 总览：8 个指标卡 + 资产 donut（纯 CSS conic-gradient）+ 3 个问题
6. 深度报告：VIP 专属，打印导出 PDF
7. 决策模拟：VIP 专属，买房 / 提前还贷

**前端技术特征**
- 无构建、无框架、原生 JS，`app.js` **单文件 747 行**承载全部逻辑（渲染/事件/API/鉴权/报告/决策）。
- 状态管理极简：全局 `state` + 每次操作后全量 `refresh()`。
- 图表手写：无图表库，donut 用 `conic-gradient` 拼。

**V2 要求的页面能力（现状全部缺失）**：财富驾驶舱、财富决策沙盘（实时 What-if）、目标规划、情景模拟、压力测试、AI 主动管家、Portfolio X-Ray。

---

## D. 可复用模块清单

| 模块 | 复用方式 | 备注 |
|---|---|---|
| `calc_engine.py` | ✅ **完全复用，直接扩展** | 最高价值资产；V2 加资产配置分析/目标测算/现金流/风险/情景 |
| `extraction.py` | ✅ 复用框架 | 可插拔（规则/LLM）架构好；扩展现金流目标、保险、投资抽取 |
| `chat.py` 状态机 | ✅ 复用 | 加「规划意图」分支即可 |
| `db.py` | ✅ 复用 | 分层 + CRUD + 鉴权 + 白名单防注入；schema 需扩展 |
| `main.py` 鉴权 | ✅ 完全复用 | pbkdf2 + Bearer + Depends 不动 |
| `health.py` | ◐ 演化为 Wealth Score 的一部分 | 或保留为「问题发现」独立模块 |
| `decision.py` | ◐ 复用公式，重构进 Scenario Engine | 等额本息/剩余本金/月供公式是通用资产 |
| `report.py` | ◐ 复用报告框架 | 内容升级为「驾驶舱报告 + 三套方案」 |
| 前端 `api()` / `fmtMoney` / `renderTable` / 决策表单 | ◐ 复用 | 驾驶舱/沙盘需新写 |

---

## E. 技术债与风险

| # | 问题 | 风险 | 建议 |
|---|---|---|---|
| 1 | **SQLite 每次操作新建连接**（`get_conn` 无连接池） | 并发/高频计算下性能差 | V2 高频计算可先加单例连接或 WAL；生产迁移 PostgreSQL（db.py 已预留注释） |
| 2 | **会话 token 明文存 `users` 表、无过期** | 安全债 | 加过期时间 + 刷新机制 |
| 3 | **确认状态存内存 `_PENDING`**（chat.py 单进程） | 重启丢失、多进程失效 | 生产迁 Redis/DB |
| 4 | **CORS `allow_origins=["*"]`** | 配合 token 可控，但应收紧 | 收窄 origin |
| 5 | **`app.js` 单文件 747 行** | V2 加驾驶舱/沙盘会失控 | 拆模块（dashboard/chat/sandbox/…） |
| 6 | **图表手写、无图表库** | 做 Portfolio 堆叠、蒙特卡洛分布、实时沙盘力不从心 | 引入 ECharts（纯前端、无需构建、中文文档好） |
| 7 | **⚠️ `.env` 含真实 API key，且项目无 `.gitignore`、无 git** | 一旦 git init 立即泄漏密钥 | 立即加 `.gitignore`（忽略 `.env`、`data.db`、`__pycache__`）再 git init |
| 8 | **`reminder` 半成品**（有表无 UI 无写入） | 方案误判为「已有提醒」 | V2 要么真正落地「主动提醒」，要么明确砍掉 |
| 9 | **测试覆盖不均** | decision.py / report.py 无测试 | V2 每加一个引擎/场景都要带测试 |
| 10 | **项目未纳入 git 版本控制** | 「不推翻现有」无法回溯，大改有风险 | V2 动工前先 `git init` + 基线提交 |

---

## 审计小结（一句话）

> 现有系统是一台**架构正确、但计算能力只有 20% 的发动机**：分层清晰、确定性计算与 LLM 分离到位、鉴权/隔离/测试齐备；但 Wealth Engine 只有「体检 + 2 场景」，资产/目标/保险/投资/事件数据模型缺失，「驾驶舱/沙盘/主动管家」三大体验完全空白。V2 的关键不是推倒重来，而是**在现有正确地基上补全引擎广度和决策体验**。
