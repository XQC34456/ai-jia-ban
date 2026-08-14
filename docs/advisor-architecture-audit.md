# AI Advisor 架构审计报告

> 日期：2026-08-14 · 纯审计，0 代码改动。
> 结论先行：**当前「AI 顾问」不是 AI 顾问，是一个「确定性规则引擎 + LLM 做意图路由和数字抽取的前置插件」。**
> 严格按你给的 5 级定义，它连 Level 1（文案润色器）都够不着，处于 **Level 0**。

---

## 一、当前架构图（真实链路，逐段对应代码）

```
用户输入 message
   │
   ▼
[前端 chat.js]  send()  →  POST /api/agent/chat  { message }        ← 只传 message，不带 context、不带历史
   │                                                        static/views/chat.js:110
   ▼
[API 层]  agent_chat() → converse(body.message, user, llm=get_provider(), context=body.context)
   │                                                        app/api/agent.py:25-29（body.context 恒为 None）
   ▼
[入口]  converse()  →  先 extract_actions() 建档抽取（RuleExtractor 确定性），命中→ConfirmCard；否则→handle()
   │                                                        app/agent/entry.py:12-21
   ▼
[Runtime]  handle()  编排链                                            app/agent/runtime.py:36-72
   │  ① 拒算门 refusal_gate()  ────────────────────────────── app/agent/router.py:39-51
   │  ② 意图路由 route_intent()  ── 确定性关键词 → LLM 兜底 → Literal 校验 → VIEW_OVERVIEW
   │                                                    app/agent/router.py:54-69
   │  ③ SCENARIO_COMPARE 需 extract_scenario_params()（LLM 抽数字）app/agent/params.py:75-87
   │  ④ dispatch(intent)  ── intent → 固定工具映射（纯字典）app/agent/dispatch.py:23-30
   │  ⑤ build_response()  ── metrics 取数 + finding/recommendations 确定性推导
   │                                                    app/agent/response.py:185-209
   ▼
[A2 工具]  get_overview / get_issues / get_goals / compare_scenario  → 调 service 层（build_overview / build_issues / build_goals / compare_scenarios）
   │                                                        app/agent/tools.py:53-93（只读，零计算）
   ▼
[Engine/Decision]  确定性财富计算（冻结契约）
   ▼
[响应组装]  AgentResponse { intent, status, summary, finding, metrics[], recommendations[], next_actions[], limitations, source[] }
   │                                                        app/schemas/agent.py:76-86
   ▼
[前端]  chat.js 渲染 m.agent.summary / finding / metrics / recommendations / next_actions
```

**DeepSeek 只在 3 个点被调用，且全是「结构化 JSON 抽取」，没有一处生成对话自然语言：**

| 调用点 | 位置 | 角色 |
|--------|------|------|
| 意图路由兜底 | app/agent/router.py:59-68 | 分类（只输出 7 意图之一） |
| 场景参数抽取 | app/agent/params.py:75-87 | 从自然语言抽数字参数 |
| 建档抽取（**已禁用**） | app/extraction.py:275 `LLMExtractor` | 被 profile.py:25 用 `RuleExtractor` 确定性替代 |

**唯一例外**（不在对话主链路里）：深度报告 `/api/report` 的「综合建议」章节 `app/report.py:75-110` `_llm_advice()`，这才是全项目唯一一处「把家庭数据喂给 LLM、让 LLM 生成自然语言」的地方——但它独立于 AI 顾问对话，前端 chat.js 的「深度报告」弹窗是另一个按钮，走的 `/api/report`。

---

## 二、A–F 逐项回答（全部引用真实代码，非推测）

### A. DeepSeek 有没有真正参与推理？

**没有参与任何「推理」，只做「抽取/分类」。**

- 协议 `LLMProvider.complete_json(system, user, schema)` 只有 3 个入参（app/agent/provider.py:13-17），**没有 messages 数组、没有多轮、没有工具定义**。
- `DeepSeekProvider.complete_json` 拼的 messages 是 `[system, user]`，user 就是**原始用户消息**（app/agent/providers/deepseek.py:40-47），没加任何家庭数据。
- 对话主链路（runtime → response）里，DeepSeek 的输出**不进入 summary / finding / recommendations**——这三者分别是固定模板和字段拼接，见 C。

### B. DeepSeek 每次到底看到了什么？

**只看到「系统提示词 + 用户原始 message + JSON Schema」。看不到任何家庭数据。**

- 意图路由的 system 是 `_ROUTER_SYSTEM`（app/agent/router.py:15-20），只让输出 intent。
- 参数抽取的 system 是「从用户消息提取情景参数」（app/agent/params.py:80-84）。
- **DeepSeek 完全没有看到**：家庭数据、overview、priorities、issues、metrics、recommendations、scenario 结果、沙盘状态、当前页面、历史对话、用户选择、上一轮回答、MetricRef、next_actions、source——**一项都没有**。

对照你列的清单，除了「用户原始 message」以外，其余全为 **否**。唯一能看到家庭数据的地方是 report.py 的 `_llm_advice`（它把 snapshot+problems 序列化进 user content，app/report.py:86-102），但那条链路不进 AI 顾问对话。

### C. 是否只是「模板 + LLM 润色」？

**比这更原始：连「LLM 润色」都没有。是「纯模板 + 确定性字段拼接」。**

- summary：7 句写死模板 `_OK_SUMMARY`（app/agent/runtime.py:23-31）。同一 intent 永远同一句话。
- finding：`_derive_finding`（app/agent/response.py:212-231）是 `"；".join(f"{title}：{finding}")` 之类的字符串拼接。
- recommendations：`_derive_recommendations`（app/agent/response.py:234-257）是 `f"{action}：{detail}"` 拼接。
- LLM 在对话主链路里**不产出任何自然语言**。它只决定「intent 是哪个」和「消息里的数字是多少」。

### D. 是否存在真正的工具调用？

**不存在。工具选择是「intent → 固定工具」的硬编码字典，不是 LLM 决策。**

- `INTENT_TOOL`（app/agent/dispatch.py:12-20）+ `dispatch()`（dispatch.py:23-30）：intent 一旦确定，调哪个工具是写死的。
- LLM 只负责输出 intent（还只是兜底，关键词优先）。LLM **不能**根据上下文选择「查询 vs 解释 vs 启动 scenario vs 修改参数 vs 比较 vs 查看历史」——这些能力被硬编码成 7 个意图，且 `EXPLAIN_RESULT` 因 context 恒为 None 而永远走「请先查看某个结果」分支（app/agent/runtime.py:64-68）。
- DeepSeek 的 function-calling 能力（`tool_choice`）只出现在被禁用的 `LLMExtractor`（app/extraction.py:301），主链路完全没用到。

### E. 多轮对话是否真正存在？

**不存在。完全无状态，单轮即弃。**

- 前端 `send()` 只 POST `{ message }`（chat.js:110），**从不回传历史**。
- 后端 `AgentRequest` 虽有 `context` 字段（app/schemas/agent.py:89-92），但前端从不填，`body.context` 恒为 None。
- 前端 `store.chat.messages`（static/store.js:32）只是**本地展示数组**，不回传、不落库；登出即清空（store.js:66）。
- DB 无任何 conversation/message 表（app/db.py 表清单：family/users/person/asset/liability/cashflow/goal/reminder/meta/insurance/family_profile/scenario_snapshot——**无对话/会话表**）。

你给的测试「为什么养老有问题？→ 那多存5000呢？→ 如果不想多存呢？」：
- 第 1 句：关键词「为什么」命中 `EXPLAIN_RESULT`（router.py:30），但 context=None → 走「请先查看某个结果」分支，**无法解释「养老有问题」**（因为它根本不知道上一轮讲了养老）。
- 第 2 句：「多存5000」无任何关键词 → 兜底 LLM 意图路由或 VIEW_OVERVIEW，**完全丢失「养老」语境**。
- 第 3 句：同理，**毫无上下文**。

### F. 属于哪一级？

**Level 0**（确定性规则引擎，LLM 仅作「意图分类 + 数字抽取」前置）。连 Level 1「LLM 文案润色器」都没达到——因为对话回答没有一行字是 LLM 生成的。

---

## 三、当前问题清单（按严重度）

| # | 问题 | 证据 | 后果 |
|---|------|------|------|
| P0-1 | **对话回答是写死模板，LLM 不生成自然语言** | runtime.py:23-31 `_OK_SUMMARY`；response.py:212-257 字段拼接 | 用户问任何「为什么/怎么调/合不合适」，得到的都是模板 + 字段罗列，无「顾问感」 |
| P0-2 | **LLM 看不到家庭数据** | provider.py:16 协议只有 3 参；deepseek.py:40-47 messages=[system, user 原始消息] | LLM 无法针对「你家」说话，只能当分类器 |
| P0-3 | **无多轮记忆，单轮即弃** | chat.js:110 不回传历史；schemas/agent.py:89 context 恒 None；db.py 无对话表 | 追问、澄清、连续决策全部失效 |
| P0-4 | **`EXPLAIN_RESULT`（「为什么」）是死分支** | runtime.py:64-68 context=None 时永远 need_clarification | 用户最核心的「为什么」诉求，产品上就是坏的 |
| P1-5 | **意图路由靠关键词，脆弱** | router.py:23-31 关键词表 | 换个说法（「我退休后钱够花吗」）→ 关键词「退休」能中，但「够花」这种口语可能落 VIEW_OVERVIEW 兜底 |
| P1-6 | **工具选择硬编码，无自主调用** | dispatch.py:12-20 INTENT_TOOL | 无法做「理解→查数→发现异常→再查→给结论」的链式动作 |
| P1-7 | **无评价闭环** | 无评测代码 | 改不动、不敢动，只能靠人肉验收 |
| P2-8 | **建档抽取 LLM 能力闲置** | extraction.py:275 被 profile.py:25 确定性替代 | 不是问题，是刻意的安全选择（防 LLM 幻觉污染数据），保留 |

---

## 四、为什么用户会感觉「不智能」（本质归纳）

1. **每句话都是模板**：`_OK_SUMMARY` 一共 7 句，同一意图永远是同一句。用户换着问，回答不变——这是「不智能」最直接的体感。
2. **LLM 与家庭数据完全隔离**：DeepSeek 从头到尾没看过你家任何数字，所以它说不出任何「针对你」的话。它只是「告诉你该调哪个查询」的开关。
3. **没有记忆**：每次都是陌生人第一次对话。你追问，它失忆。
4. **「为什么」是坏的**：`EXPLAIN_RESULT` 因为 context 永远为空而永远走兜底。用户最想听的解释，恰恰是断的。
5. **「顾问」名不副实**：当前架构叫「AI 家办顾问」，但实际上是「确定性财富报表 + 一个 NLP 分类器」。方向没错（确定性计算是对的、铁律是对的），但「AI 顾问」这一层**还没开工**——它只搭了骨架（分层 + 契约 + 防编造闸），还没装「理解、上下文、推理、对话」这四个引擎。

一句话：**骨架是对的，灵魂是空的。** 你现在不是要「改文案」，是要「把 AI 顾问这一层真正建起来」。

---

## 五、从 Level 0 → Level 5 的最小改造路径

> 原则：**确定性财富计算（Engine/Decision）纹丝不动**，全部改造落在 A 层（Agent 交互层）+ 新增的「上下文/记忆」层。这就是你之前设想的 A→H 阶段，我把它映射到具体改造点：

| 阶段 | 目标 | 关键动作 | 对应你的阶段 |
|------|------|----------|--------------|
| 1 | **Advisor Context** | 新建「上下文构建器」：把 `build_overview`/`build_issues` 结果 + 家庭画像 + 上一轮结果，打包成 LLM 能看的结构化 context；替换 `complete_json(system, user, schema)` 的协议，让 provider 能收 context | B |
| 2 | **Intent + Routing 强化** | 保留确定性关键词（快、稳、零成本），但把 LLM 兜底升级成「带上下文的理解」；修复 `EXPLAIN_RESULT` 死分支 | C |
| 3 | **Tool Layer 开放** | 让 LLM 真正通过 function-calling 选择工具（get_overview/issues/goals/compare_scenario），而不是硬编码 intent→tool；工具仍只读、仍不计算 | D |
| 4 | **Agent Loop** | 引入「理解→查数→发现异常→再查→模拟→给结论」的多步循环，LLM 决定何时查什么 | E |
| 5 | **Memory** | 新增对话历史（DB 表 or 会话态），把上一轮意图/结论/数字塞回 context，让追问有记忆 | F |
| 6 | **Advisor UX** | 对话升级：自然语言回答（LLM 生成，但数字仍从 MetricRef 引用、不可编造）+ 依据可追溯 + 下一步按钮 | G |
| 7 | **Evaluation** | 30~50 条黄金场景（含「为什么养老有问题→多存5000→不想多存」这类多轮），做回归评测 | H |

**核心铁律延续**：LLM 可以**生成文字、组织上下文、决定查什么**，但**数字永远来自 Engine 返回 + MetricRef 的 source 硬闸**。防编造闸（schemas/agent.py:68-73）必须在新协议里继续生效——这才是 Level 5「财富 Agent」的安全底座。

---

## 六、哪些必须继续冻结（Engine / Decision / Schema）

| 冻结项 | 位置 | 理由 |
|--------|------|------|
| **Engine**（财富计算） | app/engine/、app/services/scenario.py 的 `compare_scenarios`、`build_overview` 内部公式 | 数字唯一真相源，绝不 LLM 化 |
| **Decision**（问题检测） | app/decision/ `build_issues` 7 个 detector | 判断唯一真相源 |
| **场景契约 C3.5** | app/schemas/scenario.py `SCENARIO_NAMES` / `SCENARIO_PARAM_MODELS` | 新增场景必须改这里，再由 contract test 逼同步 |
| **Agent 输出 Schema A1** | app/schemas/agent.py `AgentResponse` / `MetricRef` | 防编造硬闸，可扩展字段但不可削弱 |
| **A2 工具只读 + VIP 门** | app/agent/tools.py | 工具 = 获取事实，绝不计算 |

---

## 七、哪些新增能力应该放在 AI Advisor 层（而非 Engine/Decision）

| 新增能力 | 归属层 | 说明 |
|----------|--------|------|
| 上下文构建器（context builder） | **Advisor 新层** | 把 Engine 结果打包成 LLM 可读上下文，是「让 LLM 看见数据」的关键，Engine 不感知 |
| 对话历史 / 记忆 | **Advisor 新层** | 存储与回填上一轮意图/结论/数字；Engine 无状态 |
| LLM 自然语言回答生成 | **Advisor 新层** | 只有文字生成归 LLM；数字仍从 MetricRef 引用 |
| 工具选择（function-calling） | **Advisor 新层** | 让 LLM 决定查什么；查的动作仍走只读 A2 工具 |
| 多步 Agent Loop | **Advisor 新层** | 编排「查数→发现→再查→模拟→结论」 |
| 评测集（30~50 场景） | **Advisor 新层** | 回归护栏，保证改 LLM 提示词不破坏财富正确性 |

**一句话边界**：Engine/Decision 继续「只会算、只会判断」，Advisor 层负责「会理解、会对话、会记忆、会调用」——两者之间靠 **MetricRef.source 防编造闸** 焊死。

---

## 八、审计结论

1. 当前 AI 顾问 = Level 0（确定性报表 + NLP 分类器），不是 AI 顾问。
2. 骨架（分层、契约、防编造、VIP 门）全部正确且值得保留，**问题不在骨架，在「理解/上下文/记忆/对话」四个引擎还没装**。
3. 唯一的「真 LLM 自然语言」在 `/api/report` 的 `_llm_advice`——它已经证明了「喂家庭数据 → LLM 生成自然语言」可行，可作改造范本。
4. 升级路径清晰、可分阶段、每阶段可独立验收，且全程不碰 Engine/Decision 冻结契约。

**等你确认后，我们再拆成《AI Advisor Core Architecture v1》总计划，按 A→H 阶段 TDD 推进。**
