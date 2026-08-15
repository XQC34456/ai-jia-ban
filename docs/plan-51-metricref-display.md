# 「51分」MetricRef 展示修复 — 工作计划

> 状态：**已确认实施并完成（2026-08-16）**。Phase 1 收口后的唯一独立展示层尾项。
> 依据：设计 [design-advisor-context.md](design-advisor-context.md) §6「展示层裁定」+ 用户 2026-08-15 指令
> （保留 Engine 真值，改变它进入 prose 的方式；极小、边界明确；独立 commit；不碰 Advisor 主链）。

## 1. 任务本质（一句话）

「51 分」**不是数字错了，是数字进入 prose 的方式错了**——数字的真值早已在
`metric.allocation_fitness`（MetricRef 载体，`_issue_metrics` 已把它 surface 成
`issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness`），唯一 bug 是
`_fallback_summary` 把带数字的 finding 内联进了 summary 文案。

## 2. 根因（已代码取证）

真实模式泄漏链：

```
detect.py:174  finding = "配置适配度 {score} 分"        ← 数字（Engine 判断层）
   ↓ _build_priorities（response.py:449 逐字透传）
PriorityRef.finding = "配置适配度 51 分"
   ↓ _fallback_summary（response.py:465）
summary = "当前最需要关注：资产配置适配度偏低（配置适配度 51 分）"  ← 铁律·数字无编造 FAIL
```

- LLM summary 含数字 → `_strip_numeric_text` 剥为空 → `_fallback_summary` 兜底把 finding 内联。
- **确定性 Q10/Q11 不触发**：fake LLM 的 canned summary 无数字，不进 fallback → 基线 iron_ok=True。
- **真实模式触发**：真 LLM summary 常带数字被剥 → fallback 注入 → 铁律 FAIL。

## 3. 关键取证（决定爆炸半径）

| 事实 | 结论 |
|------|------|
| 冻结基线签名**不含 summary/finding 文本**（只记 priorities 的 title + metric_keys + key_numbers + iron_ok） | 改 finding 文本 **不会动基线签名 → 无需重冻结** |
| 数字真值已在 `metric.allocation_fitness`，`_issue_metrics` 已 surface 成 MetricRef | 「数字以 MetricRef 呈现」结构上**已成立**，缺的只是 prose 侧的漏 |
| 前端只渲染 `agent.finding`/`agent.summary`（chat.js:465/509），不渲染 priorities | 「51分」prose 泄漏面**只有 summary 一处** |
| 其余 7 个 detect 的 finding 也内联数字（CASHFLOW/SAVINGS/LIQUIDITY/DEBT/RETIREMENT/GOALS/IDLE_CASH） | **系统性模式**，但 Q4/Q5/Q12 的 CHECK_GOALS 泄漏已在冻结基线记录为 iron_ok=False（已知失败）→ **本刀不扩大** |
| 无任何测试断言 detect_allocation 的 finding 文本（test_decision/v23_priorities 用合成数据） | 改 finding 文本不破测试 |

## 4. 改动（2 文件，全部在「数字进入 prose 的边界」）

### 4.1 `app/decision/detect.py` — `detect_allocation`（只这一条，去数字）

finding 与 reason 改定性，**数字真值仍在 `metric.allocation_fitness`**（已 MetricRef 载体），severity/title/target 不动：

```python
recs = [_rec(_action_text(a), _detail_text(a),
             reason="配置适配度偏低，偏离目标配置",      # 原 f"配置适配度 {score} 分，偏离目标配置"
             target=_target_for(a), scenario="invest")
        for a in alloc["adjustments"][:2]]
if not recs:
    recs = [_rec("调整资产配置", "按目标配置逐步增配低配大类、减配超配大类",
                 reason="配置适配度偏低，偏离目标配置",   # 原 f"配置适配度 {score} 分，偏离目标配置"
                 target={"allocation_fitness": 60}, scenario="invest")]
return {
    "issue_id": "ALLOCATION_LOW_FITNESS_001", "type": "allocation", "severity": sev,
    "title": "资产配置适配度偏低",
    "finding": "当前资产结构偏离目标配置",              # 原 f"配置适配度 {score} 分"；定性+说明 why，不重复 title
    "reason": list(fit["reasons"]) or ["当前配置偏离目标配置"],
    "metric": {"allocation_fitness": score, ...},        # 不动 —— 数字真值
    "target": {"allocation_fitness": "≥ 60"},           # 不动
    ...
}
```

### 4.2 `app/agent/response.py` — `_fallback_summary`（prose 边界硬闸）

finding 含数字 → 不注入（任何 detect 的 finding 即使还带数字，也**永远进不了 summary prose**，系统性兜底）：

```python
if priorities:
    p = priorities[0]
    s = f"当前最需要关注：{p.title}"
    if p.finding and not _DIGIT_RE.search(p.finding):
        s += f"（{p.finding}）"
    return s
return "已生成家庭财务分析，详见下方画像与下一步行动。"
```

`_DIGIT_RE` 已在 response.py:287 定义，零新依赖。

## 5. 测试（先写测试再改，TDD）

新建 `tests/test_metricref_display.py`：

| 用例 | 断言 |
|------|------|
| T-D1 | `_fallback_summary([PriorityRef(finding="配置适配度 51 分", ...)])` → 输出**无任何数字**（守卫回归） |
| T-D2 | 真实 family 跑 `build_issues` → 命中 ALLOCATION_LOW_FITNESS 的 issue → `finding` 无数字，`metric.allocation_fitness` == 真值（Engine 真值保留） |
| T-D3 | 该 issue 构造 PriorityRef → `_fallback_summary` → summary 含 title、无数字（全链路） |

## 6. 验证（做完必须自我验证，不能只声明）

1. `pytest tests/test_metricref_display.py -v` → 3 用例绿。
2. 确定性 12 题基准 → 与冻结基线**签名零 diff**（声明：prose 不在签名内，改文本不动签名）。
3. 全量 `pytest` → 全绿（568+）。
4. 真实 12 题重跑 → **Q10/Q11 summary 不再含「51 分」**，`allocation_fitness=51.0` 只出现在 evidence/metrics（MetricRef 卡片）。
5. 独立 commit，不动其它文件。

## 7. 明确不做的（边界声明）

- **不动其它 7 个 detect 的 finding**（系统性模式记录为后续独立任务；Q4/Q5/Q12 是冻结基线已知失败）。
- **不 surface `allocation_fitness` 进 `_allocation_metrics`**（那会改 Q10 的 metric_keys/key_numbers → 需重冻结，超出「极小」）。
- **不碰**：Engine、Decision 阈值/severity、契约 schema、Advisor 主链、前端、冻结基线签名。
- **不改铁律**：`assert_no_fabrication` 数字检测保持（它是对的，错的是 prose 泄漏）。

## 8. 产出

- 变更 + 测试 + 验证报告（真实 Q10/Q11 的「51分」现在如何以 evidence 呈现）。
- 收口后：给 Phase 1 打正式 tag。
