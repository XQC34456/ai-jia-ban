# V2.4 Conversation Memory 交付报告

> 状态：**已完成并全量验证通过**（2026-08-14）。
> 上一阶段：V2.3 Advisor Brain（commit `df45207`）。

---

## §1 交付结论

V2.4 三层顾问记忆已落地，6 类多轮问题全部机制性解决，4 条硬约束 + 数字防编造铁律不破。

**核心反转达成**：从「每次见用户都重新认识这个家庭」→「持续了解这个家庭」。

---

## §2 7 个 Task 对应 commit

| Task | 内容 | commit |
|------|------|--------|
| 0 | Memory 存储 Schema（3 张新表 + 版本化 CRUD） | `9b6df27` |
| 1 | 短期对话记忆（converse 写轮 + 限量摘要 builder） | `0d5bea4` |
| 2 | 家庭事实记忆（goal 写 confirmed + 数字防编造闸） | `f6bcf4c` |
| 3 | 顾问判断记忆（priorities + evidence + 有效条件快照） | `9378d97` |
| 4 | 判断失效检测（确定性逐 key 对比 → stale） | `191311b` |
| 5 | Memory 注入 advisor（三层摘要进 system prompt） | `8d51b9a` |
| 6 | 端到端 6 类多轮场景 | `b2d4e79` |

---

## §3 全量测试结果

| 层 | 结果 |
|----|------|
| pytest（全量 413 条，含 V2.1~V2.4） | **413 passed** |
| node（前端解释层单测 12 条） | **12 passed** |
| playwright e2e（3 条） | **3 passed** |

V2.4 新增测试 35 条：
- Task 0 存储 Schema：9 条
- Task 1 短期记忆：4 条
- Task 2 家庭事实：5 条
- Task 3 顾问判断：4 条
- Task 4 失效检测：3 条
- Task 5 注入：4 条
- Task 6 端到端：6 条

---

## §4 6 类多轮场景逐项结果

| 类 | 场景 | 断言 | 结果 |
|----|------|------|------|
| A 连续理解 | 「为什么养老有问题」→「那55岁退休呢」 | 第二轮 system 注入第一轮对话 | ✅ |
| B 用户纠正 | 「我想买房」→「不是，是给父母换房」 | 纠正被记录进短期记忆 | ✅ |
| C 家庭状态变化 | 收入 1万→5万 | 旧判断确定性失效（stale） | ✅ |
| D 判断失效 | 判断现金流 P0 → 收入翻倍 → 再问 | 第二轮注入「已失效」提示 + 重新评估 | ✅ |
| ④ 目标变化 | 教育金 50万→30万 | goal version 1→2，旧版本 superseded | ✅ |
| ⑤ 历史事实更新 | child_birth_year 2018→2016 | version 1→2，旧事实 superseded，不误导 | ✅ |

> 注：计划 §8 原写「约 15 条」，实际每类 1 条端到端（共 6 条）+ 各类机制单元测试覆盖更细的契约（版本化/限量/防编造/stale），合计 35 条 V2.4 测试。多轮场景的「AI 仍知道在谈养老」通过共享 FakeLLMProvider 的 `chat_messages` 断言第二轮 system prompt 真实注入了第一轮记忆，而非仅测「DB 里存了两条」。

---

## §5 失败场景及原因（过程记录，均已修正）

| 场景 | 失败原因 | 修正 |
|------|---------|------|
| Task 1 `build_conversation_summary_limited` | 测试用 summary `结论0` 含数字，被 V2.3 防编造闸清空 | 改用无数字 summary `结论甲/乙/丙`——这恰好反证防编造闸对 assistant 摘要也生效 |
| Task 2 `test_income_not_in_memory_fact` | 误以为收入在 `income` 表 | 收入实际在 `cashflow` 表，修正断言 |

**两处都是测试写法问题，非产品缺陷**。无产品层回归。

---

## §6 4 条硬约束验证

| # | 硬约束 | 落地方式 | 状态 |
|---|--------|---------|------|
| 1 | 当前数据永远高于记忆 | 记忆层只读 `memory_*` 表 + `dump_family` 做失效快照；Engine/Decision 依旧只读 db 主表，**绝不读 memory 表** | ✅ |
| 2 | inferred 绝不伪装 confirmed | source/confidence 由**写入位置**决定：`apply_confirmation`→`chat_confirmed`，对话推断→`inferred`（闸已建，推断入口留 V2.5） | ✅ |
| 3 | 历史事实不参与财富计算 | `memory_fact` 只注入 system prompt 作上下文，`build_overview`/`build_issues` 不读它 | ✅ |
| 4 | Advisor 知道为什么重判 | `detect_invalidation` 确定性逐 key 对比 `validity_conditions`，变化→stale + 注入「⚠️ 已失效」提示 | ✅ |

---

## §7 数字防编造延续（冻结契约）

- Engine（`app/engine/`）、Decision（`app/decision/`）、场景契约、Agent 输出 Schema A1、A2 工具、LLMProvider 协议 **全程零改动**。
- 记忆层本身防编造：`is_safe_fact_value` 拒绝 inferred 含数字的 value；`build_validity_conditions` 复用 `_EVIDENCE_SPECS` 同源取值器；L3 判断直接序列化 `PriorityRef`/`EvidenceRef`（数字带 source），不经过 LLM 二次加工。

---

## §8 一个设计决策说明（供审计）

计划 §2.3 写「db 主表（含 goal）不进 memory_fact」，但 §8 场景 ④「目标变化」要求 goal version 递增检测目标变化。两者存在张力。

**实际落地**：净值事实（income/expense/asset/liability）严格不进 memory_fact；**goal 例外写 memory_fact**（key=`goal:{type}`），理由：目标是「顾问知识」而非「当前净值」，且 db.goal 表无历史版本，无法检测「教育金 50万→30万」的变化，而 memory_fact 的 `version`+`superseded_by` 机制恰好承载此需求。已在 `profile.py` 注释中明确此边界。

---

## §9 V2.5 主动管理能力边界（本次不做）

- 主动发现 / 主动提醒（当前仍是用户提问驱动的被动顾问）
- 长期 Agent / 自动执行动作（`create_action` 已预留）
- 用户偏好学习 / 个性化人格
- inferred 事实的对话推断写入入口（防编造闸已建，推断触发点留 V2.5）
- token 预算超限时的 L1 动态递减（当前固定 5 轮，摘要每轮一行、总量天然受限）

---

## §10 验收结论

| 验收维度 | 结论 |
|---------|------|
| 6 类多轮问题全解决 | ✅（§4） |
| 4 条硬约束不破 | ✅（§6） |
| 数字防编造铁律延续 | ✅（§7，冻结契约零改动） |
| 前端不暴露 Memory/Tool/Decision 内部 | ✅（前端 chat.js 零改动，仍只传 message） |
| 全量测试 | ✅（413 pytest + 12 node + 3 e2e） |

**V2.4 达到验收标准。**
