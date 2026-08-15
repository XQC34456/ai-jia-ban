# Phase 2 第一刀「档案对照（filing-archive reconciliation）」工作计划

> 状态：**待用户确认（2026-08-16）**。Phase 1 冻结基线 `v1.0-phase1`（23b67df）之后、Phase 2 的第一刀。
> 依据：V1.0 主纲 [plan-v10-restructure.md](plan-v10-restructure.md) Phase 2「家庭数据智能复用」+ 用户 2026-08-15/16 决策。
> 用户已确认的两个决策点：**冲突判定 = 同类别异值**；**冲突写库 = 确认后覆盖更新**。

---

## 0. Phase 2 范围框定（钉死，取自主纲 §Phase2/§九/§五）

| 维度 | 钉死内容 |
|------|----------|
| **目标** | 家庭数据智能复用：已有数据不被重复询问、不重复建档；建档是渐进式（一句话持续完善档案）。服务论断 #4「已有数据重复询问」 |
| **5 个核心工作** | ①档案对照（本刀）②增量建档 ③字段冲突 ④来源追踪 ⑤缺数检测 |
| **验收锚（§九）** | 数据复用：用户复述档案已有信息 → 系统识别并复用，不重复建档、不重复问 |
| **不做什么（Phase 2 全局）** | 不碰 Engine/Decision 计算口径；不碰铁律（防编造/内部 id 等）；不碰前端信息架构；不做数据治理/health_check 统一口径（roadmap §6 暂缓服务 Phase 2） |

---

## 1. 任务本质（一句话）

**建档路径在弹确认卡前对照当前档案**，把每个抽取动作分成 `new / exists / conflict` 三类：已存在的复用不写、真新增正常写、同类别异值走覆盖更新——直接实现「不重复问」和「建档是渐进式」，并修掉「金额不同的同类别静默重复插入」这个数据污染 bug。

## 2. 现状取证（根因）

| 事实 | 结论 |
|------|------|
| `apply_confirmation`（profile.py:141）逐条 `db.apply_action`，**写库前无对照** | 用户复述/更新数据时没有「已存在/冲突」判断 |
| `_cashflow_exists`（db.py:602）只按「类别+金额+周期」exact 判重 | 金额不同的同类别 → **静默重复插入**（Q10「工资 3 万」vs 档案 2.5万+1.5万 → 第三笔收入） |
| `_asset_exists`（db.py:594）只按「type+name+value」exact 判重 | 同 type 不同 value → 重复插入；name 跨抽取不稳定（RuleExtractor「存款」→ name=存款，档案是 name=现金） |
| liability/goal/person **无任何去重** | 直接 INSERT，连 exact 都没有 |
| Q10 实证（advisor_eval/family.py 档案）：月收入 4 万（2.5+1.5）、现金 50 万 | 消息「我月收入 3 万，存款 50 万」= **重复**（存款 50 万已在）+ **冲突**（收入 3 万 vs 4 万） |
| 冻结基线签名（benchmark12.py:344）**不含** ConfirmCard 的 message_head/pending_items；Q10 reanswer 走 `cancel_and_reanswer` 独立路径 | 改确认卡内容 **预期零基线 diff**，无需重冻结 |

## 3. 第一刀 A 边界

### 做
1. 新增纯函数 `reconcile_actions(family_id, actions)`：逐动作对照 `db.dump_family`，返回带状态的对照结果。
2. `create_confirm` 调用它，把对照结果存进 `_PENDING`；确认卡按状态组织内容。
3. `apply_confirmation`（确认分支）按状态写库：`new` 插入、`exists` 跳过、`conflict` 单匹配覆盖、`conflict` 多匹配（歧义）跳过+注明。

### 不做（第一刀明确边界）
- **不改** ConfirmCard / AppliedResponse schema（对照信息走 items/message 文案）。
- **不改前端**（chat.js 已渲染 message/items/groups 文本，零改动）。
- **不改 Advisor 主链**：entry.py 建档 gate 仍返回 ConfirmCard；取消→re-answer 路径零改动。
- **不碰** Engine/Decision/铁律/冻结基线。
- **不做**：增量建档、来源追踪、缺数检测、对话式澄清、并存版本、新事件埋点类型。

## 4. 设计

### 4.1 身份字段（粗粒度稳定，避开 name 跨抽取不稳定）

| kind | 对照表 | identity（身份字段） | value（判断 exists/conflict 的值字段） |
|------|--------|----------------------|----------------------------------------|
| income | cashflow(flow_type=income) | category + period | amount |
| expense | cashflow(flow_type=expense) | category + period | amount |
| asset | asset | type | value |
| liability | liability | type | principal、monthly_payment |
| goal | goal | type | target_amount、current_saved |
| person | person | name | birth_year、monthly_income |

> 取 `dump_family` 各表（persons/assets/liabilities/cashflows/goals），与动作 `fields` 按上表比对。动作字段缺省值沿用 `apply_action` 的默认（income category 缺省"工资"等）。

### 4.2 分类算法（每类独立）

```
cand   = 档案中 identity 全同的行
exact  = cand 中所有 value 字段全同的行
→ exact 非空            ⇒ exists
→ cand 恰 1 行          ⇒ conflict（matched_id = cand[0].id，可覆盖）
→ cand > 1 行且值不同   ⇒ conflict（matched_id = None，歧义：不自动覆盖）
→ cand 空               ⇒ new
```

**多匹配歧义安全**（Q10「收入 3 万」vs 档案 2.5万+1.5万）：不确定覆盖哪条 → 不自动写，确认卡标注「档案有多笔记录」，确认后不动。既修掉重复插入 bug，又避免危险地随便覆盖一条。

### 4.3 写库（`apply_confirmation` confirmed=True）

| 状态 | 写库 | applied 文案 |
|------|------|-------------|
| new | `db.apply_action`（原样） | 「已记录：X」 |
| exists | 跳过 | 不进「已记录」，单独注明「X 已在档案」 |
| conflict（matched_id） | `db.update_entity(table, matched_id, value_fields)` 覆盖 | 「已更新：X（档案原为 …）」 |
| conflict（歧义） | 跳过 | 「未改动：X（档案有多笔记录）」 |

> 冲突覆盖复用现成 `db.update_entity`（db.py:801）——`ENTITY_COLS` 已覆盖全部 5 表，只更新传入的非 None 字段（income 只改 amount，liability 只改 monthly_payment 等），identity 字段不变。

### 4.4 确认卡呈现（零 schema/前端变更）

- `items` = new + conflict 动作的 summary；conflict 项文案**追加差异标注**：
  - 单匹配：「月收入 3 万 ⚠️ 档案现在是 2.5 万」
  - 歧义：「月收入 3 万 ⚠️ 档案有多笔工资记录，未自动改动」
- `exists` 不进 items，message 追加注：「（现金 50 万已在档案，无需重复建档）」。
- 全 exists（无 new/conflict）：message =「以下信息已在档案中，无需重复建档：…」，items=[]，确认不写任何东西（仍返回 ConfirmCard，保持建档 gate 语义）。

### 4.5 代码落点

- **Modify `app/agent/profile.py`**：
  - 新增 `@dataclass ReconciledAction {action, status, table, matched_id, archive_value}`。
  - 新增 `reconcile_actions(family_id, actions) -> list[ReconciledAction]`（读 dump_family，纯对照逻辑）。
  - `create_confirm`：调 reconcile，`_PENDING[pending_id]["reconciled"] = [...]`，按状态组 items/message。
  - `apply_confirmation`：按 reconciled 状态写库 + 组 applied 文案（含 exists/歧义注明）。
- **`app/agent/entry.py`**：零改动（create_confirm 签名不变）。
- **`app/db.py`**：零改动（复用 dump_family / apply_action / update_entity）。
- **New `tests/test_filing_reconcile.py`**。

## 5. 测试（TDD，先红后绿）

| 用例 | 场景 | 断言 |
|------|------|------|
| R1 新增 | fresh family + income 30000 | status=new；card items 含之；confirm → 1 行插入 |
| R2 已存在 | 先插 income 25000 再提交同一条 | status=exists；card items 不含；confirm → 仍 1 行 |
| R3 冲突单匹配覆盖 | 档案 1 条工资 25000，提交 30000 | status=conflict(matched_id)；card 标注「档案现在是 2.5 万」；confirm → 1 行且 amount=30000 |
| R4 冲突多匹配安全 | 档案 2 条工资 25000+15000，提交 30000 | status=conflict(matched_id=None)；confirm → 仍 2 行、不覆盖；message 注明 |
| R5 资产存在（type 身份） | 档案 现金500000，提交 存款500000 | status=exists（type=存款 命中，name 差异不影响）；不写 |
| R6 Q10 端到端 | converse「我月收入3万，存款50万」→ 卡 → confirm | 卡 items 不含存款；confirm 后档案无第三笔收入 |
| R7 全存在 | 档案已有 存款50万，提交「我存款50万」 | card message=已在档案，items=[]；confirm 不写 |

**已有测试影响**：test_agent_profile / test_v27_extraction / test_advisor_context / test_v24_* 用 fresh family（或 family 1 空档案）→ 全 `new` → 行为不变；跑全量 pytest 确认零非预期失败。

## 6. 验证（做完必须自我验证）

1. `pytest tests/test_filing_reconcile.py -v` → 7 用例绿。
2. 确定性 12 题基准 → 与冻结基线 `advisor_eval/baseline_benchmark12.json` **零 diff**（声明：ConfirmCard 的 message_head/pending_items 不在签名内；Q10 reanswer 独立路径零改动）。
3. 全量 `pytest` → 全绿（572+）。
4. 真实 12 题（`--real --report`）→ Q10 弹卡 items 由 2 → 1（存款 50 万不再弹），真实模式确认无第三笔收入。
5. 独立 commit（只动 profile.py + 新测试 + 本计划文档）。

## 7. 明确不做的（边界声明，防范围蔓延）

- 不改 schema / 前端 / Advisor 主链 / Engine / Decision / 铁律 / 冻结基线。
- 不做对话式澄清（「你说 3 万，档案是 2.5 万，是更新吗？」）——冲突直接上确认卡标注，用户确认即覆盖；澄清循环属缺数检测/后续工作。
- 不做并存版本（memory_fact 的 version 语义只对 goal，财富主表覆盖即覆盖，不保留历史版本）——历史可追溯属「来源追踪」后续工作。
- 不新增事件埋点类型（product_event 8 类不动）。
- 不做资产 type 内的多账户区分（歧义时安全跳过，不做选择器 UI）。

## 8. 风险与已知限制（记录，不阻塞）

| 限制 | 说明 |
|------|------|
| `_PENDING` 快照时效 | 对照在弹卡时完成；弹卡→确认间档案被改（单轮内概率极低）会用旧对照 → 记录为已知限制 |
| 身份字段是启发式 | type/category 粗粒度可能把同类型不同账户误判为冲突（此时走歧义安全路径，不覆盖），后续「来源追踪」可增强 |
| 资产只按 type 判身份 | 同 type 多笔资产 + 用户复述其中一笔 → 歧义安全跳过，不做精确匹配（name 不可靠，后续可加规范化） |
