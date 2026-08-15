# AdvisorContext 契约设计（Phase 1b · Step 2 + Step 3 + Step 4）

> **状态：Step 2 + Step 3 + Step 4 已实现（2026-08-16）。** 契约 schema、converse 入口消费、前端各页写结构化 context、
> chat.js 带 context、G3 存原 query、**真实 advisor_path 消费 Context**（advise/run_advisor 穿参，
> `_advisor_context_block` 以【当前情境】块注入顾问提示，范围+意图+聚焦对象，零数字）、
> **G3 闭环「取消建档后继续回答」**（`filing_declined` 代码层语义 + `cancel_and_reanswer`）均落地；
> T1–T8b 契约测试已冻结为 [test_advisor_context.py](../tests/test_advisor_context.py) 并转绿，
> 确定性 12 题基线 17 锚零 diff（Step 4 后**仅 Q10 有意重冻结**）。真实 12 题基准（2026-08-16 重跑）：
> Q12（goals context）从 need_clarification 转 status=ok 围绕「孩子教育金」回答（#8 关闭）；
> Q10（取消建档继续回答）弹卡→取消→re-answer 转 CHECK_ALLOCATION status=ok，回答原配置问题，
> 不再返回「好的，已忽略」（G3 关闭）。
> 依据：12 题基准 [report_benchmark12.md](../advisor_eval/report_benchmark12.md)（G1/G3/#8 实证）+ 现状核对 [verification-v10-current-state.md](verification-v10-current-state.md)（论断 #8）+ 架构主纲 [plan-ai-advisor-core-architecture.md](plan-ai-advisor-core-architecture.md) §5。
> 本设计回答：**Context 到底是什么、从哪来、被谁消费、优先级如何、如何用契约解掉 G1/G3/#8。**

---

## 0. 定位与铁律

### Context 是什么
> **AdvisorContext 是「用户为什么来问」的结构化输入，是进入 Advisor 决策链的第一等对象。**

它回答三个问题，且**只**回答这三个：
- 用户在**看什么**（source）
- 用户**已知什么**（payload 里的标识与用户新声明事实 + family_state 里的 Engine 已确认数据）
- 用户**想解决什么**（query / intent_hint / first_turn_action）

### Context 不是什么（铁律，冻结）
1. **不是额外提示词**：页面不得塞散文指令。所有字段结构化，且每个字段的语义在下方 schema 里钉死。
2. **不是新的计算来源**：payload **禁止携带页面展示的聚合数字**（gap / score / dti / rfr / coverage / monthly_need / 收益估算…）。所有金额、评分、缺口、比率**只能**来自 Engine/Decision 的确定性结果。
3. **不是建档替代品**：payload 里的用户新声明事实（如 `retire_age`）只是"用户此刻的假设"，落入答案前必须与 family_state 对照、标为 assumption，不直接写库。

> 推论（最重要）：**页面传的 payload 越少越好。** 页面能拿到的数字，Engine 也能拿到且更权威。payload 只放「标识」和「用户新声明的事实」两类——前者指向 Engine 已有数据，后者是用户刚说出口的信息。

---

## 1. 完整 schema（双层）

契约分两层：**页面提交层**（前端 → 后端，只带用户侧信息）与**解析层**（后端在 `converse()` 入口构建，带系统确定性事实）。解析层是六阶段循环里传递的对象。

```python
# app/schemas/context.py（新增；agent.py 只保留 AgentResponse 等输出契约）

class AdvisorContextRequest(BaseModel):
    """前端 → 后端：页面告诉顾问「用户在看什么、想解决什么」。
    对应 AgentRequest.context 字段（现为空转，见 verification 论断 #8）。"""
    source: Literal["goals", "retirement", "allocation", "sandbox", "overview", "chat"]
    intent_hint: str | None = None      # 页面建议的第一轮意图（SEED，非 OVERRIDE，见 §4）
    query: str | None = None            # 用户真正想解决的问题（缺省 = 本次 message）
    payload: dict[str, Any] = {}        # 标识 + 用户新声明事实（铁律：绝不含聚合数字）
    first_turn_action: str | None = None  # 顾问第一轮应该做什么


class AdvisorContext(BaseModel):
    """解析层：converse() 入口一次性构建，随六阶段循环传递、逐阶段积累。
    数字字段只由系统确定性写入——payload 永不进入 evidence/metrics。"""
    request: AdvisorContextRequest
    # —— 系统在 Context 阶段写入（唯一真相源）——
    family_state: dict[str, Any] | None = None   # Engine 已确认的家庭数据（build_overview 等）
    # —— 系统在后续阶段写入（缺数检测 / Evidence 阶段）——
    missing: list[str] = []            # 缺数检测产出：影响答案的最小缺失项（P1.3 底座）
    evidence: list[dict] = []          # Evidence 阶段确定性产出（MetricRef 列表）
```

**生命周期（谁在什么时候写哪个字段）：**

| 字段 | 谁写 | 何时 |
|------|------|------|
| `request.*` | 前端（各来源页「问顾问」） | 请求发出时 |
| `family_state` | Context 阶段（Engine 读档案） | `converse()` 入口，先于 intent |
| `missing` | 缺数检测（P1.3 底座） | Intent 确定后、回答前 |
| `evidence` | Evidence 阶段（Engine 计算） | 回答组装前 |
| `query` | request 提供；缺省回退 message | `converse()` 入口归一 |

> **归一规则**：`ctx.query = request.query or message`。G3 的"原问题不丢"正是靠这个字段——它独立于"建档流程"，跨取消存活。

---

## 2. 各来源 payload（最小化原则）

规则：**payload 只放「标识」+「用户新声明的事实」；绝不放「页面展示的聚合数字」。**

| source | payload（允许） | 明确禁止（为什么） |
|--------|-----------------|--------------------|
| **goals** | `{"goal_id": 1}`（或 `{"goal_type": "教育"}`） | ❌ `target_amount/current_saved/gap/monthly_need` —— Advisor 从 Engine 读，页面传了就成第二计算源 |
| **retirement** | `{"retire_age": 60}`（用户刚调的滑杆，属新声明） | ❌ `need_pv/investable/gap/rfr/nwc` —— Engine 算 |
| **allocation** | `{"target_alloc": {...}}`（用户想试的配比，新声明） | ❌ `hhi/risk_metrics/allocation_fitness` —— Engine 算 |
| **sandbox** | `{"scenario_id": 3}`（或 `{"scenario_name": ...}`） | ❌ `params/baseline/option/delta` —— Engine 算 |
| **overview** | `{}`（空） | ❌ `score/net_worth/top_issue/recent_changes` —— 页面展示即来自 Engine，重复无用 |
| **chat** | `{}`（空） | —（普通对话无页面上下文） |

**判定口诀**：*payload 里的值，如果"删掉它 Advisor 也能从家庭数据里拿到"，就不该传。* 传了只会制造漂移（页面算的 51 分 vs Engine 算的 51 分）。

---

## 3. converse() 消费点与优先级

### 现状（错误链）
```
message → looks_like_filing gate →（吞问题）→ LLM/fallback/页面各拼
```
context 只在 `handle()` 的 EXPLAIN_RESULT 分支被读一次（runtime.py:90-93），intent 路由与首轮回答完全看不到它。

### 目标链（契约进入决策链）
```
message + context
  ↓ ① build_advisor_context(message, user, context)
  ↓      request 归一（query = request.query or message）
  ↓      family_state = Engine 读档案（先于 intent，Context 阶段）
  ↓ ② Intent 路由：intent_hint 参与（SEED），低置信度→澄清
  ↓ ③ 建档判定降级：ctx.source 表明提问面 → 不触发 filing gate（G1）
  ↓ ④ 回答路径：payload 标识聚焦 + missing 只追影响答案的缺失项
  ↓ ⑤ Evidence：Engine 计算（数字唯一来源，payload 永不进来）
  ↓ ⑥ Response：evidence 供展示层引用（数字以 MetricRef 呈现）
  ↓ ⑦ G3：若需建档卡 → 确认卡携带 original_query + 解析后 ctx
```

### 优先级（高 → 低，用户 2026-08-15 确认）
**用户当前 query → 页面 intent_hint → payload 标识 → message → family_state。**

| 优先级 | 输入 | 作用 | 边界 |
|--------|------|------|------|
| 1 | `query`（用户当前真正想问的） | 要被回答的问题本体 | `request.query` 缺省回退 `message`；**压倒一切页面建议** |
| 2 | `intent_hint`（页面建议意图） | 缩小路由搜索空间 | 仅当 query 未强确定性路由到矛盾意图时生效（SEED，不 OVERRIDE） |
| 3 | `request.payload` 标识 | 聚焦具体目标/情景/资产 | 只影响"读哪份数据"，不影响"怎么算" |
| 4 | `message` | 用户字面原话 | 永远保留；是 query 的最终来源（G3 恢复物） |
| 5 | `family_state`（系统写） | 已有数据复用（#4） | 唯一事实源，页面 payload 永远不覆盖它 |

> 核心语义：**页面知道"用户从哪里点进来的"，但不知道"用户现在真正想问什么"。** 用户当前的问题必须压倒页面 hint——否则从 Goals 页点进来后用户随口问"我退休够不够"，会被 `intent_hint=CHECK_GOALS` 误导到目标页。

**建档判定在契约下的新规则**：`ctx.source ∈ {goals, retirement, allocation, sandbox, overview}` ⇒ 这次对话**按提问处理**，`looks_like_filing` 不参与意图判定（它的误判正是 Q2 弹卡的根因，见基准报告）。`source=chat` 时保留现状判定，但只作为"非情景词 + 非问句 + 有金额"时的兜底，不再抢先覆盖回答。

---

## 4. G1 / G3 / #8 如何被契约解决

### G1（建档 gate 吞问题）→ 契约给"这是提问"信号
- 根因（基准实证）：`looks_like_filing` 在 LLM 之前拦截，「投入股票」措辞命中建档（profile.py:61 `_SCENARIO_RE` 有"投资"无"投入"）；真实 LLM 想答却被 canned 澄清覆盖。
- 解法：契约的 `source` 让**"这次是提问"成为构造事实，而非启发式猜测**。跨页面入口天然是提问面；chat 内的提问由**先答后问**（Phase 1c 两条路径）兜底。
- 验收：Q2 带 goals/retirement 等 source 提问 → 直接回答，绝不弹卡。

### G3（取消建档丢原问题）→ 契约让 query 跨取消存活
- 根因（基准实证）：`create_confirm` 只存 `{family_id, actions}`（profile.py:83），取消 = `discarded` 终态，原 message 无从找回。
- 解法：`create_confirm` 存储扩展为 `{family_id, actions, original_query, advisor_context}`；取消分支把 `original_query` + 解析后 ctx **重新投入回答路径**（不是建档路径）。`ctx.query` 正是这个"不丢的问题"。
- 验收：Q10 弹卡 → 取消 → Advisor 继续回答"30万怎么分"（缺必要数据时才进澄清循环）。

### #8（context 未消费）→ 契约让 context 进决策链
- 根因（基准实证）：Q12 传 context 但回答与 Q5 相同；前端从不发 context（chat.js:167 只有 `{message}`）。
- 解法：§3 的消费链。前端各页从"写 `store.chat.draft` 纯文本"改为"写 `store.chat.advisorContext` 结构化"；chat.js 请求体发 `{message, context}`；后端 `build_advisor_context` 在入口消费。
- 验收：Q12 带 goals context → intent == intent_hint（或经消息校验后的细化），回答针对 `payload.goal_id` 指向的目标，与 Q5（无 context）可观测不同。

---

## 5. 契约测试（冻结不变量，先写测试再实现）

以下不变量**先冻结为测试**（复用 [test_advisor_benchmark.py](../tests/test_advisor_benchmark.py) 的零 API 成本模式），实现后任何一条变红即回归：

| # | 不变量 | 测试形态 |
|---|--------|----------|
| T1 | **context 不得丢** | Q12 带 goals context → `intent == intent_hint`，回答聚焦 payload 指向的目标；断言与 Q5 无 context 时的回答路径不同 |
| T2 | **原 query 不得丢** | G3 链：弹卡 → 取消 → 断言回答重新进入「30万怎么分」的回答路径（`missing` 只含真正缺的必要项，不含"原问题"本身） |
| T3 | **已有数字不得重复追问** | family 已有收入 → 断言回答的 `missing` **不含**"月收入/月支出"；Q11 轮2 场景 |
| T4 | **context 不算数** 🔴 **Phase 1 硬红线** | payload 塞 `gap=999999` → 断言 metrics/evidence 里出现的是 **Engine 的 gap**（900000），`999999` 永不进入任何数字字段。即使 payload 恶意塞数，Advisor 的最终数字也必须来自 Engine，不是 Context |
| T5 | **确定性基线不倒退** | 现有 17 个回归锚 + 契约改造后重跑 12 题，无 context 的题签名不变（有意变更才重新冻结） |
| T6 | **payload 白名单** | 每个 source 的 payload 用 pydantic 校验：出现禁止字段（如 goals 页传 `gap`）→ 拒绝或剥离并记日志，绝不静默接受 |

---

## 6. 展示层裁定（Phase 1b 立方向 → 2026-08-16 独立小任务已实现）

基准发现 Q11 真实模式 summary 含"配置适配度 **51 分**"→ 触发铁律·数字无编造。**实际根因（2026-08-16 代码取证）**：
`detect.py:174` allocation finding 带数字 → `_build_priorities`（response.py:449）逐字透传进
`PriorityRef.finding` → `_fallback_summary`（response.py:465）把 finding 内联进 summary prose
（真实 LLM summary 含数字被防编造闸剥空后必走此兜底）。数字真值早已在
`metric.allocation_fitness`（`_issue_metrics` 已 surface 成 MetricRef，数字载体成立），
缺的只是 prose 侧泄漏。

**裁定方向（用户已确认，不在此放宽铁律）**：
- Engine finding **内部可以**保留数值（issue 记录是内部数据）。
- 但进入**用户文案的结构化 severity/summary 层**时，数字不得内联——改以 `MetricRef`（evidence 卡片）呈现，severity/finding 文案去数字（"资产配置适配度偏低"，数字活在 metrics+evidence）。
- 这是一处独立的展示层小改（detect/layers/response），**归属 Phase 1c 或之后**，Phase 1b 只记录方向，不实现。

**已实现（2026-08-16，独立 commit，两层级防线）**：
1. **修源头**：`detect_allocation` finding/reason 去数字 → 定性「当前资产结构偏离目标配置」，真值留在 `metric.allocation_fitness`。
2. **修兜底**：`_fallback_summary` 加数字守卫（finding 含数字不注入），任何 detector 的 finding 都进不了 summary prose。

只动 ALLOCATION_LOW_FITNESS 一条；其余 7 个 detect 的系统性数字模式记录为后续任务（Q4/Q5/Q12
CHECK_GOALS 泄漏已是冻结基线已知失败 iron_ok=False，不扩大）。验证：新增 T-D1/D2/D3 全绿、
12 题确定性基线签名零 diff、全量 572 pytest 绿、真实 12 题「51 分」prose 0 次（只在
evidence/metrics，如 `allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness`）、
铁律·数字无编造 12/12 ✅。

---

## 7. 实现边界（本设计不触碰的冻结项）

| 冻结项 | 位置 | 理由 |
|--------|------|------|
| Engine（财富计算） | app/engine、app/services | 数字唯一真相源，契约只读不写 |
| Decision（问题检测） | app/decision | 判断唯一真相源 |
| Agent 输出 Schema A1 | app/schemas/agent.py | 防编造硬闸，只扩不减 |
| A2 工具只读 + VIP 门 | app/agent/tools.py | 工具 = 获取事实，绝不计算 |

实现只允许发生在：**app/schemas/context.py（新增契约）、app/agent/entry.py（入口消费）、app/agent/runtime.py（handle 消费）、static/（各页写结构化 context）、chat.js（请求体带 context）、app/agent/profile.py（create_confirm 存原 query）**。

---

## 8. 实现顺序（用户锁定，2026-08-15）

**严格按 T1 → T6 先红后绿（TDD）**，完成后再单独处理 Q11「51 分」展示裁定——**两个问题不混做**：

1. 写 `tests/test_advisor_context.py`，覆盖 T1–T6 全部不变量 → 先红。
2. 按「契约 schema → converse 入口消费 → 各页写结构化 context → chat.js 带 context → G3 存原 query」实现 → 逐条转绿。
3. 转绿后跑全量回归（现有 17 个基准锚 + 516 pytest）不倒退。
4. **之后**才进「51 分」展示裁定（detect/layers/response 文案去数字），单独 commit。
