# P0 修复计划：structure 失败不整体降级 + router 注入记忆

> 2026-08-14 · 真实 DeepSeek 顾问评测暴露（V2.4 基线：铁律 64/64 + 顾问感 2.92/3）。

## 背景

obs1 第2轮「那这笔钱你建议我怎么安排更稳妥？」答非所问（「需要补充以下信息：场景
（买房 / 提前还贷 / 投资 / 收入变化）」），judge continuity 2 分。根因三层：

1. **路由无记忆**：`route_intent` 签名无 `memory_context`，指代「这笔钱」无法消解 →
   误路由 `SCENARIO_COMPARE`。
2. **结构失败整体降级（核心）**：`_structure_advisor_answer` 偶发失败（DeepSeek 在
   `response_format=json_object` 下偶发返回非 JSON → `complete_json` 返回 None）→
   `advise()` 直接 `return None` → tool_loop 已产出的散文 + 工具结果全部丢弃。
3. **兜底追问宽泛**：降级到 `extract_scenario_params`，场景未识别 → 返回
   `_SCENARIO_HINT` 宽泛追问。

## 修复方案

### A（核心）：structure 失败用散文兜底

只改 `app/agent/advisor.py` 的 `advise()`（约 213-215 行）：

```python
llm_json = _structure_advisor_answer(llm, raw.get("content"), message)
if llm_json is None:
    prose = raw.get("content")
    if not prose:
        return None
    llm_json = {"summary": prose}
```

**边界（铁律）**：prose 只是「回答可用性兜底」，非确定性事实来源——
`metrics` / `priorities` / `evidence` 仍从 `tool_results` 确定性取，数字仍由
`_strip_numeric_text` 处理，`source` / `status` 绝不从 prose 猜。核心价值是
「structure 失败 ≠ 整个 advisor 失败」。

### B（顾问感）：router 注入 memory_context

改 `app/agent/router.py` 的 `route_intent`（加 `memory_context` 参数，拼进 user 消息）
+ `app/agent/runtime.py` 透传。`build_memory_context` 本身不动。

## 边界约束

- Engine / Decision / Memory 三层完全不改。
- rubric 不改；64/64 + 2.92/3 作基线，修复后直接对比。
- P1 stale（保险不进 validity_conditions）暂不动，保持实验可归因性。

## TDD 顺序

A 红 → 绿 → `pytest -q` → B 红 → 绿 → `pytest -q` → 真实 DeepSeek 重跑 → 对比基线 →
再定 C（兜底文案）与 P1 stale。

## 验收

- obs1 不再降级为「场景（…）」，回答围绕「给父母留养老钱 → 这笔钱」。
- `complete_json#2` 偶发 FAIL 不再导致整轮 advisor 链路降级。
- 铁律 64/64 无回归。
- obs1 continuity 2 → 3。
