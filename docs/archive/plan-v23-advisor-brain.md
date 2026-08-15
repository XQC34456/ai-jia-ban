# V2.3 Advisor Brain（顾问思考层）· 实施计划

> **状态**：仅计划，未实现。等你确认后才开工。
> **前置**：V2.1 Context Engine ✅（`fb70cfa`）、V2.2 Tool Calling ✅（`491f6e2`→`6be38c2`，321 passed）。
> **一句话**：V2.2 让 AI 有了「手」（会调用工具），V2.3 给它「脑」（会像顾问一样思考）。不新增工具，不写状态机 if/else。

---

## 0. 一句话目标与核心反转

**目标**：让 AI 从「会调用工具的回答器」升级成「会诊断、会排优先级、会给证据、会权衡、会承认不确定、会主动带用户下一步」的家庭财富顾问。

**核心反转**（与 V2.2 同理）：
- V2.2 反转 = 「不是页面调用 AI，而是 AI 调用工具」。
- **V2.3 反转 = 「不是让 LLM 自由选工具，而是让 LLM 带着思考 SOP 选工具、并用结构化证据链回答」。**

**回答「为什么做完后用户会明显感觉是顾问而不是 ChatGPT」**（本节先给结论，§11 展开）：
1. 它不再「问什么答什么」，而是先**诊断**你的家庭，再**点出当前主要矛盾**——「你现在最该解决的不是投资收益率，而是现金流和长期储备之间的矛盾」。
2. 它每个判断都能**给出证据**——「我为什么这么说？因为你的应急金只有 X 个月 / 储蓄率只有 Y%」，且每个数字都带出处（`source`），点开可追溯。
3. 它**不给你标准答案**，而是摆出 A/B/C 的「得到什么 / 失去什么」，让你看清取舍。
4. 它**敢说不知道**——信息不够就明确说「我还差两个数才能判断」，而不是硬猜。
5. 它**主动带下一步**——「我先帮你看现金流，确认问题在哪，再往下找」。
6. 你**挑战它、情绪化、要它二选一**时，它不会崩溃或说教，而是重新审视 / 共情 / 解释为什么不能简单二选一。

---

## 1. 当前架构审计（V2.2 真实实现，逐段对应代码）

> 依据 [advisor-architecture-audit.md](advisor-architecture-audit.md)（Level 0 结论）+ V2.2 落地代码。

### 1.1 V2.2 已经做到的（地基，V2.3 不推翻）

| 能力 | 落地位置 | 状态 |
|------|----------|------|
| 9 个只读工具 + tool_loop 多轮 | `app/agent/advisor.py` `run_advisor` | ✅ 会调用而非背诵 |
| 数字防编造（LLM 文字含数字即删，数字从 tool_results 带 source 注入） | `app/agent/response.py` `_strip_numeric_*` | ✅ 硬闸 |
| 意图消歧（复利不直接 refuse，交 LLM） | `app/agent/router.py` `refusal_gate` | ✅ |
| 降级链（LLM 失败 → 确定性兜底） | `app/agent/runtime.py` `handle` | ✅ |
| advisor_path 集成（有 LLM 走 advise，失败回退 dispatch） | `app/agent/runtime.py:56-64` | ✅ |

### 1.2 V2.2 还做不到的（V2.3 要补的 8 个缺口）

| # | 缺口 | 证据 | 后果 |
|---|------|------|------|
| G1 | **LLM 自由选工具，无「思考 SOP」** | `advisor.py` `_ADVISOR_SYSTEM` 只约束「必须调工具 / 不编数字」，没有「先诊断→排优先级→再给结论」的顺序 | 它可能跳过 DIAGNOSE 直接甩结论，或调了工具却不围绕主要矛盾组织 |
| G2 | **主要矛盾没被「组织语言」环节利用** | `build_issues` 已按 P0→P2 排好 `priorities`（`decision/issue.py:33-34`），但 `get_wealth_issues` 的 schema 描述没要求 LLM「优先围绕 priorities[0] 说」 | 同时有养老+现金流+配置问题时，LLM 可能平铺，说不出「最该先解决哪个」 |
| G3 | **数字是「禁止」不是「引用」** | `response.py:311-325` `_strip_numeric_text` 一刀切删掉含数字的句子 | 「我退休还差多少钱」这类问题，AI 不能自然说数字，回答很别扭 |
| G4 | **无 trade-off 结构** | `AgentResponse` 只有 recommendations/next_actions 平列表 | LLM 可能输出「最佳方案」，违背「不制造最佳方案」原则 |
| G5 | **无不确定性表达** | schema 无 confidence/missing/alternative 字段 | LLM 信息不足时可能硬答 |
| G6 | **next_actions 是 LLM 自由发挥的 list** | `assemble_advisor_response` 直接透传 LLM 的 next_actions | 不是「主动带用户下一步」，只是罗列建议 |
| G7 | **反例行为无约束** | `_ADVISOR_SYSTEM` 未定义「被质疑/情绪化/要绝对答案」时怎么办 | 用户挑战它，它可能甩锅或说教 |
| G8 | **EXPLAIN_RESULT 单轮内无上下文** | `runtime.py` `EXPLAIN_RESULT` 依赖 `context` 参数（恒 None，跨轮留 V2.4） | 「为什么」在单轮内无法复用本轮工具结果解释 |

### 1.3 关键审计结论

**「主要矛盾」的判断逻辑已经存在于 Decision 层**——`build_issues` → `rank()`（`priority.py:21-23`）按 `P0>P1>P2` 排好序，`priorities` 字段就是「最该先解决什么」的确定性答案。**V2.3 绝不能让 LLM 自己判断主要矛盾**（那会违反铁律 P2「判断唯一真相源是 Decision」）。V2.3 要做的只是：把这个确定性答案**喂给 LLM 组织语言**，并**结构化回填**给前端。

---

## 2. V2.3 目标架构

```
用户消息
   ↓
① 意图路由（V2.2 已有：拒算门 → 关键词 → LLM 兜底）
   ↓
② Advisor Brain ── 带「思考 SOP」的 tool_loop（V2.3 核心，改造 advisor.py 提示词 + 输出 schema）
   │   UNDERSTAND  理解用户 + 判断是否需要追问
   │   DIAGNOSE    调 get_wealth_issues / get_wealth_overview 诊断
   │   PRIORITIZE  读 priorities[0] 定主要矛盾（Decision 的确定性答案）
   │   VERIFY      必要时调 run_scenario / compare_scenarios 验证
   │   REASON      组织 证据→判断→权衡（结构化 evidence/tradeoffs/uncertainty）
   │   RECOMMEND   给建议
   │   ACT         给下一步（主动、带 action 语义）
   ↓
③ 组装（response.py：evidence 数字注入 + priorities 提取 + tradeoffs/uncertainty 透传）
   ↓
④ AgentResponse（扩展 schema：priorities / evidence / tradeoffs / uncertainty）
   ↓
前端渲染
```

**Advisor Brain 职责边界**：
- **它决定**：要不要追问、查哪些数据、围绕哪个矛盾组织、是否模拟、给什么建议、下一步是什么。
- **它绝不决定**：财富数字（Engine 算）、问题优先级（Decision 排）、哪些是问题（Decision 检）。
- 二者靠 `MetricRef.source` + `PriorityRef` 的确定性回填焊死。

**为什么是「提示词 SOP」而不是「硬编码状态机」**：如果写 if/else 状态机，会退回 Level 0 的确定性规则引擎（审计结论已否决）。正确做法是——**用六步 SOP 注入 system prompt + 用结构化输出 schema 约束 LLM 每步的产物**，让 LLM 自己走这个循环，但每步都有硬闸兜底。

---

## 3. 七个核心能力 → 具体机制

| # | 用户要的能力 | V2.3 具体机制 | 落点 |
|---|-------------|--------------|------|
| ① | 识别真正问题（不是问什么答什么） | 六步 SOP 的第 1 步 UNDERSTAND 强制「先复述理解 + 判断真实决策问题」；system prompt 加「不要直接回答表层问题」 | `advisor.py` 提示词 |
| ② | 家庭主要矛盾 | **读 Decision 的 `priorities[0]`**，LLM 只组织语言；组装时确定性提取成 `PriorityRef[]` | `advisor.py` + `response.py` |
| ③ | 证据→判断链 | LLM 输出 `evidence: [{claim, metric_key}]`，系统从 tool_results 取 `metric_key` 对应数值 + source 注入；找不到就丢弃（防编造） | `response.py` 新 `_build_evidence` |
| ④ | 权衡（不制造最佳方案） | LLM 输出 `tradeoffs: [{option, gain, loss}]`；system prompt 禁止「最优/最佳」，强制「如果你看重 X 选 A，看重 Y 选 B」 | `advisor.py` + schema |
| ⑤ | 学会不确定 | LLM 输出 `uncertainty: {confidence, missing, alternatives}`；missing 非空 → 追问 | `advisor.py` + schema |
| ⑥ | 主动下一步 | `next_actions` 从「泛泛建议」升级为「带动词 + 指向具体工具」的行动；system prompt 强制「先诊断再给下一步」 | `advisor.py` 提示词 |
| ⑦ | 顾问决策循环 | 六步 SOP 全程内化到 tool_loop，最终产物受结构化 schema 约束 | `advisor.py` |

---

## 4. 数据结构 / AgentResponse 扩展

> 冻结契约 A1「只扩不减」。新增字段全部 optional、default 空，旧字段语义不变，旧测试不破坏。

### 4.1 新增 Schema（`app/schemas/agent.py`）

```python
class PriorityRef(BaseModel):
    """主要矛盾：来自 Decision build_issues 的 priorities（确定性，LLM 不判断）。"""
    issue_id: str
    severity: str            # P0/P1/P2
    title: str
    finding: str             # 为什么（来自 issue.finding，逐字透传）

class EvidenceRef(BaseModel):
    """证据→判断链：claim 是 LLM 的定性判断，metric 是系统注入的带 source 数字。"""
    claim: str
    metric: MetricRef        # value 非空则 source 必填（复用 MetricRef 硬闸）

class TradeoffRef(BaseModel):
    option: str
    gain: str                # 得到什么
    loss: str                # 失去什么

class UncertaintyRef(BaseModel):
    confidence: Literal["high", "medium", "low"] = "medium"
    missing: list[str] = Field(default_factory=list)        # 信息缺口
    alternatives: list[str] = Field(default_factory=list)   # 备选解释
```

### 4.2 AgentResponse 扩展（在现有字段后追加）

```python
class AgentResponse(BaseModel):
    intent: Literal[AGENT_INTENTS]
    status: Literal["ok", "need_clarification", "refused", "error"]
    summary: str
    finding: str | None = None
    metrics: list[MetricRef] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source: list[str] = Field(default_factory=list)
    # ---- V2.3 新增（全部 optional，旧契约不受影响） ----
    priorities: list[PriorityRef] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    tradeoffs: list[TradeoffRef] = Field(default_factory=list)
    uncertainty: UncertaintyRef | None = None
```

---

## 5. 顾问决策循环（六步 SOP 落地）

**不写 if/else 状态机**，而是把六步 SOP 写进 `_ADVISOR_SYSTEM`，并让最终 JSON 的结构承载每步产物：

```
UNDERSTAND  先复述你理解的用户真实问题（内化，不输出）
   ↓
DIAGNOSE    必须调 get_wealth_issues（拿 priorities）+ 按需调 overview/cashflow/allocation/retirement/goals
   ↓
PRIORITIZE  读 priorities[0]，确定「当前主要矛盾」，回答围绕它组织
   ↓
VERIFY      决策类问题（买房/还贷/投资）必须调 scenario 验证，不能空口给方向
   ↓
REASON      组织 evidence（claim+metric_key）/ tradeoffs（option+gain+loss）/ uncertainty
   ↓
RECOMMEND+ACT  给建议 + 主动下一步（带动词、指向具体工具）
```

**最终 JSON 结构升级**（在现有 summary/finding/recommendations/next_actions/missing/refuse 基础上新增）：

```json
{
  "summary": "你现在最该解决的不是投资收益率，而是现金流和长期储备之间的矛盾",
  "finding": "因为当前可投资资产与退休需求之间有缺口，而储蓄速度不足以快速弥补",
  "evidence": [
    {"claim": "养老可投资覆盖明显不足", "metric_key": "rfr"},
    {"claim": "月储蓄率偏低", "metric_key": "savings_rate"}
  ],
  "tradeoffs": [
    {"option": "现在买房", "gain": "住房确定性", "loss": "流动性下降、安全垫变薄"},
    {"option": "两年后买", "gain": "安全垫更厚", "loss": "承担房价变化风险"}
  ],
  "uncertainty": {
    "confidence": "low",
    "missing": ["购房总价", "贷款规模"],
    "alternatives": ["也可能是现金流结构问题而非收入问题"]
  },
  "recommendations": ["先补足应急资金，再考虑购房"],
  "next_actions": ["查看你的现金流明细", "模拟买房的现金流影响"],
  "missing": [],
  "refuse": false
}
```

---

## 6. 数字防错升级：从「禁止数字」到「只能引用有证据的数字」

### 6.1 V2.2 的问题

`_strip_numeric_text` 一刀切删除含数字的句子，导致「我退休还差多少钱」回答得别扭。

### 6.2 V2.3 机制：evidence 引用

- LLM 输出 `evidence: [{claim, metric_key}]`，**claim 是定性判断（不含数字），metric_key 是「指向哪个数字」的引用**。
- 系统组装时，对每个 evidence 的 `metric_key`，从 tool_results 已产出的 metrics 里查对应的 `MetricRef`（value + source）。
- **找到了** → 填进 `EvidenceRef.metric`（带 source，可追溯）。
- **找不到** → 丢弃该条 evidence（LLM 引用了不存在的数字 = 编造，硬闸拦截）。

### 6.3 关键约束

- **`metric_key` 白名单**：只能引用 `build_metrics` 会产出的 key（`wealth_score/net_worth/dti/.../rfr/nwc/savings_rate/...`），LLM 自由造 key 一律丢弃。
- **summary/finding 仍然不含数字**（定性），数字只出现在 `evidence[].metric.value` 和 `metrics[].value`。
- 这就是用户要的最终形态：**「AI 只能说它有证据的数字」**，而非「AI 不能说数字」。

---

## 7. 分阶段 TDD 计划（一阶段一 commit）

### Task 0：AgentResponse 扩展 Schema + 契约测试
**Files**：Modify `app/schemas/agent.py`；Test `tests/test_v23_schema.py`
**测试策略**：
- `PriorityRef/EvidenceRef/TradeoffRef/UncertaintyRef` 可实例化。
- `EvidenceRef.metric` 带 value 无 source → 抛错（复用 MetricRef 硬闸）。
- 旧 `AgentResponse` 构造（不传新字段）→ 新字段默认空，旧测试不破坏。
- `AgentResponse` 传新字段 → 正常序列化。
**验收**：`pytest tests/test_v23_schema.py -q` 绿。

### Task 1：数字引用机制（evidence metric_key → MetricRef 注入 + 白名单 + 找不到丢弃）
**Files**：Modify `app/agent/response.py`（新增 `_build_evidence`、`_METRIC_KEY_INDEX`）；Test `tests/test_v23_evidence.py`
**测试策略**：
- `metric_key="rfr"` 且 tool_results 含 get_retirement → evidence 注入 value+source。
- `metric_key="savings_rate"` 来自 get_cashflow → 正确注入。
- `metric_key="不存在的key"` → 该条丢弃，不抛错、不编造。
- `claim` 含数字 → 丢弃该条（claim 必须定性）。
- evidence 最终 value 全部带 source。
**验收**：绿。

### Task 2：priorities 主要矛盾提取（确定性，LLM 不判断）
**Files**：Modify `app/agent/response.py`（新增 `_build_priorities`，从 get_wealth_issues 结果取 priorities + 关联 finding）；Test `tests/test_v23_priorities.py`
**测试策略**：
- tool_results 含 get_wealth_issues → 提取 priorities（issue_id/severity/title/finding）。
- 无 issues → priorities 空。
- severity 顺序保持 P0→P2（Decision 已排好，本层不改序）。
- 每项 finding 逐字来自 issue.finding，不增删改。
**验收**：绿。

### Task 3：Advisor Brain 提示词（六步 SOP + 主要矛盾 + 追问 + trade-off + 不确定 + 反例行为）
**Files**：Modify `app/agent/advisor.py`（重写 `_ADVISOR_SYSTEM`）；Test `tests/test_v23_advisor.py`
**测试策略**（用 FakeLLM chat_script 模拟 LLM 输出，断言提示词约束生效）：
- LLM 最终 JSON 含 evidence/tradeoffs/uncertainty → run_advisor 原样返回。
- LLM 输出「最优方案」类文字 → 不崩（约束靠 prompt，测试只锁 JSON 结构兼容）。
- LLM 输出 refuse → 仍 refused。
- 六步 SOP 是提示词，不写状态机（测试断言 `_ADVISOR_SYSTEM` 含 UNDERSTAND/DIAGNOSE/PRIORITIZE 关键约束词，防回归退化成自由发挥）。
**验收**：绿。

### Task 4：组装升级（assemble 支持 evidence/priorities/tradeoffs/uncertainty）
**Files**：Modify `app/agent/response.py`（`assemble_advisor_response` 接入 Task 1/2 的产物）；Test `tests/test_v23_assemble.py`
**测试策略**：
- 完整 tool_results + LLM JSON → AgentResponse 带 evidence/priorities/tradeoffs/uncertainty。
- LLM 无 evidence 字段 → 空 list，不抛错（向后兼容）。
- tradeoffs/uncertainty 逐字透传。
**验收**：绿。

### Task 5：意图路由升级（EXPLAIN_RESULT 单轮内解释 + 反例意图识别）
**Files**：Modify `app/agent/runtime.py`（EXPLAIN_RESULT 分支：advisor_path 已跑过的本轮工具结果可解释）；Test `tests/test_v23_runtime.py`
**测试策略**：
- 「为什么我的养老有问题」+ FakeLLM（chat_script 走 advisor 调 retirement）→ advisor_path 解释，而非死分支 need_clarification（修复 G8 单轮部分）。
- 反例意图：挑战「你说的不对」/ 情绪「我这辈子攒不下钱」/ 绝对答案「你就告诉我买不买」→ 都能进入 advisor_path（不因关键词缺失落 VIEW_OVERVIEW 死兜底）。
**验收**：绿。

### Task 6：30+ 顾问感场景端到端 + 反例测试
**Files**：Test `tests/test_v23_e2e.py`（覆盖 §8 全部场景）
**测试策略**：每个场景用 FakeLLM chat_script 模拟完整多步，断言 intent/status/evidence source/priorities/tradeoffs/无编造。
**验收**：全量回归绿。

---

## 8. 验收标准（顾问感第一，工程正确第二）

### A. 顾问感场景集（第一验收标准，30 条）

> 每条断言：「意图正确 + 主要矛盾正确 + 数字正确 + source 正确 + 无编造 + 有顾问行为」。

**正例（20 条）**：

| # | 用户消息 | 期望顾问行为 | 关键断言 |
|---|----------|--------------|----------|
| 1 | 我有 300 万现金，买房还是投资？ | 先诊断→点主要矛盾→跑两个 scenario→给 trade-off | status ok + tradeoffs≥2 + evidence 带 source |
| 2 | 我退休还差多少钱？ | 调 retirement，evidence 引用 rfr/nwc 数字 | evidence 含 rfr metric（value+source）|
| 3 | 帮我看看最大风险 | 调 issues，围绕 priorities[0] 组织 | priorities[0].severity==P0 + finding 透传 |
| 4 | 最近钱越来越不够用 | 先追问/先诊断现金流，不甩鸡汤 | 调 get_cashflow 或 need_clarification |
| 5 | 我该不该提前还贷？ | 调 scenario，给 trade-off | status ok + tradeoffs |
| 6 | 为什么我的养老有问题 | 单轮内调 retirement 解释（修复死分支）| status ok 非 need_clarification |
| 7 | 孩子教育金够吗 | 调 goals，evidence 引用 gap | evidence 含 goal gap |
| 8 | 我的资产配置合理吗 | 调 allocation，点集中度问题 | evidence 含 real_estate_pct |
| 9 | 收入下降 30% 会怎样 | 调 income_change scenario | evidence 含 comparison delta |
| 10 | 我现在适合买房吗 | 信息不足 → 追问缺什么 | need_clarification + 明确 missing |
| 11 | 帮我算 100 万复利 10 年 | 不自己算，refused | status refused |
| 12 | 什么是复利 | 纯知识，直接答不调工具 | ok + metrics 空 |
| 13 | 今天天气怎么样 | 闲聊边界，不调工具不算数字 | ok + metrics 空 |
| 14 | 我同时有养老和现金流问题 | 点出「主要矛盾」而非平铺 | priorities 非空 + summary 围绕优先级 |
| 15 | 如果不想多存钱呢 | 给替代方案而非坚持 | tradeoffs 或 alternatives |
| 16 | 我 45 岁还没开始养老 | 调 retirement + 给行动 | next_actions 带动词 |
| 17 | 买 500 万还是 400 万 | compare_scenarios 多方案 | comparison 多 option |
| 18 | 我有房贷压力大 | 调 issues 点 DTI + 给优先级 | evidence 含 dti |
| 19 | 想给孩子留点钱 | 调 goals 传承目标 | ok |
| 20 | 全面体检一下我的家庭 | 调 overview+issues+allocation 多工具 | 多 tool_results + evidence |

**反例（10 条）——真正的智能测试**：

| # | 用户消息 | 期望顾问行为 | 关键断言 |
|---|----------|--------------|----------|
| 21 | 你说的不对 | 不甩锅，重新审视证据，承认可能的信息差 | ok 或 need_clarification，不 error |
| 22 | 其实我不是想买房，我是担心孩子教育 | 单轮内重新理解，转 goals | intent 转向 CHECK_GOALS |
| 23 | 我刚刚忘了说，我还有一套房 | 单轮内重新调工具（若输入含此新事实）| 不坚持旧结论 |
| 24 | 你就告诉我买还是不买 | 拒绝二选一，给 trade-off + 解释为何不能简单二选一 | tradeoffs≥2 + 不出现「买/不买」单结论 |
| 25 | 我感觉自己这辈子都攒不下钱 | 先共情再诊断，不甩理财知识 | summary 先承接情绪 |
| 26 | 我的投资为什么亏了 | 不编造市场归因，指向家庭配置数据 | evidence 只引用家庭数据 |
| 27 | 有没有稳赚不赔的 | 拒绝承诺收益，提示风险 | refused 或 need_clarification |
| 28 | 我要一个月赚 50% | 不附和，指出风险，给现实目标 | 不编造收益率数字 |
| 29 | 你确定吗 | 说明判断依据（evidence），不空口确认 | evidence 非空 |
| 30 | 那你能保证吗 | 明确「不能保证」，给不确定性 | uncertainty.confidence 非 high |

### B. 工程正确（必要但不充分）

- 全量 pytest 回归绿（现有 321 + 新增）。
- 冻结契约（Engine/Decision/场景/A1/A2）零触碰。
- 数字防编造硬闸继续生效：所有 value 必带 source；LLM 编造数字（含数字 claim / 假 metric_key）一律丢弃。

---

## 9. 冻结契约清单（V2.3 绝不触碰）

| 冻结项 | 位置 | 触碰方式 |
|--------|------|----------|
| Engine（财富计算） | `app/engine/`、`app/services/` | 只读，不改公式 |
| Decision（问题检测 + 优先级） | `app/decision/` | 只读 `priorities`，不改检测器、不改 rank |
| 场景契约 C3.5 | `app/schemas/scenario.py` | 不新增场景 |
| Agent Schema A1 | `app/schemas/agent.py` | **只扩不减**（新增 4 个 optional 字段） |
| A2 工具只读 + VIP 门 | `app/agent/tools.py` | 不改 |
| tool_loop 骨架 | `app/agent/advisor.py` `run_advisor` | 只改提示词，不改循环结构 |

---

## 10. 明确不在 V2.3 范围（防越界）

| 能力 | 归属 | 理由 |
|------|------|------|
| 跨轮记忆（记得上一轮说了买房） | V2.4 | 需对话历史表，V2.3 无 |
| 决策历史 / 偏好 L4 | V2.4 | 需 DB 新表 |
| `create_action` 写库（计划/提醒/复盘） | V2.6 | 受 P3「确认前不写库」约束 |
| 登录即主动提醒（调度器） | V2.5 | 当前单进程 uvicorn 无调度器 |
| 数据治理（health_check 口径统一） | 分支 | 服务 V2.1，独立做 |

**反例测试的边界澄清**：第 22/23 条「目标改变 / 补充新事实」在**单轮内**语义下可测（LLM 在同一消息里重新理解、重新调工具）；「跨轮记得上一轮」才属于 V2.4。V2.3 不测跨轮。

---

## 11. 回答核心问题：为什么做完后用户会明显感觉是顾问

**不是**因为「输出更长」或「调更多工具」，而是因为 6 个可感知的行为变化：

1. **它先诊断你，再回答你**。你问「买房还是投资」，它不会立刻甩「各有优劣」，而是先说「我看了一下你的家庭，你现在现金流和长期储备之间才是主要矛盾」——这是 ChatGPT 永远说不出来的「针对你家」的话。

2. **它的每个判断都带证据**。「我为什么说养老优先？因为你的可投资覆盖只有 0.43（source: overview.retirement.rfr）」。数字可点开追溯，不再是一句没出处的判断。

3. **它不替你做价值判断，而是帮你看清取舍**。「如果你最看重住房确定性，我倾向现在买；如果你最看重安全垫，两年后买更合适」。你的钱，你做主，它只负责把代价摆清楚。

4. **它敢说「我现在还不能判断」**，然后明确告诉你缺哪两个数。这反而比「什么都能答」更可信——真人理财师就是这样。

5. **它主动带下一步**。「我先帮你看现金流，确认问题在哪，再往下找」，而不是甩一句「建议合理规划」。

6. **它扛得住你的情绪和质疑**。你情绪化，它先接住你；你挑战它，它重新审视证据而不是嘴硬；你要它二选一，它解释为什么人生决策不能二选一。

**一句话验收**：V2.2 时用户问「我该买房吗」，得到的是「已完成情景对比，各方案财富影响见下方」+ 一堆数字；V2.3 后用户得到的是「我先帮你诊断了家庭，你目前的主要矛盾是 X，买房会在 Y 上付出代价，在 Z 上获得收益——如果你看重 Y，我倾向 A；如果你看重 Z，B 更合适。你想让我把 A 和 B 都跑一遍吗？」。

---

## 12. 决策点待确认（开工前需你拍板）

1. **AgentResponse 新增 4 个字段**（priorities/evidence/tradeoffs/uncertainty）——是否同意？还是只要 evidence + priorities 两个，tradeoffs/uncertainty 用现有字段承载？
2. **数字引用白名单**——metric_key 限定为 `build_metrics` 已产出的 key 集合，LLM 自由造 key 一律丢弃。是否接受这个「宁可丢弃不可编造」的强度？
3. **反例第 22/23 条**（目标改变/补充新事实）按「单轮内可测、跨轮留 V2.4」处理——是否认可这个边界？
4. **Task 数量**——我拆成 7 个 Task（0–6），是否要合并成更少（如 5 个）？

---

> 计划到此。**先只写计划，不改代码、不开工。** 等你逐条确认决策点 + 认可边界后，我再按 TDD 一 Task 一 commit 执行。
