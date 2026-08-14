# V2.4 Conversation Memory（顾问记忆层）实现计划

> 状态：**规划阶段，待确认后开工。当前只写计划，不改代码。**
> 上一阶段：V2.3 Advisor Brain 已封版（commit `df45207`）。

---

## §0 目标与核心反转

V2.3 让 AI **会思考**（六步 SOP + evidence/priorities/tradeoffs/uncertainty），V2.4 让 AI **记得住**。

**核心反转（一句话）：**

> 从「每次见用户都重新认识这个家庭」→「持续了解这个家庭」。

**明确不做的事：**

- ❌ 不做「把 `messages[]` 存库，下一轮无脑塞回 DeepSeek」——那是 Chat History，不是 Conversation Memory。
- ❌ 不做「LLM 判断旧结论是否失效」——判断必须确定性（延续铁律 P2）。
- ✅ 做「保存 家庭状态 + 顾问判断 + 判断依据 + 判断有效性」，新事实进入时**确定性**识别旧判断是否失效。

**V2.4 要解决的 6 类问题（用户原话）：**

1. 连续追问（「为什么」→「那 55 退休呢」→「那不想降生活质量呢」）
2. 否定重判（「不是买房，是给父母换房」）
3. 新信息重判（「我刚升职，收入增加了」）
4. 目标变化（旧目标不能污染当前建议）
5. 历史事实更新（孩子 8 岁 → 10 岁）
6. 判断失效（上次判断现金流 P0，这次收入翻倍后还成立吗）

---

## §1 架构审计（当前 V2.3 真实状态）

> ⚠️ 注意：`docs/advisor-architecture-audit.md` 是 **V2.2 之前的过时文档**，其「Level 0 / 无 tool calling / LLM 看不到家庭数据」的结论已被 V2.2（9 个只读工具 + tool_loop）和 V2.3（Advisor Brain）推翻。本节基于当前真实代码。

### 1.1 真实链路（逐段对应代码）

```
前端 chat.js send()  →  POST /api/agent/chat  { message }            ← 只传 message，不回传 context/历史
   │                                                       static/views/chat.js:110
   ▼
API  agent_chat() → converse(body.message, user, llm=get_provider(), context=body.context)
   │                                                       app/api/agent.py:25-29（body.context 恒 None）
   ▼
入口 converse()  →  extract_actions() 建档抽取（RuleExtractor 确定性，命中→ConfirmCard）
   │               _wealth_context_text(user)  ← 每次全量 dump_family + build_wealth_context
   │               handle(message, user, llm, context=None, wealth_context=ctx)
   │                                                       app/agent/entry.py:18-28
   ▼
Runtime handle()  ① refusal_gate → ② route_intent → ③ advisor_path（有 LLM 时）
   │                                                       app/agent/runtime.py:42-93
   ▼
advisor_path  advise() → run_advisor() tool_loop
   │   _messages_with_context(message, wealth_context)  ← 把 wealth_context 注入 system prompt
   │   tool_loop：LLM chat 选工具 → execute_tool → 结果回传 → 第二轮推理（MAX_ROUNDS=6）
   │                                                       app/agent/advisor.py:73-116
   ▼
组装 assemble_advisor_response() → AgentResponse{evidence/priorities/tradeoffs/uncertainty}
   │                                                       app/agent/response.py
   ▼
前端 chat.js 渲染 summary/finding/metrics/recommendations/next_actions
```

### 1.2 缺口清单（8 个，按严重度）

| # | 缺口 | 证据 | 后果 |
|---|------|------|------|
| **G1** | **无会话持久化** | app/db.py 表清单：family/users/person/asset/liability/cashflow/goal/reminder/meta/insurance/family_profile/scenario_snapshot —— **无 conversation/message/memory/session 表** | 每次请求独立，无会话 ID，无法关联上一轮 |
| **G2** | **前端只传 message** | chat.js:110 `body: { message: text }`；AgentRequest.context 字段存在但前端从不填 | 后端拿不到任何历史/上下文 |
| **G3** | **wealth_context 每次全量重建** | entry.py:31-34 `_wealth_context_text` 每次 `dump_family + build_wealth_context` | 无增量/缓存，且只有「当前快照」没有「历史」 |
| **G4** | **无跨轮记忆** | advisor.py:63-70 `_messages_with_context` 只拼 `[system(含 wealth_context), user(message)]` | LLM 只看到「当前 message + 当前家庭快照」，看不到上一轮说了什么、调了什么、判断了什么 |
| **G5** | **「当前 vs 历史状态」无区分** | db.apply_action 直接改当前值（profile.py:47），无版本快照 | 用户收入从 3 万变 5 万后，旧值丢失，无法知道「变了」 |
| **G6** | **用户纠正无记忆** | 无任何「用户否定/纠正」记录 | 用户说「不是买房，是给父母换房」，AI 无法关联上一轮，只能重读当前句 |
| **G7** | **AI 过去判断无保存** | priorities[0] 每次 build_issues 重算，算完即弃 | 无「上次判断是现金流 P0，这次收入增加后是否还成立」的失效检测 |
| **G8** | **EXPLAIN_RESULT context 形同虚设** | AgentRequest.context 字段（schemas/agent.py:125-128）前端从不填；Task 5 后 EXPLAIN_RESULT 也走 advisor_path 单轮解释 | 「为什么」的解释没有跨轮依据 |

**一句话归纳**：V2.3 的 AI 会思考，但**每轮都是失忆地思考**。所有上下文（wealth_context）每轮从零重建，所有判断（priorities）算完即弃，所有对话（message）用后即焚。

---

## §2 三层记忆架构

### 2.1 总览

```
                 ┌─────────────────────────────────────────────┐
                 │            Advisor Memory（V2.4 新增）        │
                 │                                              │
   当前事实       │  L1 短期对话记忆   L2 家庭事实记忆  L3 顾问判断记忆 │
   (db 主表)     │  conversation_    memory_fact      advisor_     │
   dump_family   │  message (最近N轮) (source/version) judgment    │
   build_overview│                                              │
        │        └──────────────┬───────────────────────────────┘
        │                       │  结构化摘要（限量，绝不全文堆塞）
        ▼                       ▼
   [当前状态]  ────────►  [Memory Context Builder]  ──►  system prompt
        │                        ▲
        │                        │  新事实写入 → 确定性失效检测
        └────────────────────────┘
```

**边界（延续 V2.3 铁律）：**

- **当前状态真相源**：db 主表 + `build_overview`/`build_issues`（确定性计算，永不 LLM 化）。
- **记忆层**：只存「历史 + 判断 + 依据」，**不参与计算**，只提供上下文。
- 顾问推理永远用**当前状态**；记忆层只负责「告诉 LLM 曾经发生过什么」。

### 2.2 第一层：短期对话记忆（Short-term Conversation Memory）

**目的**：记住最近几轮对话，让追问、纠正、连续决策有上下文。

**存什么**（结构化，非原文堆砌）：

| 字段 | 说明 |
|------|------|
| turn | 轮次 |
| role | user / assistant |
| message | 用户原文（user 轮）或 AI 结论摘要（assistant 轮，**非全文**） |
| intent | AI 判断的意图 |
| tool_calls | 本轮调用了哪些工具（名字列表） |
| corrected | 用户是否否定/纠正了上轮判断 |

**注入策略**：最近 **N 轮**（默认 5，可配）的结构化摘要，逐条压缩为一行，注入 system prompt。**绝不塞原文全文、绝不无限增长。**

### 2.3 第二层：家庭事实记忆（Family Fact Memory）

**目的**：记住用户确认过的家庭事实，区分「聊天里说过」≠「永久事实」。

**核心字段**（用户点名要求）：

| 字段 | 说明 |
|------|------|
| key | 事实键（如 `retirement_age`、`risk_preference`、`child_birth_year`） |
| value | 事实值 |
| source | 来源：`chat_confirmed`（建档确认）/ `onboarding` / `inferred`（对话推断） |
| confidence | `confirmed` / `inferred`（推断的可被覆盖） |
| version | 版本号（同 key 递增） |
| created_at / updated_at | 时间戳 |
| superseded_by | 被哪个新版本取代（NULL = 当前有效） |

**关键机制：聊天里说过 ≠ 永久事实。** 只有「用户确认建档」（`apply_confirmation`）才写入 `confidence=confirmed`；对话中 LLM 推断的写入 `confidence=inferred`，可被更高置信度事实覆盖。

**与 db 主表的关系（重要）**：db 主表（person/asset/liability/cashflow/goal）是「当前净值事实」真相源，**不进 memory_fact**。memory_fact 只存 db 主表没有的**顾问知识类事实**（退休计划、风险偏好、口头目标、纠正记录）。两者不重叠、不重复。

### 2.4 第三层：顾问判断记忆（Advisor Judgment Memory）

**目的**：记住「上次主要矛盾是什么、为什么、什么条件下成立」，新事实进入时识别失效。

**存什么**：

| 字段 | 说明 |
|------|------|
| priorities | 上次主要矛盾（Decision 的 priorities，只读不改序） |
| evidence | 判断依据（EvidenceRef 序列化） |
| recommendation | 上次建议 |
| validity_conditions | **有效条件快照**：判断时依赖的关键事实值（如 `{"monthly_income": 30000, "dti": 0.4}`） |
| status | `active` / `stale` |
| created_at / invalidated_at | 时间戳 |

**失效检测（确定性，不 LLM）**：新对话时，重新 build 当前状态，与 `validity_conditions` 逐 key 对比。任一 key 值变化 → 标记 `stale`，并在注入时提示 LLM「上次判断依赖的 X 已从 A 变为 B，需要重新评估」。

---

## §3 数据结构（DB 新增 3 张表）

> 全部落在 app/db.py，沿用现有 sqlite3 + `CREATE TABLE IF NOT EXISTS` 风格。**只加表，不改现有表结构。**

```sql
-- L1 短期对话
CREATE TABLE IF NOT EXISTS conversation_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    turn INTEGER NOT NULL,
    role TEXT NOT NULL,               -- user / assistant
    message TEXT,                     -- 用户原文 / AI 结论摘要
    intent TEXT,                      -- AI 判断意图（assistant 轮）
    tool_calls TEXT,                  -- JSON 数组：本轮调用工具名
    corrected INTEGER DEFAULT 0,      -- 用户是否否定上轮
    created_at TEXT NOT NULL
);

-- L2 家庭事实
CREATE TABLE IF NOT EXISTS memory_fact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,             -- chat_confirmed / onboarding / inferred
    confidence TEXT NOT NULL,         -- confirmed / inferred
    version INTEGER NOT NULL,
    superseded_by INTEGER,            -- 指向新版本 id；NULL = 当前有效
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- L3 顾问判断
CREATE TABLE IF NOT EXISTS advisor_judgment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    priorities TEXT NOT NULL,         -- JSON：PriorityRef 列表
    evidence TEXT,                    -- JSON：EvidenceRef 列表
    recommendation TEXT,
    validity_conditions TEXT NOT NULL,-- JSON：{key: value} 判断时事实快照
    status TEXT NOT NULL,             -- active / stale
    created_at TEXT NOT NULL,
    invalidated_at TEXT
);
```

**约束**：

- `conversation_message` 按 `(family_id, turn)` 查询最近 N 轮；**不设上限增长防护**（见 §4 限量注入 + 可选清理策略）。
- `memory_fact` 每个 key 最多一条 `superseded_by IS NULL` 的记录（当前有效版本唯一）。
- `advisor_judgment` 每个 family 最多一条 `status='active'`（新判断写入时旧 active 置 stale）。

---

## §4 注入机制（怎么喂给 LLM，防无脑塞）

**铁律（用户 #7、#8）：不允许把所有历史消息无脑塞给 DeepSeek；Memory 必须有明确结构化 Context，不允许无限增长。**

新增 **Memory Context Builder**（纯函数，零 LLM、零计算）：

```
build_memory_context(family_id) -> str
  ├─ L1：最近 N=5 轮对话摘要，每轮一行：
  │     [1] 用户:「为什么养老有问题」 → AI:CHECK_RETIREMENT 调 get_retirement
  │     [2] 用户:「那 55 退休呢」(纠正退休假设) → AI:重新评估 RFR/NWC
  ├─ L2：当前有效的顾问知识事实，每条约一行：
  │     · 计划退休年龄 55（source=chat_confirmed, v2）
  ├─ L3：最近一次判断（若 active）：
  │     · 上次主要矛盾：现金流 P0（依据：月结余 -10000）
  │     ⚠️ 若 stale：附「已失效：月收入 30000→50000，请重新评估」
  └─ 合成一段结构化文本，注入 advisor 的 system prompt（在 wealth_context 之后）
```

**限量规则**：

- L1 固定最近 5 轮；超出截断，**永不全文堆塞**。
- L2 只注入「当前有效」事实（`superseded_by IS NULL`），历史版本不注入（仅供失效检测）。
- L3 只注入「最近 1 次判断」，旧的 active 被覆盖后不保留注入。
- 三者合计有 token 预算上限（如 2000 字），超限时 L1 递减轮数、L2 只取 confirmed。

**注入位置**：`advisor.py` 的 `_messages_with_context` 目前只拼 `[system(wealth_context), user(message)]`，V2.4 改为 `[system(wealth_context + memory_context), user(message)]`。**不改 LLMProvider 协议，不改 DeepSeek 实现。**

---

## §5 失效检测（新事实 → 旧判断失效）

**确定性机制，绝不让 LLM 判断失效**（延续铁律 P2：判断确定性，LLM 只组织语言）。

```
写入 advisor_judgment 时：
  validity_conditions = 当前 build_overview 的关键值快照
    （如 {"monthly_income": 30000, "monthly_surplus": -10000, "dti": 0.4, "rfr": 0.6}）

下次对话时：
  current = 重新 build_overview 的对应值
  changed = [k for k in validity_conditions if validity_conditions[k] != current[k]]
  if changed:
      advisor_judgment.status = 'stale'
      memory_context 里注入「⚠️ 上次判断依赖的 monthly_income 已从 30000 变为 50000」
```

**有效条件快照的来源**：不是所有 overview 字段，而是「上次判断依据里出现过的 metric_key」+ 一个固定最小集（月收入/月结余/DTI/应急月数/房产占比/RFR）。这样避免无限快照，且精确对焦「判断依据变了没」。

---

## §6 数字防编造延续（冻结契约）

V2.4 全程不触碰 V2.2/V2.3 的防编造底座，且记忆层本身也要防编造：

- **L2 事实 value 来自哪**：`chat_confirmed` 的事实 value 来自确认建档时的 `db.apply_action`（确定性）；`inferred` 事实 value 来自 LLM 输出 → **必须过「数字防编造闸」**（含数字的 value 必须能溯源到 db 或明确标注 source，否则不写入）。
- **L3 判断的 priorities/evidence**：直接序列化 V2.3 的 `PriorityRef`/`EvidenceRef`（数字带 source），**不经过 LLM 二次加工**。
- **注入的 memory_context 只描述「历史发生了什么」，绝不注入 LLM 新造的财富数字**。

**冻结项（V2.4 不改）**：Engine（app/engine/）、Decision（app/decision/）、场景契约 C3.5（schemas/scenario.py）、Agent 输出 Schema A1（schemas/agent.py 的 MetricRef 防编造硬闸）、A2 工具只读 + VIP 门（tools.py）、LLMProvider 协议（provider.py）。

---

## §7 TDD 任务分解（7 个任务，待确认后按序执行）

> 每任务按「先写测试 → 跑红 → 实现 → 跑绿 → commit」执行。测试目录 `tests/`。

### Task 0: Memory 存储 Schema（3 张新表 + CRUD）

**文件**：Modify `app/db.py`（新增建表 + 5 个 CRUD 函数）
**测试**：`tests/test_v24_memory_db.py`

- `init_db()` 建 3 张表（幂等）
- `append_conversation(family_id, role, message, intent, tool_calls, corrected)`
- `recent_conversations(family_id, n)` → 最近 n 轮（按 turn 倒序）
- `upsert_fact(family_id, key, value, source, confidence)` → 版本化（同 key 新版本 supersede 旧版本）
- `current_facts(family_id)` → 当前有效事实（superseded_by IS NULL）
- `save_judgment(family_id, priorities, evidence, recommendation, validity_conditions)` → 旧 active 置 stale
- `latest_judgment(family_id)` → 最近判断（含 stale）

### Task 1: 短期对话记忆（写入 + 限量读取 + 摘要）

**文件**：Modify `app/agent/entry.py`（converse 前后写 conversation_message）；新增 `app/agent/memory.py`（摘要 builder）
**测试**：`tests/test_v24_conversation_memory.py`

- converse 每轮写入 user 轮 + assistant 轮（assistant 存结论摘要，非全文）
- `build_conversation_summary(family_id, n=5)` 生成结构化摘要，每轮一行
- 限量：n 轮截断，不全文堆塞

### Task 2: 家庭事实记忆（source/timestamp/confidence/version）

**文件**：Modify `app/agent/profile.py`（apply_confirmation 确认建档时写 memory_fact）
**测试**：`tests/test_v24_fact_memory.py`

- 确认建档 → `upsert_fact(confidence='confirmed')`
- 同 key 新事实 → version +1，旧版本 superseded_by 指向新 id
- `current_facts` 只返回当前有效版本
- 数字 value 防编造：含数字但无 source 的 inferred 事实不写入

### Task 3: 顾问判断记忆（主要矛盾 + 依据 + 有效条件快照）

**文件**：Modify `app/agent/response.py` 或新增（在 assemble 后写 judgment）
**测试**：`tests/test_v24_judgment_memory.py`

- advisor 产出 priorities 后，`save_judgment` 写入 priorities + evidence + validity_conditions（从 tool_results 提取关键值快照）
- `latest_judgment` 返回最近判断
- 新判断写入时旧 active 置 stale

### Task 4: 判断失效检测（新事实 → 旧判断 stale）

**文件**：Modify `app/agent/memory.py`（失效检测函数）
**测试**：`tests/test_v24_invalidation.py`

- 确定性：当前状态 vs validity_conditions 逐 key 对比，变化 → stale
- 收入变化（30000→50000）→ 标记 stale + 注入「已失效」提示
- 无变化 → 保持 active，不提示

### Task 5: Memory 注入 advisor（结构化摘要进 system prompt）

**文件**：Modify `app/agent/advisor.py`（_messages_with_context 拼接 memory_context）+ `app/agent/entry.py`（预取 memory_context）
**测试**：`tests/test_v24_injection.py`

- `build_memory_context` 合成三层摘要（L1 最近 5 轮 + L2 当前事实 + L3 最近判断）
- 注入 system prompt（在 wealth_context 之后）
- 限量：token 预算超限时递减 L1 轮数
- stale 判断附「已失效」提示

### Task 6: 端到端（连续追问 / 否定重判 / 新信息重判 / 目标变化 / 历史事实更新 / 判断失效）

**文件**：`tests/test_v24_e2e.py`
**测试**：6 类多轮场景（见 §8），用 FakeLLMProvider 驱动多轮对话，断言记忆正确注入 + 判断正确失效 + 数字不编造。

---

## §8 验收场景（不能只测「第二轮能看到第一轮消息」）

用户原话：验收不能只测「第二轮能看到第一轮消息」，要测**连续追问 / 否定重判 / 新信息重判 / 目标变化 / 历史事实更新 / 判断失效**。设计以下 6 类（每类 2~3 条，共约 15 条多轮场景）：

| 类 | 场景示例 | 断言 |
|----|---------|------|
| ① 连续追问 | 「为什么养老有问题」→「那 55 退休呢」→「那不想降生活质量呢」 | 第 3 轮 AI 仍知道在谈养老 + 退休年龄假设，不重问已答问题 |
| ② 否定重判 | 「买房」→「不是，是给父母换房」 | 第 2 轮 AI 识别纠正，重新调工具，不坚持旧结论 |
| ③ 新信息重判 | 「我的现金流问题」→「我刚升职，收入从 3 万到 5 万」 | 判断失效：现金流 P0 → 重新评估，validity_conditions 变化触发 stale |
| ④ 目标变化 | 「教育金 50 万」→「改成教育金 30 万」 | 新目标覆盖旧目标，旧目标不污染当前建议 |
| ⑤ 历史事实更新 | 「孩子 8 岁」→ 三周后「孩子 10 岁了」 | version +1，旧事实 superseded，不误导 |
| ⑥ 判断失效 | 判断现金流 P0 → 收入翻倍 → 再问「我最大风险」 | 旧判断标 stale，AI 明确说「之前判断需重新评估」 |

---

## §9 冻结契约（V2.4 不改）

| 冻结项 | 位置 | 理由 |
|--------|------|------|
| Engine（财富计算） | app/engine/、services/scenario.py、build_overview 公式 | 数字唯一真相源 |
| Decision（问题检测） | app/decision/build_issues 7 detector | 判断唯一真相源 |
| 场景契约 C3.5 | schemas/scenario.py SCENARIO_NAMES/SCENARIO_PARAM_MODELS | 新增场景必须改这里 |
| Agent 输出 Schema A1 | schemas/agent.py AgentResponse/MetricRef | 防编造硬闸，可扩不可削 |
| A2 工具只读 + VIP 门 | agent/tools.py | 工具=获取事实，绝不计算 |
| LLMProvider 协议 | agent/provider.py | 换模型不换财富系统 |

**V2.4 改动面**（全部在 A 层 + 新增 memory 层）：db.py（加表）、agent/memory.py（新增）、agent/entry.py（注入）、agent/advisor.py（拼接）、agent/profile.py（写事实）、schemas/agent.py（AgentRequest 加 session 字段，可选）。

---

## §10 范围外（V2.5 / V2.6，本次不做）

- 主动管理 / 主动发现问题（V2.5）
- 长期 Agent / 自动执行动作（V2.6，create_action 已预留）
- 用户偏好学习 / 个性化人格
- 多家庭切换 / 多用户协作
- 事实冲突的 LLM 仲裁（保持确定性）

---

## §11 决策点（待你确认后开工）

> 以下 4 点是我在设计中遇到的分叉，需要你拍板。确认后我严格按本计划 + 你的选择 TDD 推进。

**D1. 会话粒度**：会话按 `family_id`（一个家庭一个长期会话，无需显式 session 创建）还是每次前端生成独立 `session_id`？
- 推荐：**family_id 维度**（最简单，符合「长期顾问」定位；一个用户一个家庭，前端零改动）。

**D2. 短期记忆注入内容**：注入「结构化摘要」（每轮压缩成一行）还是「摘要 + 原文」？
- 推荐：**纯结构化摘要**（不塞原文，token 可控，防噪音，符合 #7「不无脑塞历史」）。

**D3. 家庭事实记忆的写入来源**：只从「确认建档」写 confirmed，还是「确认建档 + 对话 LLM 推断」双写（inferred 低置信度）？
- 推荐：**双写**——confirmed（建档确认，不可自动覆盖）+ inferred（对话推断，可被覆盖）。这是「聊天说过 ≠ 永久事实」的直接落地。

**D4. 前端是否回传 session**：服务端按 family_id 自动关联历史（前端只传 message，改动最小），还是前端显式传 session_id/历史？
- 推荐：**服务端自动关联，前端零改动**（后端自己从 DB 读历史，前端 chat.js 保持只传 message）。

---

## §12 用户确认 + 4 条硬约束 + 验收重点

> 2026-08-14 用户确认：D1～D4 全部按推荐方案通过。开工时追加 4 条硬约束 + 4 类验收重点。

### 硬约束（V2.4 铁律，优先级高于一切实现细节）

1. **当前数据永远高于记忆**：记忆层不能成为财富计算的数据源。历史记录说「月收入 3 万」，当前家庭数据已是 5 万 → AI 必须以 5 万为准。Engine/Decision 只读 `db.dump_family()` 当前值，**绝不读 memory 表**。
2. **inferred 绝不能伪装成 confirmed**：聊天里「我应该明年会买房」只能记 `source=conversation, confidence=inferred`，绝不写成 `user_confirmed`。source/confidence 由**写入位置**决定（建档确认=confirmed，对话推断=inferred），不由 LLM 决定。
3. **历史事实不能偷偷参与财富计算**：历史 3 万只能回答「收入过去一年发生了什么变化」，**绝不能**被 Engine 当当前收入重算财富指标。
4. **Advisor 必须知道「为什么重新判断」**：判断失效时，AI 不是机械重答，而是理解「上次判断建立在月收入 3 万的基础上，现在变成 5 万，需重新评估」。这由 §5 的确定性失效检测 + 注入的「已失效」提示实现，**不是 LLM 自己猜**。

### 验收重点（不能只测「记住上一句话」）

- **A. 连续理解**：买房 → 预算 700 万 → 首付 200 万 → 现在能不能买，逐步形成完整上下文。
- **B. 用户纠正**：「你刚说我现金流风险最高，但我算错了，月收入其实是 5 万」→ 更新事实 → 重新调工具 → 重新判断，不坚持旧结论。
- **C. 家庭状态变化**：收入 3 万 → 5 万，AI 知道当前状态已变化。
- **D. 判断失效**：旧判断依赖收入 3 万 → 收入变 5 万 → 旧判断 stale → 重新评估。**失效检测必须由确定性代码完成，不是 LLM 说「可能过时了」。**

---

## §13 交付报告要求（完成后）

7 个 Task 对应 commit；pytest / node / e2e 全量结果；15 条多轮场景逐项结果；失败场景及原因；V2.5 主动管理能力边界；是否达到 V2.4 验收标准（6 类问题全解决 + 铁律 10 条不破）。
