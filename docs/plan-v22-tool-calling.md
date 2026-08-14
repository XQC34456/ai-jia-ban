# V2.2 Tool Calling · 实施计划

> 唯一主体计划的 **V2.2 阶段展开**。依据 [plan-ai-advisor-core-architecture.md](plan-ai-advisor-core-architecture.md) §10 + [plan-master-roadmap.md](plan-master-roadmap.md) §4。
> 前置：V2.1 Context Engine 已完成（`build_wealth_context` + provider 注入通道就位）。

---

## 0. 一句话目标与核心反转

**让 AI 顾问从「会调用工具的聊天机器人」变成「能针对真实家庭问题完成多步决策链路的顾问」。**

不是这个（错误方向）：

```
DeepSeek → 选择工具 → 工具返回 JSON → 直接回答   ← 还是聊天机器人
```

而是这个（顾问感）：

```
用户 → AI Advisor
        ├── 理解问题/识别意图
        ├── 已知 Context？→ 判断需要什么信息
        │        └── 信息不足 → 反问用户（不猜）
        ├── Tool Calling → Engine / Decision / Sandbox
        ├── 拿到结构化事实 + source
        ├── DeepSeek 第二轮推理 → 风险/权衡/建议
        └── 顾问式回答（数字来自 Engine，LLM 只做人话）
```

**V2.2 验收不是「9 个工具调用成功」，而是「针对真实家庭问题，完成正确的多步决策链路」。**

---

### 最高产品原则（凌驾于一切实现细节）

> **Tool 是 AI 顾问的能力，不是 AI 顾问本身。**
> 用户体验必须是「顾问在和我交流」，而不是「AI 在调用 9 个接口」。

四条硬约束：

1. **前端绝不暴露 Tool 调用过程**。工具链是「眼睛和手」，调用轨迹、`data_origin`、`source`、`issue_id` 一律不面向用户；用户只看到一段自然的顾问对话。
2. **意图模糊时先自然追问，不机械 tool_loop、不机械 refuse**。例：
   > “你是想知道复利本身怎么计算，还是想看看复利对你家庭未来资产有什么影响？”
   明确目的后再决定调不调 Tool。
3. **数字防错全收**：涉及家庭资产/负债/现金流/退休/配置等数字，必须来自 Engine/Tool，由前端/AgentResponse 注入可追溯数字；LLM 不编造、不计算。
4. **fail-open 不中断对话**：Tool 失败/数据不足/参数不明 → 不编数字 → 明确告诉缺什么 → 必要时追问 → 能给原则性建议就给 → 不能算就不假装算出来。

**产品大方向**：AI 顾问是产品中枢，其他功能（数据/沙盘/决策/行动）都是它的能力模块——
`AI 顾问 → 理解家庭 → 获取数据 → 分析问题 → 调用沙盘 → 比较方案 → 解释结果 → 形成行动 → 持续跟进`。

---

## 1. 完整数据流（V2.2 新增 advisor_path）

```
用户消息
   ↓
converse → 建档抽取（不变）
   ↓
handle → route_intent（V2.1 已有，含 LLM 兜底注入 context）
   ↓
【V2.2 新增】advisor_path（意图路由后，非闲聊意图走这里）
   ↓
① 构建 messages = [system(Advisor Policy + Wealth Context + 回复骨架), user(问题)]
   ↓
② tool_loop（真实 function calling）：
     LLM.chat(messages, tools=9 个只读工具 schema)
     ├─ 有 tool_calls → 执行工具(调 A2 → Engine/Decision) → 结果(带 source)回传 → 循环
     └─ 无 tool_calls → 输出结构化 JSON（summary/finding/recommendations/next_actions）
   ↓
③ 数字防编造：系统从「已执行工具结果」确定性取 metrics(带 source)
     LLM 文字里禁止出现财富数字（只定性），数字由系统填
   ↓
④ build_response → AgentResponse（复用冻结 Schema，不改 A1）
   ↓
前端渲染：结论(LLM) + 数字(系统 metrics 带 source) + 建议(LLM)
```

---

## 2. 10 个设计要点逐一回应

| # | 用户要求 | 本计划方案 |
|---|---------|-----------|
| 1 | 真实 tool calling 链路 | provider 新增 `chat(messages, tools)`，用 DeepSeek 原生 `tools`/`tool_calls`（非 prompt 塞工具说明）；extraction.py 已有单轮参考，扩展为多轮 loop |
| 2 | 9 工具各自解决什么 | 见 §3 工具表（每工具「解决什么顾问任务 + 何时调用」） |
| 3 | 多工具串联 | tool_loop 天然支持：LLM 一轮可发多个 tool_calls，工具结果回传后继续调下一个（买房=overview→issues→scenario） |
| 4 | 工具结果回模型第二轮 | tool_loop 把 `{role:"tool", tool_call_id, content}` 回传，LLM 读结果做第二轮推理 |
| 5 | 防编造数字 | 两段式：LLM 输出**结构化 JSON**（文字只定性、禁数字），数字由系统从工具结果取 metrics（带 source）。system 明确「禁止输出任何财富数字」 |
| 6 | 数字必须来自 Engine/Decision | 工具 executor 只调 A2→Engine/Decision；metrics 复用 `response.build_metrics` 确定性取数，绝不从 LLM 文本解析数字 |
| 7 | 何时反问不胡猜 | LLM 输出 `missing: [字段中文名]` → 系统转 need_clarification；复用 `params.PARAM_LABELS` 单一事实源 |
| 8 | 区分真实/典型/沙盘 | 工具结果带 `data_origin`（real/scenario）；典型画像不进 advisor_path（只服务冷启动向导） |
| 9 | 人话转化不甩 issue_id | LLM 读工具结果的 title/finding（已是人话）做总结，system 禁止输出 `issue_id`/`RFR`/`source` 等内部标识给用户 |
| 10 | 失败/异常/数据不足降级 | LLM 失败→回退 V2.1 确定性七意图；工具异常→复用 `errors.map_tool_error`；数据不足→need_clarification |

**第 11 点（用户补充 · 最高优先级）：意图消歧优先于机械路由/机械 refuse。**

测算类关键词（复利/年化/收益/利息/测算…）不再直接拒绝，而是先判断「用户到底要什么」：

- 「什么是复利？」→ 知识问题，直接答（不调 Tool、不算数字）
- 「帮我算 100 万按 5% 复利 10 年」→ 纯金融计算，无家庭上下文 → 拒绝自算
- 「复利对我家庭未来资产有什么影响？」→ scenario，走 `run_scenario`

V2.2 把现有 `refusal_gate` 的「纯计算词直接 refuse」升级为「先追问意图」：

> “你是想知道复利本身怎么计算，还是想看看复利对你家庭未来资产有什么影响？”

意图不明 → 先自然追问，明确目的后再决定调不调 Tool。这是「顾问」和「查询接口」的分水岭。

---

## 3. 9 个只读工具（V2.2 范围；create_action 留 V2.6）

| Tool | 底层能力 | 解决什么顾问任务 | 何时调用 |
|------|---------|----------------|---------|
| `get_family_profile` | `db.dump_family` | 成员/资产/负债/保险全貌 | 需要了解"这个家庭是谁" |
| `get_wealth_overview` | `build_overview` | 财富全景（评分/净资产/现金流/DTI/应急） | 需要现状基线 |
| `get_wealth_issues` | `build_issues` | P0→P2 问题 + 建议 | 需要风险判断 |
| `get_cashflow` | `overview.cashflow` | 收支/结余/储蓄率 | 问现金流 |
| `get_allocation` | `overview.asset_allocation` | 配置/房产占比/适配度 | 问配置 |
| `get_retirement` | `overview.retirement` | RFR/NWC/养老象限 | 问养老 |
| `get_goals` | `build_goals` | 目标/缺口/每月需存 | 问目标 |
| `run_scenario` | `compare_scenarios` 单方案 | 单方案"如果…会怎样" | 单一假设 |
| `compare_scenarios` | `compare_scenarios` 多方案 | 多方案对比权衡 | "先还贷 vs 投资" |

> 9 个全是「已有能力 + 暴露成 tool schema」，`create_action`（写库，受 P3）留 V2.6。
> 工具返回 JSON 带 `data_origin: "real"`（真实）或 `"scenario"`（模拟）。

---

## 4. 10 个端到端调用轨迹

> 格式：`问题 → 意图 → 工具链 → 第二轮推理 → 最终回答`（每步标注 data_origin）

**T1「我现在适合买房吗？」** → SCENARIO_COMPARE
1. `get_wealth_overview`(real) → 现状 DTI=62%、应急 2 月
2. `get_wealth_issues`(real) → 负债偏高 P0、应急不足 P1
3. 缺房价参数 → LLM 输出 `missing:["房价"]` → need_clarification 反问
4. （补「500 万」后）`run_scenario(buy_house)`(scenario) → RFR 0.9↓0.4、DTI 62%↑85%
5. 第二轮推理：DTI 超阈值 + 应急不足 → 风险高
6. 回答：结论「现在买房压力偏大」+ 数字（DTI 85%、RFR 0.4，source）+ 建议「先补应急/降首付」

**T2「为什么你说我的养老有问题？」** → EXPLAIN_RESULT
1. `get_wealth_issues`(real) → 养老 issue（finding 已是人话）
2. `get_retirement`(real) → RFR=0.43
3. 推理：房产占比 68%、可投资资产少 → 退休金缺口
4. 回答：「主要问题是房产占比高、可投资资产少，导致退休现金流不足」（不甩 RFR）

**T3「拿 200 万买房会怎样？」** → SCENARIO_COMPARE（参数齐）
1. `run_scenario(buy_house, price=200万)`(scenario) → 各指标 delta
2. 推理：读 delta → 判断影响
3. 回答：模拟结果 + 权衡（数字带 scenario source）

**T4「先还房贷还是投资？」** → SCENARIO_COMPARE（双方案）
1. `get_wealth_issues`(real) → 拿负债利率
2. `compare_scenarios(prepay, invest)`(scenario) → 两方案对比
3. 推理：读 comparison delta → 权衡
4. 回答：A vs B 对比 + 建议（「更值得比较」）

**T5「帮我看最大的风险」** → CHECK_ISSUES
1. `get_wealth_issues`(real) → P0 issue
2. 推理：取 P0 → 解释
3. 回答：最大风险 + 为什么 + 建议

**T6「收入下降 30% 还能撑多久？」** → SCENARIO_COMPARE
1. `run_scenario(income_change, -30%)`(scenario) → 应急月数变化
2. 回答：能撑 X 个月 + 建议

**T7「我的配置合理吗？」** → CHECK_ALLOCATION
1. `get_allocation`(real) → 房产占比/适配度
2. 回答：配置评价 + 建议

**T8「每月该存多少？」** → CHECK_GOALS
1. `get_goals`(real) → 缺口/monthly_needed
2. 回答：每月需存 X + 建议

**T9「什么是复利？」** → 闲聊（非财富）
1. 无工具调用
2. 直接知识回答（不碰财富数字，不调 Engine）

**T10「孩子 5 年后上大学，教育金够吗？」** → CHECK_GOALS
1. `get_goals`(real) → 教育目标缺口
2. 回答：够/不够 + 缺口 + 建议

---

## 5. 分阶段 TDD 计划（一阶段一 commit）

### Task 0：provider 扩展 tool calling

**Files:** Modify `app/agent/provider.py`（协议加 `chat`）、`app/agent/providers/deepseek.py`（实现 `chat`）

**Interfaces:**
- Produces: `chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict | None`
  返回 `{"content": str|None, "tool_calls": [{"id","name","arguments"}]}` 或 None（失败降级）

- [ ] Step 1 写失败测试：`chat` 发送 tools 参数；有 tool_calls 时解析；无 tools 时返回 content；超时返回 None
- [ ] Step 2 跑红
- [ ] Step 3 实现（extraction.py 的 tool_calls 解析作参考，扩展为通用 chat）
- [ ] Step 4 跑绿 + 全量回归
- [ ] Step 5 commit

### Task 1：9 工具 schema 注册表

**Files:** Create `app/agent/tool_schemas.py`（工具 schema + executor 注册表）

**Interfaces:**
- Produces: `TOOL_SCHEMAS: list[dict]`（9 个 OpenAI 函数描述）、`execute_tool(name, args, user) -> dict`（带 `data_origin`）

- [ ] Step 1 写失败测试：9 个 schema 完整；execute_tool 返回带 data_origin + source 的结果；execute_tool 调 A2 工具（monkeypatch 验证）
- [ ] Step 2 跑红
- [ ] Step 3 实现（映射现有 get_overview/get_issues/get_goals/compare_scenario + 读子字段）
- [ ] Step 4 跑绿 + 全量回归
- [ ] Step 5 commit

### Task 2：tool_loop Agent 循环

**Files:** Create `app/agent/advisor.py`（`run_advisor` 多轮循环）

**Interfaces:**
- Produces: `run_advisor(user, message, llm, wealth_context) -> dict`（返回 LLM 最终结构化 JSON 或降级标记）

- [ ] Step 1 写失败测试：单工具（T5）、多工具串联（T1 三连）、无工具（T9 闲聊）、超轮数降级
- [ ] Step 2 跑红
- [ ] Step 3 实现（`MAX_ROUNDS=6` 防死循环；工具结果回传 `role:tool`）
- [ ] Step 4 跑绿
- [ ] Step 5 commit

### Task 3：回答组装 + 数字防编造

**Files:** Modify `app/agent/response.py`（新增从工具结果取 metrics）

**Interfaces:**
- Produces: `assemble_advisor_response(tool_results, llm_json, intent) -> AgentResponse`（metrics 从 tool_results 取，带 source）

- [ ] Step 1 写失败测试：LLM 文字含数字则被拒/丢弃；metrics 只来自 tool_results；每个 value 带 source
- [ ] Step 2 跑红
- [ ] Step 3 实现（复用 build_metrics；LLM JSON 的 summary/finding 只取文字，数字由 metrics 覆盖）
- [ ] Step 4 跑绿
- [ ] Step 5 commit

### Task 4：意图消歧 + 反问 + 降级

**Files:** Modify `app/agent/advisor.py`（missing→need_clarification；异常→降级）、`app/agent/router.py`（`refusal_gate` 纯计算词 refuse → 先追问意图）

- [ ] Step 1 写失败测试：缺参数→need_clarification+missing；工具异常→map_tool_error；LLM 返回 None→确定性兜底；复利类模糊意图→先追问（不直接 refuse）
- [ ] Step 2 跑红
- [ ] Step 3 实现（含 `refusal_gate` 升级：纯计算词不再直接 refuse，转「意图消歧」追问；明确是知识问答则直接答，明确是家庭影响则走 scenario，明确是纯金融计算才 refuse）
- [ ] Step 4 跑绿
- [ ] Step 5 commit

### Task 5：handle 集成 + 顾问感场景端到端

**Files:** Modify `app/agent/runtime.py`（意图路由后走 advisor_path）、Create `tests/test_v22_advisor.py`

- [ ] Step 1 写失败测试：§6-A 的 20 个顾问感场景中 V2.2 可覆盖的 17 个（意图+工具链+数字+source+无编造+next_actions），跨轮 3 个（#7/8/9）留 V2.4 不测
- [ ] Step 2 跑红
- [ ] Step 3 实现集成（财富/决策意图走 run_advisor；知识问答与场景判断由意图消歧分流）
- [ ] Step 4 跑绿 + 全量回归 + node
- [ ] Step 5 commit

---

## 6. 验收标准（顾问感第一，工程正确第二）

> **「pytest 276 passed / Node 12 passed / Tool 调用成功」只能证明工程正确，不能证明像顾问。**
> V2.2 的第一验收标准是：**用户和它聊起来，像不像一个真正懂家庭财富的顾问。**

### A. 顾问感测试集（第一验收标准）

≥20 个真实用户问题，每个检查 6 件事：

| 能力 | 要求 |
|------|------|
| 理解 | 理解用户真正想解决什么，而不是字面匹配关键词 |
| 追问 | 信息不足/意图模糊时知道问什么（不知道就问，不瞎答） |
| 数据 | 需要数字时主动调 Tool 取真实数据，不靠常识脑补 |
| 推理 | 能把多个 Tool 结果组合成判断（不单点查询） |
| 表达 | 不像数据库查询结果，不甩 JSON/issue_id/RFR/source |
| 行动 | 最后给用户下一步选择（next_actions 可点，不空谈） |

**20 个测试问题**（跨轮记忆类标注 V2.4）：

| # | 问题 | 主考能力 | 版本 |
|---|------|---------|------|
| 1 | 我现在该不该买 500 万的房 | 推理+行动 | V2.2 |
| 2 | 我最近压力很大，感觉钱不够用 | 理解+追问 | V2.2 |
| 3 | 我退休够不够 | 数据+推理 | V2.2 |
| 4 | 我有 300 万现金该怎么配置 | 推理+行动 | V2.2 |
| 5 | 为什么我的家庭评分这么低 | 数据+表达 | V2.2 |
| 6 | 我想改善一下 | 追问（目标模糊） | V2.2 |
| 7 | 连续追问上一轮结果 | 跨轮记忆 | V2.4 |
| 8 | 否定 AI 的判断 | 跨轮记忆 | V2.4 |
| 9 | 提供新信息后要求重新判断 | 跨轮记忆 | V2.4 |
| 10 | 与财富无关的普通问题 | 理解（边界） | V2.2 |
| 11 | 什么是复利 | 意图消歧→追问 | V2.2 |
| 12 | 帮我算 100 万复利 10 年 | 拒绝自算 | V2.2 |
| 13 | 复利对我家庭资产有什么影响 | 意图消歧→scenario | V2.2 |
| 14 | 收入下降 30% 还能撑多久 | 数据+推理 | V2.2 |
| 15 | 先还房贷还是投资 | 多方案对比 | V2.2 |
| 16 | 孩子 5 年后上大学教育金够吗 | 数据+行动 | V2.2 |
| 17 | 我的配置合理吗 | 数据+表达 | V2.2 |
| 18 | 每月该存多少 | 数据+行动 | V2.2 |
| 19 | 为什么你说我养老有问题 | 表达（不甩 RFR） | V2.2 |
| 20 | 拿 200 万买房会怎样 | 单方案模拟 | V2.2 |

**顾问感验收的真问题**（不返回什么 JSON，而是）：

> `理解用户 → 判断是否需要数据 → 必要时调 Tool → 读真实结果 → 形成判断 → 解释为什么 → 给下一步行动`

最终用户看到的，始终是一段自然的顾问对话。

### B. 工程正确（必要但不充分）

1. **多步决策链路**：每个 V2.2 场景断言 `意图正确 + 工具链正确 + 数字==Engine + source 正确 + 无编造`。
2. **数字防编造**：LLM 输出文字含财富数字 → 丢弃；metrics 数字全部来自工具结果（带 source）。
3. **顾问式回答**：summary/finding 是定性人话，不出现 `issue_id`/`RFR`/`source` 等内部标识。
4. **反问不胡猜**：信息不足 → need_clarification + missing（复用 PARAM_LABELS）。
5. **数据来源可辨**：工具结果带 `data_origin`（real/scenario）。
6. **降级安全**：LLM 失败/超时 → 确定性兜底（不 500，不编数字）。
7. **冻结契约零触碰**：Engine/Decision/Schema A1/A2 逻辑不改（仅新增 tool schema 暴露层）。
8. **全量回归**：pytest 全绿 + node 12。

---

## 7. 明确不在 V2.2 范围（防越界）

- ❌ `create_action`（写库，受 P3，留 V2.6）
- ❌ 对话记忆/多轮记忆（V2.4）
- ❌ 主动提醒（V2.5，需调度器）
- ❌ 修改 AgentResponse/MetricRef Schema（冻结 A1，只复用）
- ❌ 修改 Engine/Decision 计算逻辑

---

## 8. 决策点（已全部确认接受，其中第 3 点升级）

> 状态：4 点均已确认接受。第 3 点由用户升级为「意图消歧」，最终形态如下。

1. **两段式数字防编造** ✅：LLM 只填定性文字（禁止输出数字），数字由系统从工具结果填 metrics（带 source）。
2. **9 个只读工具 + create_action 留 V2.6** ✅。
3. **意图消歧（升级版）** ✅：意图/参数模糊时，先自然追问、明确目的，再决定调不调 Tool；不机械 refuse、不机械 tool_loop。见 §0 最高原则第 2 条 + §2 第 11 点。
4. **降级策略** ✅：LLM 失败回退 V2.1 确定性七意图（现有 `_OK_SUMMARY` 模板）；fail-open 不中断对话（不编数字、说清缺什么、能给原则建议就给）。
