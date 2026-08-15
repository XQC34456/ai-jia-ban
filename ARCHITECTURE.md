# AI家办 · 系统架构与铁律

> 本文件是 AI家办（家庭财富智能决策操作系统）的**长期架构与原则**，优先级高于单次实现。

## 一句话定位

**AI家办不是「存家庭财富的数据库」，而是「家庭财富决策操作系统」。**
它帮用户：看清现状 → 发现风险 → 模拟决策 → 推动行动。

---

## 核心铁律（不可违反）

### 铁律 1：AI 不负责「算钱」
```
AI 负责：理解人 → 调用模型 → 解释结果 → 推动决策
AI 不负责：凭经验计算任何财务数字
```
数字**只来自 Wealth Engine**。AI 收到的永远是 API 返回的结构化 JSON，只组织语言、解释含义。

### 铁律 2：财富计算只有一个路径
```
用户 → AI → 调用 Wealth API → Engine → Decision Layer → Scenario → 结构化结果 → AI解释 → 用户行动
```
禁止在 **前端 / Service 层 / AI / Scenario 二次复制** Engine 的财富公式。
任何「重算」都必须走 `Engine.apply → build_overview`，保证全局数字一致。

### 铁律 3：Engine 是确定性纯函数，与 LLM 严格隔离
- `app/engine/`：只计算（确定性、纯函数、零 LLM、零 I/O）。
- `app/decision/`：只判断（规则）。
- AI Agent：只解释。
- 前端：只展示。

---

## 分层架构

```
┌─────────────────────────────────────────────────────────┐
│  前端（Vue 3 CDN）  /  AI Agent  /  报告  /  提醒         │  展示 + 解释
├─────────────────────────────────────────────────────────┤
│  API Schema（pydantic v2 契约，docs/api-contract-v1.md）  │  契约边界
├─────────────────────────────────────────────────────────┤
│  Services / Orchestration（build_overview / compare）     │  编排
├─────────────────────────────────────────────────────────┤
│  Decision Layer（7 类问题 + 四象限 + P0/P1/P2）           │  判断
├─────────────────────────────────────────────────────────┤
│  Wealth Engine（确定性纯函数）                             │  计算
├─────────────────────────────────────────────────────────┤
│  Family Data（SQLite）                                    │  数据
└─────────────────────────────────────────────────────────┘
```

- **API v1 契约**：见 `docs/api-contract-v1.md`（已冻结）。
- **战略主纲（V1.0）**：见 `docs/plan-v10-restructure.md`（唯一总纲，产品做什么）。
- **现状核对**：见 `docs/verification-v10-current-state.md`（8 条论断代码取证）。
- **实施路线图**：见 `docs/plan-master-roadmap.md`（Phase 0-8 怎么落地）。
- **顾问核心架构**：见 `docs/plan-ai-advisor-core-architecture.md`（六阶段顾问循环 + 问答建档解耦）。

---

## Scenario State → Projection State（最小原语）

沙盘要「基线 + 多方案 + 全局指标对比」，唯一正确路径是让 Engine 暴露一个**最小原语**：

```python
# app/engine/scenario.py —— 返回「应用情景后的数据副本」，不重写模型
def apply_scenario(data, name, params) -> modified_data: ...
```

然后复用已存在的 `build_overview(modified_data)` 重算全局指标（财富评分/RFR/NWC/流动性/DTI）。
这保证「买 700 万房后 RFR 1.31」这个数字，前端、AI、沙盘三方拿到的**完全一致**——因为都来自同一次 Engine 计算。

---

## 能力边界（Known Limitations）

当前模型对养老测算有三处边界（注入 `retirement.known_limitations`，前端/Agent 必须如实呈现，不夸大）：
- `retirement_debt_service_not_included`（养老测算未计退休期还贷）
- `goal_retirement_semantic_overlap`（养老目标与退休测算语义重叠）
- `other_asset_liquidity_assumption`（other 类资产流动性按假设）
