# 顾问核心架构计划（V1.0 六阶段顾问循环）

> **唯一主体架构计划。** 依据：战略主纲 [plan-v10-restructure.md](plan-v10-restructure.md) §六/§七/§八 + 现状核对 [verification-v10-current-state.md](verification-v10-current-state.md)。
> 本文件回答：**顾问应该长什么样（目标架构）→ 当前差什么（真缺口）→ 怎么改（改造方案）→ 先做什么（Phase 1）。**
> 旧版「Plan D AI Advisor V2（V2.1→V2.6）」的 V2.x 阶段已并入 [plan-master-roadmap.md](plan-master-roadmap.md) §5 的 Phase 1-8，本文件为 V2.x 的架构升级版。

---

## 0. 定位（一句话）

> **「一个长期理解这个家庭，并帮助这个家庭做财富决策的 AI 顾问。」**

核心反转不变：**不是「页面调用 AI」，而是「AI 顾问调用整个财富系统」。** LLM 不是整个顾问，只是六阶段循环里「理解与叙事」的组件；判断、计算、证据由系统层确定性保证。

---

## 1. 冻结边界（任何阶段不得触碰）

| 冻结项 | 位置 | 理由 |
|--------|------|------|
| Engine（财富计算） | app/engine/、app/services/ `build_overview` / `compare_scenarios` | 数字唯一真相源 |
| Decision（问题检测） | app/decision/ `build_issues` | 判断唯一真相源 |
| 场景契约 C3.5 | app/schemas/scenario.py | 新增场景必须改这里 + contract test 逼同步 |
| Agent 输出 Schema A1 | app/schemas/agent.py `AgentResponse` / `MetricRef` | 防编造硬闸，只扩不减 |
| A2 工具只读 + VIP 门 | app/agent/tools.py | 工具 = 获取事实，绝不计算 |

> 改造只允许在 **app/agent/ 编排层与前端入口层**进行，不触碰上表。

---

## 2. 目标架构：六阶段顾问循环

LLM 是六阶段里的「理解与叙事组件」，其余由系统层确定性完成。每阶段给出 **系统职责 / LLM 职责 / 失败策略 / 当前状态**：

| 阶段 | 系统职责 | LLM 职责 | 失败策略 | 当前状态 |
|------|----------|----------|----------|----------|
| **1. Intent** | 识别用户真正目的（含建档/提问判别） | 辅助语义理解 | 低置信度 → **澄清**（缺 G4） | ⚠️ 无置信度，兜底 Overview |
| **2. Context** | 读取档案 + 页面上下文 + 历史问题 | 理解语境 | 已有数据优先复用（缺 #4） | ⚠️ 回答路径有注入，建档路径无 |
| **3. Evidence** | 确定必须取哪些 Engine 数据 | 决定解释方式 | 系统保证必需证据（部分缺 #6） | ⚠️ P1.1 基线已缓解 |
| **4. Reasoning** | Scenario / Decision / Engine 计算 | 形成顾问式判断 | 计算失败不得编造 | ✅ 已满足 |
| **5. Response** | 校验结构与事实 | 直接回答 / 解释 / 追问 | 答非所问检测 | ✅ 已满足（结论先行） |
| **6. Action** | 连接模拟 / 计划 / 提醒 / 复评 | 提出下一步 | 不强迫行动 | ⏳ Phase 4 |

**架构核心变化**：从「messages → DeepSeek → response」单轮，升级为**六阶段显式状态机**。LLM 的每个阶段产出都要过系统校验；尤其 Intent 阶段必须产出**置信度**，低置信度进入 Clarify 子状态而不是静默兜底。

---

## 3. 真缺口 → 架构改造点

> 每缺口都落到具体阶段，可独立验收。

| 缺口 | 落点 | 改造 |
|------|------|------|
| **G1 建档优先** | Intent 阶段 | 建档/提问判别改为「**意图 vs 建档**」双标签，而不是 `looks_like_filing` 的粗暴拦截（[profile.py:65-77](../app/agent/profile.py#L65-L77)） |
| **G2 建档/问答耦合** | Intent + 流程 | 建档独立状态机（见 §4 解耦），chat 只负责问答 |
| **G3 取消建档丢问题** | Context + 流程 | 确认卡保存原问题，取消后**原问题继续进回答路径**（见 §4） |
| **G4 无澄清循环** | Intent 阶段 | `route_intent` 产出置信度；低置信度 → Clarify 子状态，提最小澄清问题（[router.py:55-81](../app/agent/router.py#L55-L81)） |

---

## 4. 流程重构：问答与建档彻底解耦

**现状（错误）**：`converse()` 入口第一步判建档 → 确认卡 → 不回答（[entry.py:37-44](../app/agent/entry.py#L37-L44)）；确认卡只存 `{family_id, actions}` 不存原问题（[profile.py:80-85](../app/agent/profile.py#L80-L85)）。

**目标流程**（主纲 §七「我想投资 30 万」例子）：

```
用户消息
   ↓
① Intent：判别「提问 or 建档告知 or 两者皆是」   ← 不拦截，先识别
   ↓
② 先给基础回答（不依赖建档）                      ← G1 修复：能答就答
   ↓
③ Context：查档案 + 页面上下文 + 历史              ← 已有数据直接复用（#4）
   ↓
④ 只追问影响答案的缺失项（最小澄清）              ← G4 修复
   ↓
⑤ 若含建档信息 → 生成确认卡（边回答边沉淀）
      ├─ 确认 → 写库（P3 门）
      └─ 取消 → 原问题进入继续回答（不回建档路径）  ← G3 修复
   ↓
⑥ 根据问题价值给下一步：模拟 / 配置 / 计划          ← Action 阶段
```

**关键契约改动**：
1. **确认卡必须携带 `original_message`**：`create_confirm` 的 `_PENDING` 存储扩展为 `{family_id, actions, original_message}`；取消分支把 `original_message` 重新投入回答路径，而不是丢弃。
2. **建档独立入口**：`onboarding.js` 从「锁死向导」改为「可跳过 + 渐进式」；建档不强制，问答不依赖建档完成。

---

## 5. AdvisorContext 契约（跨页面入口结构化）

**现状**：`store.chat.draft` 纯文本预填（[store.js:33](../static/store.js#L33)）；后端 `AgentRequest.context` 字段空转（[agent.py:173](../app/schemas/agent.py#L173)，前端从不发送）。**context 是「存在但从未使用」的死字段。**

**目标**：跨页面「问顾问」携带结构化 `AdvisorContext`，后端第一轮必须消费它（上下文连续性验收，主纲 §九）。

```text
AdvisorContext = {
  source: "goals" | "retirement" | "allocation" | "sandbox" | "overview" | "chat",
  intent_hint: string,            # 期望第一轮回答的意图
  payload: dict,                  # 各来源页携带的关键数据（见下表）
  first_turn_action: string,      # 顾问第一轮应该做什么
}
```

| 来源 | payload（必须携带） | first_turn_action |
|------|--------------------|--------------------|
| Goals | `{goal_type, target_amount, current_saved, gap, monthly_need, target_date}` | 直接回答「这个目标怎么完成」 |
| Retirement | `{retire_age, need_pv, investable, gap}` | 解释缺口与关键变量 |
| Allocation | `{current_alloc, target_alloc, hhi, risk_metrics}` | 解释为什么这样配置 / 哪里需调整 |
| Sandbox | `{scenario_name, params, baseline, option, delta}` | 解释该情景对家庭的影响 |
| Overview | `{score, net_worth, top_issue, recent_changes}` | 回答当前最值得关注什么 |

**改动点**：
- 前端：各页「问顾问」不再写 `draft` 字符串，改为写结构化 `store.chat.advisorContext`；chat.js 请求体发 `{message, context}`。
- 后端：`AgentRequest.context` 从「可空注释」转为**必用字段**——`converse()` 收到 context 时，用它引导 Intent 判定与首轮回答（而非只靠消息文本）。

---

## 6. 现有基础如何复用（不重造）

| 已有能力 | 复用于 | 说明 |
|---------|--------|------|
| P1.1 `_with_baseline`（[advisor.py:39-60](../app/agent/advisor.py#L39-L60)） | Evidence / Reasoning | 扩展为「必需证据确定性预取」，覆盖零工具调用场景 |
| P1.3 `follow_up_questions` | Context / 缺失项追问 | 作为「缺数检测」底座，上移到回答前的最小澄清 |
| V2.4 三层记忆 L2（[memory.py:132-153](../app/agent/memory.py#L132-L153)） | Context / 长期管理 | 扩展 memory_fact 覆盖范围（收入/支出/资产/负债）到 Phase 2 |
| 结论先行 + 图表限 1-2 张（layers.py） | Response | **保持现状，不反向优化**（论断 #7 已排除） |
| 确认卡 `_PENDING`（P3 门） | 解耦后建档写入 | 扩展存储原问题（G3） |
| `build_wealth_context`（[advisor.py:105](../app/agent/advisor.py#L105)） | Context 阶段 | 回答路径的 Context 注入继续使用 |

---

## 7. 顾问 Tools 与 Policy（沿用）

**Tools**（10 个，全部只读 + 确定性）：`get_family_profile` / `get_wealth_overview` / `get_wealth_issues` / `get_cashflow` / `get_allocation` / `get_retirement` / `get_goals` / `run_scenario` / `compare_scenarios` / `create_action`（受 P3 约束）。9 个已有，仅 `create_action` 需 Phase 4 落地。

**Policy**（Tool Calling 不能乱）：

| 用户表述 | 规则 |
|----------|------|
| 问数字（「财富评分多少」） | **必须调 Engine**，不自己报数 |
| 「我该不该 / 要不要」 | 先读家庭 → 读风险 → 必要时 Scenario |
| 信息不足 | **不猜，追问最少必要信息** |
| 纯知识（「什么是复利」） | 直接答，不调 Engine |

---

## 8. 回复结构与人格（沿用）

**人格**：专业 + 克制 + 直接 + 有温度。允许说「这个问题我现在不能直接判断」，说明缺什么——反而提高可信度。

**固定回复骨架**（不自由发挥）：

```
结论 → 为什么 → 我看到的情况(数字+source) → 如果这样做 → 更值得比较(A/B/C) → [帮我比较]按钮
```

**回答长度分级**：数字查询短答 + 追问钩子；决策问题深度答；情绪表达先共情再诊断。

---

## 9. 分阶段实施（Phase 1 具体）

> 每阶段独立 commit，全量回归通过才进下一阶段。契约先行（主纲 §十二）。

### Phase 1a：Advisor Benchmark（先立回归）
- 主纲 §十一 12 题 → `tests/` 回归用例。每题断言：intent 正确 / 是否直接回答 / 是否需澄清 / 确定性工具 / 关键数字 / 证据路径 / 行动建议。
- **红线 #12**：先跑出 12 题基线分数，再改代码，改完对照基线验证不倒退。

### Phase 1b：AdvisorContext 契约
- 定义 pydantic 契约（§5）+ 前端写入 + 后端消费 + 首轮回答。
- 验收：「从 Goals 页点问顾问」第一轮直接回答该目标问题（主纲 §十一 #12，上下文连续性）。

### Phase 1c：两条路径重构
- **跨页面问顾问**（G2 入口侧 + §5 契约消费）。
- **取消建档继续回答**（G1/G3）：`_PENDING` 存原问题；取消分支原问题重新走回答路径。
- **澄清循环**（G4）：Intent 置信度 + Clarify 子状态（Phase 1 先做「低置信度 → 最小澄清」单轮）。

### Phase 2/3（依赖 Phase 1 验收通过）
- Phase 2：档案查询 / 增量建档 / 字段冲突 / 来源追踪 / 缺数检测（数据复用）。
- Phase 3：必需证据确定性预取全覆盖（含零工具调用场景）。

---

## 10. 执行纪律

1. **先 TDD 再实现**：每阶段先写验收测试（Advisor Benchmark + B2 极限 + H 评测），红了再写代码。
2. **一阶段一 commit**：全量回归通过才进下一阶段。
3. **冻结契约零触碰**：需改 Engine/Decision/Schema 就停下报上来。
4. **两错加规则**：同一错误犯 2 次，回写 CLAUDE.md 红线或 gotchas。
5. **技能随用随关**：每阶段结束后关闭该阶段加载的 skill 上下文。
