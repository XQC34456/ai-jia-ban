# V2.5 判断失效（P1 stale）复盘与归档

> 状态：**已收口 / 冻结**（2026-08-14）
> 上一阶段：V2.4 Conversation Memory

---

## §1 结论

**「P1 初始暴露的“保险变化未触发 stale”是真实的测试现象；经逐层验证后确认根因并非 Memory 核心失效机制，而是 evaluator 的 `run_observation` 在真实 `converse` 前提前调用带副作用的 `detect_invalidation`，导致 stale 被提前消费。修复 observer 后，保险与收入两类变化均能独立产生完整 before→after invalidation，obs4 恢复 3.0。」**

> **归档定性：V2.5 evaluator bug** —— 不是 Memory 核心失效，不是产品缺陷。P1 初始判断没有误报，但根因在评测脚本而非产品代码。

---

## §2 因果链（逐层验证）

| 层 | 结论 | 证据 |
|----|------|------|
| 确定性失效检测 | 正常 | 保险→stale、收入→stale 均正确触发，before→after 完整 |
| Memory 注入 | 正常 | `converse` 里 `detect_invalidation` 拿到完整 5 维变化清单 |
| evaluator observer | **bug（根因）** | `run_observation` 在 `converse` 前调用带副作用的 `detect_invalidation`，把判断提前标 stale，导致 `converse` 里因 `status != active` 拿不到失效维度 |
| Advisor reassessment | 模型能力边界（非代码 bug） | 有完整失效维度注入后，advisor 仍未必「复述变化数字」——与「数字防编造」铁律结构性冲突 |

**修复**：`run_eval.py` 的 pre-change 改为只读 diff（`_snapshot_conditions` / `_diff_snapshots`），绝不再在 `converse` 前消费 stale。

**obs4 双维度确认**（真实 DeepSeek）：
- 4A 加收入 → `cashflow_surplus 10000→25000`、`dti 0.3→0.218`、`rfr 1.24→2.24` ✅
- 4B 补保险 → `insurance_count 0→1`、`total_coverage 0→3000000` ✅

---

## §3 验收基线（2026-08-14，真实 DeepSeek）

```text
Tests                 428 passed / 0 failed
Real DeepSeek         PASS
Iron Rules             64 / 64
Advisor avg            2.92 / 3
obs1  remember         3.0
obs2  proactive_gap    3.0
obs3  reevaluate       2.5
obs4  invalidation     3.0
obs5  synthesis        3.0
obs6  overall          3.0
Hard failures          0
```

---

## §4 冻结内容

1. A：structure 失败保留 prose，不丢 tool-loop 成果。
2. B：router 注入 memory context。
3. evaluator：pre-change 改为只读 diff，禁止提前消费 stale。
4. P1：保险维度进入 validity conditions。
5. C：`missing → need_clarification.summary` 数字泄漏修复（`_strip_numeric_text` 闸，TDD 覆盖）。
6. 现有 428 个测试作为回归门槛。
7. 64/64 作为真实 DeepSeek 铁律门槛。
8. 2.92/3 作为当前 Advisor 顾问感基线。

---

## §5 暂不做

- 不继续强化 obs4 prompt。
- 不修改 Engine。
- 不修改 Decision。
- 不修改 Memory 核心 invalidation 机制。
- 不为了 obs3 的 judge 分数做针对性优化（judge 存在波动，与本轮改动无因果）。
- 不为了让 LLM 复述数字而放宽 summary 数字铁律。

---

## §6 固化架构原则

> **确定性层负责事实、数字、来源、状态和失效；LLM 负责理解、推理和表达；评测层不得改变产品状态。**
