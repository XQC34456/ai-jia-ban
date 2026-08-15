# V2.1 Context Engine · 实施计划

> 唯一主体计划的 **V2.1 阶段展开**。依据 [plan-ai-advisor-core-architecture.md](plan-ai-advisor-core-architecture.md) §10 + [plan-master-roadmap.md](plan-master-roadmap.md) §4。
> 本阶段只做「让 AI 看见家庭」，**不做回答生成**（那是 V2.3）。做完 V2.1，AI 回答本身不变，但地基就位。

---

## 0. 一句话目标

**把 `db.dump_family` 的九块原始数据 + `build_overview`/`build_issues`/`build_goals` 的确定性输出，组装成 LLM 可读的 Wealth Context，并打通注入 provider 的通道。**

- 用户感知：V2.1 结束时 AI 回答不变（因为回答生成在 V2.3）。
- 工程价值：V2.2（Tool Calling）、V2.3（Advisor Brain）的地基。没有它，后面一切「让 AI 懂我家」都是空谈。

---

## 1. 为什么不是「简单 prompt 拼接」

用户警告过：「不要为了接上 DeepSeek 而做成简单 prompt 拼接」。本计划与「简单拼接」的本质区别：

| 维度 | 简单 prompt 拼接（要避免） | 本计划的 Context Engine |
|------|---------------------------|------------------------|
| 数据来源 | 把 `dump_family` 原始 JSON 一股脑 dump 进 prompt | 每个数字来自 `build_overview`/`build_issues`（Engine 确定性输出） |
| 数字防编造 | LLM 可能基于原始数据自行推算、编数字 | 每个数字带 `source` 字段路径，沿用 `MetricRef` 硬闸语义 |
| 计算边界 | LLM 可能"算"出 RFR/DTI | 组装器是纯函数，只「搬运」Engine 已算好的数字，绝不计算 |
| 消费时机 | 拼给意图路由（判断意图不需要家庭数据，纯浪费） | 通道打通但不消费；真正消费在 V2.2（tool 决策）+ V2.3（回答生成） |

**铁律（延续 P1/P4）**：组装器零 LLM、零 I/O、零财富计算，只引用 Engine/Decision 已产出数字，每个数字带 source。

---

## 2. 完整链路数据流（Context → Memory → Tools → Reasoning → Response）

用户要求「明确每一层到底给模型什么信息」。这是全链路图，V2.1 只负责 **Context** 这一层，其余标注阶段：

```
用户消息
   ↓
converse(message, user, llm, context)
   ↓
【V2.1 新增】build_wealth_context(family_data)   ← 组装 4 块 Wealth Context（纯函数）
   ↓
┌─ 建档抽取 RuleExtractor → ConfirmCard（不碰 LLM）
└─ handle()
     ↓
   route_intent(message, llm)          ← 【不注入 context】判断「想问什么」不需要家庭数据
     ↓
   【V2.2】tool_calling：LLM 读 context + 工具 schema → 决定调哪个 tool + 参数
     ↓
   dispatch(intent, user) → A2 工具 → build_overview / build_issues / build_goals
     ↓
   【V2.3】advisor_brain：LLM 读 context + tool 结果 → 生成「针对你家」的回答
     ↓
   build_response → AgentResponse（metric.value 必带 source，LLM 只组织语言）
     ↓
   前端渲染
```

**每一层给模型什么信息（灵魂表格）**：

| 层 | 阶段 | 给模型的输入 | 模型输出 | 模型绝不能做 |
|----|------|-------------|---------|-------------|
| Context | **V2.1（本阶段）** | 4 块 Wealth Context（数字带 source） | 无（纯组装，不生成） | 组装器绝不计算 |
| Memory | V2.4 | 历史对话 + 决策历史 + L4 偏好 | 无 | — |
| Tools | V2.2 | Context + 10 工具 schema | 决定调哪个 tool + 参数 | 不自答数字 |
| Reasoning | V2.3 | Context + tool 结果 | 自然语言解释/建议 | 不编数字、不甩 RFR |
| Response | V2.1→V2.3 | AgentResponse（metric.value+source） | 组织语言 | value 必带 source |

---

## 3. Wealth Context 四块结构（V2.1 交付物）

`build_wealth_context(family_data)` 返回四块（Conversation 第五块留 V2.4）：

| 块 | 内容 | 来源（绝不重算） |
|----|------|-----------------|
| **Family Context** | 成员（关系/出生年/职业）、资产/负债明细、保险 | `family_data` 原始（`dump_family`） |
| **Financial Context** | 财富评分/净资产/现金流/流动性/DTI/配置/养老 RFR-NWC | `build_overview` 关键字段 |
| **Decision Context** | P0/P1/P2 问题 + 建议（去重） | `build_overview.issues/recommendations` |
| **Goal Context** | 目标 + 缺口 + 每月需存 | `build_overview.goals` |

**关键设计**：只调一次 `build_overview(family_data)`（它内部已含 `build_issues` + `build_goals`），再补 `family_data` 原始明细。避免重复计算 + 保证口径一致。

返回结构（dict，含 `to_text()` 序列化为紧凑文本供 LLM 读）：

```python
{
  "family":    {"members": [...], "assets": [...], "liabilities": [...], "insurance": [...]},
  "financial": {"wealth_score": {"value": 72, "source": "overview.wealth_score"}, ...},
  "decision":  {"issues": [{"severity": "P0", "title": ..., "finding": ...}], "recommendations": [...]},
  "goals":     [{"name": ..., "gap": {"value": 200000, "source": "overview.goals.0.gap"}, ...}],
}
```

> `to_text()` 输出人话摘要（如「净资产 320 万（source: overview.net_worth），其中房产占比 68%…」），但**数字永远跟着 source 标注**，让 LLM 知道这数字是有出处的、不能改。

---

## 4. 分阶段 TDD 计划

> 一阶段一 commit；冻结契约（Engine/Decision/Schema A1/A2）零触碰；全量回归通过才进下一阶段。

### Task 0：数据治理（轻）— 锁定干净原料

**Files：**
- Test: `tests/test_v21_context.py`（新建，含契约测试）
- 标注: `app/db.py`（`person.monthly_income` 双口径注释）、`app/calc_engine.py`（shim 注释）、`app/engine/metrics.py`（`safety_margin` 注释）

**Interfaces：**
- 无新增函数；补契约测试锁定「口径一致」事实。

**内容（只标注 + 锁契约，不改逻辑、不删代码）：**

1. **口径统一确认**：`build_problems`（`/api/family` 用）= `build_issues` 拍平；`build_overview` 内部也用 `build_issues`。补测试断言两者问题集合一致，防回归。
2. **死字段标注**（不删）：
   - `person.monthly_income` 与 `cashflow(flow_type=income)` 双口径 → Context Engine 统一从 `build_overview.cashflow.income` 取，不读 `person.monthly_income`。
   - `metrics.snapshot` 的 `safety_margin`/`goals_funding` 是 Engine 中间量，overview 未暴露，V2.1 不消费。
   - `calc_engine.py` 兼容层有 test lock，V2.1 不清理。

- [ ] **Step 1** 写契约测试：

```python
def test_issues_consistent_across_endpoints():
    """/api/family 的 problems 与 /api/wealth/overview 的 issues 同源。"""
    data = make_family(...)  # 复用现有 fixture
    problems = decision.build_problems(data)
    overview = build_overview(data)
    assert [p["title"] for p in problems] == [i["title"] for i in overview["issues"]]
```

- [ ] **Step 2** 跑测试（应先通过——这是锁现状，不是改行为）
- [ ] **Step 3** 加 3 处死字段注释（db.py / calc_engine.py / metrics.py）
- [ ] **Step 4** 全量回归 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m pytest -q` → 261+ passed
- [ ] **Step 5** commit

---

### Task 1：ContextEngine 组装器（纯函数）

**Files：**
- Create: `app/agent/context.py`
- Test: `tests/test_v21_context.py`

**Interfaces：**
- Produces: `build_wealth_context(family_data: dict) -> dict`（含 `to_text()`）
- Consumes: `build_overview`（`app.services`）、`build_issues`（`app.decision`，经 overview 透出）

- [ ] **Step 1** 写失败测试：

```python
def test_empty_family_returns_empty_context():
    ctx = build_wealth_context({"family": {}, "persons": [], "assets": [],
                                "liabilities": [], "cashflows": [], "goals": [],
                                "reminders": [], "insurance": [], "family_profile": None})
    assert ctx["family"]["members"] == []
    assert ctx["financial"]["wealth_score"]["value"] is None

def test_context_numbers_carry_source():
    ctx = build_wealth_context(make_family_with_data())
    assert ctx["financial"]["net_worth"]["source"] == "overview.net_worth"
    # 每个带 value 的数字都必须有 source（防编造闸门）

def test_context_matches_overview():
    """组装器搬运的数字与 build_overview 完全一致，不重算。"""
    data = make_family_with_data()
    ctx = build_wealth_context(data)
    ov = build_overview(data)
    assert ctx["financial"]["wealth_score"]["value"] == ov["wealth_score"]
```

- [ ] **Step 2** 跑测试 → FAIL（`build_wealth_context` 未定义）
- [ ] **Step 3** 实现 `app/agent/context.py`（纯函数 + `to_text()` 序列化）
- [ ] **Step 4** 跑测试 → PASS
- [ ] **Step 5** commit

---

### Task 2：provider 注入通道（向后兼容）

**Files：**
- Modify: `app/agent/provider.py`（`LLMProvider` 协议加 `context` 参数）
- Modify: `app/agent/providers/deepseek.py`（`complete_json` 加 `context`）
- Modify: `app/agent/provider.py` 的 `NullProvider`/`FakeLLMProvider`（同步签名，Fake 捕获 context）

**Interfaces：**
- Produces: `complete_json(self, system, user, schema, context: dict | None = None) -> dict | None`
- 向后兼容：`context=None` 时行为与现状完全一致（现有 2 处调用不变）

- [ ] **Step 1** 写失败测试：

```python
def test_fake_provider_captures_context():
    fake = FakeLLMProvider(script=[{"intent": "VIEW_OVERVIEW"}])
    fake.complete_json("sys", "user", {}, context={"financial": {"net_worth": {"value": 100, "source": "x"}}})
    # FakeLLMProvider 记录最近一次收到的 context
    assert fake.last_context is not None

def test_deepseek_injects_context_as_message():
    """context 非空时，序列化进 messages，且数字带 source 标注。"""
    # 用 monkeypatch 拦截 httpx.post，断言 payload["messages"] 含 context 文本
```

- [ ] **Step 2** 跑测试 → FAIL
- [ ] **Step 3** 实现：`complete_json` 加 `context` 参数；DeepSeek 把 `context.to_text()` 作为独立 system message 注入；Null/Fake 同步
- [ ] **Step 4** 跑测试 → PASS + 全量回归（现有 2 处调用不带 context，行为不变）
- [ ] **Step 5** commit

---

### Task 3：converse 预取 + 端到端契约测试（打通链路）

**Files：**
- Modify: `app/agent/entry.py` 或 `runtime.py`（预取 context 并暂存）
- Test: `tests/test_v21_context.py`（端到端 + H 评测雏形）

**Interfaces：**
- `converse` 在进入 `handle` 前预取 `family_data` → `build_wealth_context`，暂存（V2.1 不改意图路由行为，只打通链路）

- [ ] **Step 1** 写失败测试（H 评测雏形，3~5 黄金场景）：

```python
def test_golden_view_overview_context_injected():
    """用户问「财富评分多少」→ context 被组装且注入 provider。"""
    user = {"family_id": 1, "tier": "vip"}
    fake = FakeLLMProvider(script=[...])   # 让 route_intent 返回 VIEW_OVERVIEW
    converse("我的财富评分是多少", user, llm=fake)
    assert fake.last_context is not None  # 链路打通

def test_golden_context_numbers_match_engine():
    """黄金场景：context 里的数字 == build_overview，且都带 source（无编造）。"""
    ...
```

- [ ] **Step 2** 跑测试 → FAIL
- [ ] **Step 3** 实现预取（注意：`extract_actions` 命中建档时不预取，避免无谓开销）
- [ ] **Step 4** 跑测试 → PASS + 全量回归 + node 12
- [ ] **Step 5** commit

---

## 5. 验收标准（V2.1 完成定义）

1. **组装正确性**：`build_wealth_context` 输出的每个数字 == `build_overview`/`build_issues`/`build_goals` 对应字段，零重算、零编造。
2. **防编造硬闸**：context 里每个带 `value` 的数字必有 `source` 字段路径。
3. **注入通道**：`complete_json` 支持 `context` 参数；`context=None` 时行为与现状逐字节一致（现有 2 处调用回归通过）。
4. **链路打通**：`converse` 预取 context，H 评测雏形（3~5 黄金场景）断言「意图正确 + context 数字正确 + source 正确」。
5. **冻结契约零触碰**：Engine/Decision/Schema A1/A2 无任何改动。
6. **全量回归**：pytest 261+ passed · node 12 passed。

---

## 6. 明确不在 V2.1 范围（防越界）

- ❌ 不做 LLM 回答生成（V2.3）
- ❌ 不做 tool calling（V2.2）
- ❌ 不改意图路由行为（意图判断不需要家庭数据）
- ❌ 不做 Conversation Memory（V2.4）
- ❌ 不清理 `calc_engine.py` shim（有 test lock）

---

## 7. 需你确认的 3 个决策点

1. **V2.1 做完 AI 回答不变**（地基就位，变智能在 V2.3）——是否接受这个边界？
2. **context 注入通道「先建不消费」**：V2.1 打通 provider 注入能力，但不在意图路由消费（真正消费在 V2.2/V2.3）——是否同意？
3. **计划落盘位置**：`docs/plan-v21-context-engine.md`（与主体计划并列，作为 V2.1 展开）——是否 OK？
