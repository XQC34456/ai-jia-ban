# AI家办 · V1.0 现状核对报告

> 版本：V1.0 核对 ｜ 2026-08-15
> 依据：《产品正轨重构计划书 V1.0》（`docs/plan-v10-restructure.md`）第四章「当前产品必须纠正的核心问题」
> 方法：三条链路独立取证 —— 后端行为 / 前端 UX / 文档盘点，每条论断给出代码证据与裁定。
> 用途：Phase 1「顾问核心重构」的开工依据；避免凭印象改代码、避免修不存在的 bug。

---

## 一、核对方法

对计划书第四章的 8 条论断逐条取证，证据分三层：

| 链路 | 检查内容 | 证据形式 |
|------|----------|----------|
| 后端行为 | 建档拦截 / 意图路由 / 上下文注入 / 记忆 / 确认卡片 | `app/agent/*.py` 代码行号 |
| 前端 UX | 跨页预填 / 首登向导 / 取消建档行为 | `static/` 代码 + 真机/Playwright 探针 |
| 文档盘点 | 计划书与既有计划文档的对照 | `docs/` 文档清单 |

裁定口径：**真 = 实际发生且构成产品缺陷**；**部分 = 已有缓解但未根治**；**假 = 实际不成立（冤枉）**。

---

## 二、8 条论断裁定总表

| # | 计划书论断 | 裁定 | 一句话依据 |
|---|-----------|------|-----------|
| 1 | 顾问优先建档而非优先回答 | ✅ 真 · 缺口 | 入口第一步拦截建档并返回确认卡，带金额的问题被吞 |
| 2 | 建档流程与问答流程耦合 | ✅ 真 · 缺口 | 建档混在 chat 主链路，无独立向导；onboarding 不写库 |
| 3 | 取消建档导致原问题丢失 | ✅ 真 · 缺口 | 确认卡只存 `{family_id, actions}`，取消即丢弃原问题 |
| 4 | 已有数据被重复询问 | ⚠️ 部分 | 回答路径会预取 Context，但建档路径不查已有数据 |
| 5 | 面对不明确问题无澄清循环 | ✅ 真 · 缺口 | 意图无置信度，失败静默兜底 VIEW_OVERVIEW |
| 6 | 工具调用致证据不稳定 | ⚠️ 部分 | P1.1 已确定化关键数值，但证据 claim 仍 LLM 自由 |
| 7 | 财报/图表主导顾问行为 | ❌ 不成立 | V2.6 已结论先行、图表按意图限 1-2 张 |
| 8 | 跨页问顾问 = 文本预填未消费 | ✅ 真 | draft 纯字符串，后端 `context` 字段空转 |

---

## 三、逐条证据

### 论断 1：顾问优先建档 ✅ 真

- [app/agent/entry.py:37-44](../app/agent/entry.py#L37-L44)：`converse()` 入口，只要消息被判定为建档内容，**第一步**就返回 `create_confirm` 确认卡，根本不进入回答路径。
- [app/agent/profile.py:65-77](../app/agent/profile.py#L65-L77)：`looks_like_filing` 的判定标准是「财务关键词 + 数字」。因此「我月收入 3 万，退休后够不够？」这类**带金额的提问**会被误判为建档，被确认卡吞掉，原问题得不到回答。

**结论**：计划书所述成立。顾问入口的第一行为确实是建档，不是回答问题。

### 论断 2：建档与问答耦合 ✅ 真

- 建档的落地路径是 `/api/agent/chat → 确认卡 → /api/confirm`，与问答共用同一条 chat 主链路（[static/views/chat.js:3](../static/views/chat.js#L3)、[chat.js:169](../static/views/chat.js#L169)）。
- 首登的 `onboarding.js` 三步向导只做**演示画像 preview**，不写数据库（文档盘点：前端 UX 链路结论）。
- 没有独立的建档状态机；「建档」不是一个独立产品流程，而是 chat 的一个分支。

**结论**：成立。建档没有独立入口与流程，混在问答链路里。

### 论断 3：取消建档丢原问题 ✅ 真

- [app/agent/profile.py:20](../app/agent/profile.py#L20)：`_PENDING` 为内存 dict。
- [app/agent/profile.py:80-85](../app/agent/profile.py#L80-L85)：`create_confirm` 只存 `{"family_id", "actions"}`，**不存原始 message**；`apply_confirmation` 取消分支直接 `discarded`，原问题无从找回。
- 建档路径在 [entry.py:40](../app/agent/entry.py#L40) 提前 return，不写入对话记忆，原问题连对话历史都没有。

**边界说明**：首登三步向导（onboarding）从未保存过问题，所以「取消建档丢问题」主要发生在 **chat 对话建档路径**——那里确实丢。首登向导的真实问题是「无跳过入口，锁死用户」，性质不同。

### 论断 4：已有数据被重复询问 ⚠️ 部分

- **已回答部分**：回答路径会注入 `build_wealth_context`（[advisor.py:105](../app/agent/advisor.py#L105)）+ L2 三层记忆（[memory.py:132-153](../app/agent/memory.py#L132-L153)），已备数据会被顾问看到。
- **未根治部分**：
  - L2 记忆只存 **goal 类事实**，收入/支出/资产/负债依赖主表快照，不进 `memory_fact`（[memory.py](../app/agent/memory.py)）。
  - **建档路径不查已有数据**：即便档案里已有收入，「建档确认卡」照样弹出（[entry.py:37-44](../app/agent/entry.py#L37-L44) 无数据复用检查）。

**结论**：计划书所述「重复询问」部分成立——集中在建档路径与 L2 记忆覆盖范围。

### 论断 5：无澄清循环 ✅ 真

- [app/agent/router.py:55-81](../app/agent/router.py#L55-L81)：`route_intent` 走「拒算门 → 确定性关键词 → LLM 兜底 → Literal 校验」，**无置信度概念**，最终失败静默兜底 `VIEW_OVERVIEW`（81 行），不向用户澄清。
- 现有两类「追问」都不是语义澄清：
  - 拒算门的 `disambiguate`：只消解「这笔钱/这个」这类指代。
  - P1.3 `follow_up_questions`：回答后的**缺数检测**（系统缺失数据），不是回答前的低置信度澄清。

**结论**：成立。「澄清 → 引导 → 再回答」的顾问式循环不存在。

### 论断 6：工具调用致证据不稳定 ⚠️ 部分

- **已缓解**：P1.1 `_with_baseline`（[advisor.py:39-60](../app/agent/advisor.py#L39-L60)）在 LLM 已调用工具后，确定性注入 priorities/metrics/evidence 基线，保证关键数值稳定（铁律：数字来自 Engine）。
- **未根治**：
  - evidence 的 claim/解释、tradeoffs、是否调用 `run_scenario` 仍由 LLM 自由决定。
  - LLM 零工具调用时不补基线（[advisor.py:133-134](../app/agent/advisor.py#L133-L134) 仅在有 tool_calls 时执行 `_with_baseline`）。

**结论**：计划书所述「P1.1 已解决主要矛盾基线」属实，但「该原则需继续扩展」也属实——部分成立。

### 论断 7：财报/图表主导顾问行为 ❌ 不成立

- 顾问响应为结论先行结构（`layers.py` 保证「观点 → 证据」顺序），图表按意图限 1-2 张（[app/agent/layers.py:32-51](../app/agent/layers.py#L32-L51)）。
- 六步 SOP（Understand → Diagnose → Explain → Simulate → Recommend → Act）行为导向，财报/图表是结果与证据，不是驱动。

**结论**：该论断**不成立**。顾问已是结论先行、图表从属。**此条不应列入修复范围**，避免反向改动。

### 论断 8：跨页问顾问 = 文本预填未消费 ✅ 真

- 前端 `store.chat.draft` 为**纯文本字符串**（[static/store.js:33](../static/store.js#L33)），Goals/Retirement/Sandbox/Overview 页把文本写入 draft（[static/views/goals.js:21](../static/views/goals.js#L21) 等），chat.js:109 消费进输入框。
- 后端 `AgentRequest.context` 字段存在（[app/schemas/agent.py:173](../app/schemas/agent.py#L173)），但**前端从不发送**——chat.js:167 请求体只有 `{ message }`。即：跨页进顾问 = 复制一段文字，上下文没有结构化成 AdvisorContext 被顾问消费。

**结论**：成立。`context` 字段空转，跨页上下文断层真实存在。

---

## 四、真缺口清单（Phase 1 主攻方向）

按产品影响排序：

| 缺口 | 对应论断 | 用户可见影响 |
|------|---------|-------------|
| **G1 建档优先** | #1 | 带金额的提问被确认卡吞掉，原问题不回答 |
| **G2 建档/问答耦合** | #2 | 只想问个问题，却被要求先建档 |
| **G3 取消建档丢问题** | #3 | 「取消建档 = 问题被中断」 |
| **G4 无澄清循环** | #5 | 不理解时硬答或兜底 Overview，不问 |

四条即 V1.0 计划书 Phase 1（顾问核心重构）的明确改造对象。**修复顺序与方案见 [plan-ai-advisor-core-architecture.md](plan-ai-advisor-core-architecture.md)（六阶段顾问架构）与 [plan-master-roadmap.md](plan-master-roadmap.md)（Phase 0-1）。**

---

## 五、已有基础映射（不重复造，复用为底座）

| 已有能力 | 缓解了 | 复用于 V1.0 的位置 |
|---------|--------|-------------------|
| P1.1 `_with_baseline` 确定性基线 | #6（部分） | 六阶段 Evidence / Reasoning 阶段的"必需证据确定性预取" |
| P1.3 `follow_up_questions` 缺数检测 | #4（部分） | Context 阶段的"只追问缺失且影响答案的数据" |
| V2.4 三层记忆 L2（goal facts） | #4（部分） | 长期管理阶段的记忆底座（扩展 source/confidence） |
| 结论先行 + 图表限 1-2 张 | #7（已达标） | Response 阶段的"先判断再展示"，不反向改 |
| 确认卡 `_PENDING`（P3 铁律） | — | G2/G3 解耦后仍复用为"建档写入前的确认门" |

---

## 六、与计划书其余内容的一致性结论

- **「跨页上下文批评」成立**（#8 真），与计划书第 121-140 行「上下文入口」章节方向一致。
- **「首登向导丢问题」批评不成立**——首登问题从未保存过；真实缺陷是「无跳过、锁死用户」，已在真缺口 G2 下修正表述。
- **论断 7（图表主导）为冤枉**，明确排除出修复范围，避免在 V1.0 里做反向优化。

> 本报告为**一次性核对产物**，保留在 docs/ 供 Phase 1 溯源。若后续代码演进改变了任一裁定，须回写本文（更新行号与结论），保持「现状」二字始终可追溯。
