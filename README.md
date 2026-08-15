# AI家办 · 家庭财富决策操作系统

面向普通家庭的 AI 家庭财富决策操作系统 —— 帮用户「看清现状 → 发现风险 → 模拟决策 → 推动行动」。

**核心定位**：AI 顾问是产品主入口与决策中枢，其余模块（Engine / Decision / Cockpit / X-Ray / Sandbox / Data / Goals / Reports）都是顾问的能力底座和行动工具。

**铁律**：财务数字一律由 Wealth Engine 确定性计算，LLM 绝不计算、绝不编造。

---

## 快速开始

```bash
cd D:\Claude_Code\ai-jia-ban

# 1. 安装依赖（已装可跳过）
pip install -r requirements.txt

# 2. 启动（默认 http://127.0.0.1:8000）
python -m app.main
# 或
uvicorn app.main:app --reload
```

浏览器打开 `http://127.0.0.1:8000`。

---

## 接入 DeepSeek（可选，强烈建议）

产品默认用**确定性规则兜底**，开箱即用。接入 DeepSeek 后，意图路由兜底与场景参数抽取走 LLM。

1. 复制 `.env.example` 为 `.env`
2. 填入你的 key：

```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

3. 重启服务。

> 换豆包/通义/GLM 等 OpenAI 兼容接口，改 `LLM_BASE_URL` 和 `LLM_MODEL` 即可。

> **现状说明**：AI 顾问当前为 Level 0（确定性引擎 + LLM 做意图路由/参数抽取），回答仍是确定性模板。V1.0 产品重构目标是把产品从「财报生成器」拉回「长期家庭财富 AI 顾问」，战略主纲见 [docs/plan-v10-restructure.md](docs/plan-v10-restructure.md)，现状核对见 [docs/verification-v10-current-state.md](docs/verification-v10-current-state.md)，顾问核心架构见 [docs/plan-ai-advisor-core-architecture.md](docs/plan-ai-advisor-core-architecture.md)。

---

## 跑测试

```bash
# Windows 需带编码环境变量，否则中文输出乱码
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m pytest -q

# 前端解释层单测
node --test tests/js/humanize.test.js tests/js/scenario-interpret.test.js
```

---

## 架构

```
接入层       Web H5（static/，Vue 3 单页 App Shell + hash 路由，9 视图）
   ↓
AI 顾问层   app/agent/    converse() 统一入口 → 建档吸收(确认卡片) / 七意图路由 → 结构化响应
   ↓
抽取层       app/extraction.py  规则抽取（RuleExtractor，确定性；LLM 抽取留待 V2.2）
   ↓
服务编排层   app/services/  build_overview / build_goals / compare_scenarios（编排，不重算）
   ↓
判断层       app/decision/  7 类问题检测 + 四象限 + P0/P1/P2（确定性规则）
计算引擎层   app/engine/    metrics / allocation / projection / scenario / goals / score（纯函数）
   ↓
数据层       app/db.py      SQLite：users/family/person/asset/liability/cashflow/goal/reminder/insurance
```

**关键设计**：财务数字一律由 `app/engine/` 的纯函数计算，绝不交给 LLM；LLM 只做「听懂」和「说人话」。

> 完整分层与铁律见 [ARCHITECTURE.md](ARCHITECTURE.md)；冻结契约见 [docs/api-contract-v1.md](docs/api-contract-v1.md)。

---

## API

> 除 `/api/health`、注册/登录外，所有接口需带请求头 `Authorization: Bearer <token>`，未带/无效 → 401；数据随登录用户隔离。VIP 门（报告/决策/情景对比）：免费用户 → 403。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（无需鉴权），返回 `{ok, llm}` |
| POST | `/api/register` | 注册，返回 token（自动创建并绑定家庭） |
| POST | `/api/login` | 登录，返回 token |
| GET | `/api/me` | 当前用户信息 |
| POST | `/api/upgrade` | 模拟开通 VIP（无支付，TODO 接支付） |
| GET | `/api/family` | 家庭档案 + 快照 + 体检 |
| POST | `/api/confirm` | 确认/撤销待定建档动作（配合 `/api/agent/chat` 的确认卡片） |
| GET | `/api/wealth/overview` | 财富驾驶舱（评分/净资产/配置/现金流/养老/问题） |
| GET | `/api/wealth/issues` | 问题/告警/优先级/建议 |
| GET | `/api/wealth/goals` | 目标统一测算 |
| POST | `/api/wealth/scenario/{name}` | 情景模拟（VIP） |
| POST | `/api/wealth/scenario/{name}/compare` | 情景对比（VIP） |
| POST | `/api/agent/chat` | AI 顾问唯一入口（建档确认卡片 / 七意图结构化 AgentResponse） |
| GET | `/api/report` | 深度报告（VIP 专属） |
| POST | `/api/decision` | 决策模拟（VIP 专属） |
| POST | `/api/family/entity/{table}` | 看板新增实体 |
| PUT/DELETE | `/api/entity/{table}/{id}` | 看板编辑/删除实体 |

> `name ∈ {buy_house, prepay, invest, income_change}`；`table ∈ {person, asset, liability, cashflow, ...}`。

---

## 已完成

- 统一 App Shell（`/` 单页 + hash 路由：Sidebar 9 项 + Topbar + 主内容区）
- 9 个视图：家庭总览 / 家庭数据 / 财富健康 / 资产配置 / 退休规划 / 家庭目标 / 风险问题 / 情景沙盘 / AI 顾问
- 家庭总览：财富评分 / 净资产 / 资产配置 / 现金流 / 流动性 / 债务 / 保障 / 养老 + AI 主动洞察（确定性 `build_issues`，非 LLM）
- 情景沙盘：买房 / 提前还贷 / 投资 / 收入变化，1~3 方案对比（VIP）
- 深度报告（LLM 建议 + 打印导出 PDF，VIP）
- 决策模拟器（买房 / 提前还贷，VIP）
- 登录 + VIP 分层（免费=对话建档 + 体检 + 目标 + 问题 + 各只读视图；VIP=报告 + 决策 + 情景沙盘；模拟开通按钮）
- 家庭数据管理（成员/收入/支出/资产/负债/目标 的查看·新增·编辑·删除，纯读写不计算）
- AI 顾问统一收口（`/api/chat` 退役；`/api/agent/chat` 唯一入口；建档确认吸收进 Agent；CHECK_ISSUES/CHECK_GOALS/EXPLAIN_RESULT 由 `build_issues`/`build_goals` 确定性产出）
- 人性化落地（体检报告横幅 / 「为什么」自然语言解释 / 「模拟」按钮跳沙盘 / 沙盘模式提示 / 冷启动向导）

## 下一步：V1.0 产品重构（Phase 1 顾问核心重构）

产品从「财报生成器」回到「长期家庭财富 AI 顾问」——顾问是主入口，其余模块是能力底座。现状核对已确认 4 条真缺口（建档优先 / 建档问答耦合 / 取消建档丢问题 / 无澄清循环）。

**Phase 1（当前）**：
- Advisor Benchmark — 12 个真实问题建立回归基线
- AdvisorContext 契约 — 跨页面「问顾问」结构化传参，替代纯文本预填
- 两条路径重构 — 跨页面问顾问 / 取消建档后继续回答

> 战略主纲 [docs/plan-v10-restructure.md](docs/plan-v10-restructure.md) · 现状核对 [docs/verification-v10-current-state.md](docs/verification-v10-current-state.md) · 实施路线图 [docs/plan-master-roadmap.md](docs/plan-master-roadmap.md) · 顾问核心架构 [docs/plan-ai-advisor-core-architecture.md](docs/plan-ai-advisor-core-architecture.md)
