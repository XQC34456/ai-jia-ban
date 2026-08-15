# Phase 2 第二刀「字段冲突收尾（identity/name 守卫）」工作计划

> 状态：**待用户确认（2026-08-16）**。Phase 2 第二刀，紧接第一刀（commit 1d86aa7）之后。
> 用户已确认：第二刀 = **字段冲突收尾**；来源追踪顺延第三刀（最小粒度边界见 §7）。
> 依据：用户 2026-08-16 拆词（增量建档 / 字段冲突 / 来源追踪）→ 取证 → AskUserQuestion 确认。

---

## 0. 这一刀的本质（一句话）

**第一刀冲突覆盖把整个 `a["fields"]` 传给 `update_entity`，导致 `name` 这类「身份锚/展示字段」被一并改写（「现金」→「存款」）；第二刀把覆盖收窄到值字段，明确「哪些覆盖、哪些保留」，实现用户对字段冲突的定义——避免整行替换。**

## 1. 现状取证（实证）

| 事实 | 结论 |
|------|------|
| `apply_confirmation`（profile.py:297）conflict 分支 `db.update_entity(rc.table, rc.matched_id, a["fields"])` | **传整个动作字段**，含 identity 与 name |
| 实证脚本：档案 `{type:存款, name:现金, value:500000}`，用户「存款30万」→ 确认后 `{name:存款, value:300000}` | **name 被误改写**（现金→存款），value 更新正确 |
| `_RECONCILE_SPEC` 每 kind 已有 `value` 字段元组 | 覆盖范围已有定义，只是没被冲突分支使用 |
| `update_entity` 只更新非 None 字段 + `_coerce_entity` 按 ENTITY_COLS 白名单收窄 | 传入只含值字段即天然保留 name/identity |
| R1–R7 测试（income 冲突只断言 amount、R5 只断言 type 判身份） | 现有测试**未覆盖** name 守卫场景 → 行为兼容 |

## 2. 设计（最小改动）

**`apply_confirmation` 冲突分支：只传值字段子集，不传 identity/name。**

```python
if rc.status == "conflict":
    if rc.matched_id is not None and rc.table:
        # 冲突覆盖只更新值字段；identity 与 name 等身份锚字段永不覆盖
        spec = _RECONCILE_SPEC.get(a["kind"])
        value_fields = {c: a["fields"][c] for c in (spec["value"] if spec else ())
                        if c in a["fields"]}
        db.update_entity(rc.table, rc.matched_id, value_fields)
        ...
```

行为矩阵（语义不变处 + 修正处）：

| 场景 | 改前 | 改后 |
|------|------|------|
| income 冲突（amount 变） | category/period/amount 全传 → identity 同值无感，amount 更新 | 只传 amount → 同结果 |
| asset 冲突（value 变） | type/name/value 全传 → **name 被改写**（bug） | 只传 value → **name 保留**（修正） |
| liability 冲突（月供变，principal 未提及） | type/name/monthly_payment 传 → name 被改写 | 只传 monthly_payment → principal 保留、name 保留 |
| goal 冲突 | type/name/target_amount/current_saved 传 → name 被改写 | 只传提及的 value 字段 → name 保留 |
| exists / new / 歧义分支 | 不涉及 | 不涉及（不动） |

## 3. 代码落点

- **Modify `app/agent/profile.py`**：`apply_confirmation` 冲突单匹配分支，把 `a["fields"]` 换成值字段子集（约 3 行）。
- **New `tests/test_filing_reconcile.py` 追加 2 个用例**（R8/R9）。
- 其余零改动：`app/db.py` / 前端 / schema / Advisor 主链 / entry.py / 冻结基线。

## 4. 测试（TDD，先红后绿）

| 用例 | 场景 | 断言 |
|------|------|------|
| **R8 asset name 守卫** | 档案 `{type:存款, name:现金, value:500000}`，用户「存款30万」 | conflict 单匹配；确认后 name=现金 **保留**、value=300000（只更新值字段） |
| **R9 liability 部分值覆盖** | 档案 `{type:房贷, name:房贷, principal:2000000, monthly_payment:8000}`，用户「房贷月供9000」（只提及月供） | conflict 单匹配；确认后 monthly_payment=9000、**principal=2000000 保留**、name=房贷 保留 |

**已有测试影响**：R3（income 只传 amount → 行为不变）、R5/R6/R7（exists/歧义路径不动）全保持绿。

## 5. 验证（做完必须自我验证）

1. `pytest tests/test_filing_reconcile.py -v` → R1–R9 全绿。
2. 确定性 12 题基准 → 与冻结基线 **零 diff**（confirm 卡与写库路径对 Q10 无影响：值字段子集 = 原 amount 更新，name 不在 Q10 冲突里）。
3. 全量 `pytest` → 全绿（579+）。
4. 独立 commit（只动 profile.py + test_filing_reconcile.py + 本计划文档）。

## 6. 不做什么（边界声明）

- 不碰 schema / 前端 / Advisor 主链 / Engine / Decision / 铁律 / 冻结基线。
- 不改 exists/new/歧义分支语义；不做多匹配选择器；不做字段级对话澄清。
- 不顺手修 Q2 G1 建档 gate 误判（独立问题，已明确不修）。
- 来源追踪**不在本刀**（第三刀候选，边界见下）。

## 7. 第三刀「来源追踪」预钉边界（顺延，不在本刀实现）

最小粒度（满足「为什么这个数字现在是这样」）：确认时逐条记 `product_event`（`record_event`，复用现有 meta JSON 列，**零 schema 变更**），event_type=`filing_provenance`，meta=`{status, summary, matched_id}`。**明确不做**：新增表 / 档案行级 source 列 / 完整 provenance / 审计历史 / 非 goal 实体版本化 / memory_fact 泛化。

## 8. 风险与已知限制

| 限制 | 说明 |
|------|------|
| 值字段若动作中未提及 | 如 liability 动作只含 monthly_payment → principal 不传 → 保留。这与「用户没说就不动」一致，属正确语义 |
| identity 字段值在动作中与档案不同 | 匹配要求 identity 全同才进 conflict，冲突发生时 identity 必同值 → 不传也无损失 |
| goal conflict 仍走 `_record_goal_fact` 完整写 | 表写值字段 + memory_fact 版本化历史，V2.4 契约保持 |
