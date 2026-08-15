# 内测基线 + 暂缓清单

> 状态：**内测持续中**（2026-08-15，已按 V1.0 对齐）
> 战略主纲：[plan-v10-restructure.md](plan-v10-restructure.md) ｜ 实施路线：[plan-master-roadmap.md](plan-master-roadmap.md)
> 用途：内测阶段「做什么 / 不做什么」的统一口径。**V1.0 已推翻「观察期停手」——主线转入 Phase 1 顾问核心重构；暂缓清单以下表为准。**

---

## §1 内测范围（开放给测试者的能力）

内测开放**已完成并验证冻结**的部分：

| 能力 | 状态 |
|------|------|
| 财富画像建档（onboarding + 冷启动） | ✅ 冻结 |
| 财富概览 / 指标（Wealth Engine） | ✅ 冻结 |
| 风险诊断（Decision Layer 7 类问题 + 四象限） | ✅ 冻结 |
| 财富沙盘 / 场景模拟（Scenario） | ✅ 冻结 |
| AI 顾问（确定性引擎 + LLM 理解/叙事，结论先行） | ✅ 冻结 |
| 判断失效重判（三层记忆 + 确定性 invalidation） | ✅ 冻结 |
| 鉴权 / 多用户隔离 / 密钥安全 | ✅ 冻结 |

---

## §2 内测验收基线

```text
Tests                 539 passed / 0 failed
Node                  12 passed
Real DeepSeek         PASS
Iron Rules             64 / 64
Advisor avg            2.92 / 3
obs1  3.0 · obs2  3.0 · obs3  2.5 · obs4  3.0 · obs5  3.0 · obs6  3.0
Hard failures          0
```

> obs3（纠正后重判）= 2.5 为已知 judge 波动，内测期间**不**为刷分改产品代码。
> 内测期间主线新增为 **V1.0 Phase 1（顾问核心重构）**，验收以主纲 §九 的 9 项质量指标为准，见 [plan-ai-advisor-core-architecture.md](plan-ai-advisor-core-architecture.md) §9。

---

## §3 暂缓清单（V1.0 口径）

### §3.1 产品主线暂缓（主纲 §十三，重写为官方口径）

> 原因（主纲）：如果顾问核心逻辑仍然答非所问，任何新增功能都会把错误主线包装得更漂亮。

| # | 暂缓事项 | 归属 Phase | 触发条件 |
|---|---------|-----------|----------|
| 1 | 大规模 UI 重设计与导航重做 | — | Phase 1-4 验收通过后 |
| 2 | 继续增加大量图表类型 | Phase 6（可视化证据层） | 顾问回答稳定后，图表才作为证据层挂载 |
| 3 | 复杂 Dashboard / 数据看板 | — | 同上 |
| 4 | 新的 Agent 数量扩张 | — | 核心顾问稳定后 |
| 5 | 复杂 VIP 转化玩法 | Phase 7（商业化） | 核心价值稳定后 |
| 6 | 正式 DeepSeek 对标报告 | Phase 8（对标验证） | Phase 1-3 验收通过后，做正式盲测 + rubric |

### §3.2 技术/工程暂缓（沿用，独立于产品主线）

| # | 项目 | 归属 | 暂缓原因 | 触发条件 |
|---|------|------|----------|----------|
| 7 | 主动提醒 Proactive（需调度器） | Phase 5（长期顾问） | 属长期顾问能力，非当前核心 | Phase 1-3 后 |
| 8 | 行动闭环 Action Loop（create_action） | Phase 4（建议与行动） | 依赖 Phase 1 定下 `next_actions` 语义 | Phase 1 后 |
| 9 | 数据治理（health_check→build_issues 统一口径 / 死字段清理） | Phase 2 前置 | 内测不影响正确性，属清理 | Phase 2 前 |
| 10 | 4.1 收尾（下一步按钮化 / 沙盘决策历史） | Phase 1 后 | 依赖 `next_actions` 语义 | Phase 1 后 |
| 11 | 数据安全基线剩余（加密存储 / 最小权限 / 数据导出 / 隐私政策 / 数据出境告知） | 硬门槛 | 除「删除权」本次内测补，其余公网正式版前必做 | 公网开放前 |
| 12 | 正式版基础设施（AI Gateway / 多 Provider / 缓存 / 队列 / 长期记忆 / 主动监控 / 商业化） | 后期 | 内测规模用不上 | 真实用户量起来后 |

> 原 `product-matrix-v26.md` 的「补 6 张图表」计划与 V1.0 冲突，已**归档**至 `docs/archive/product-matrix-v26.md`，不再执行。

---

## §4 内测前必做（三件套，已落地）

| # | 补丁 | 目的 |
|---|------|------|
| A | rate limit（每用户每日对话上限） | 防 DeepSeek 费用失控 |
| B | 删除数据入口（`DELETE /api/account`） | 个保法删除权 |
| C | 内测告知文案（数据会发给 AI 服务） | 数据出境知情 + 降低敏感数据风险 |

---

## §5 命名口径变更

- **旧命名（V2.1→V2.6）已停用**：V2.1 Context / V2.2 Tool / V2.3 Brain / V2.4 Memory 已并入 V1.0 的 Phase 1-3（见 [plan-master-roadmap.md](plan-master-roadmap.md) §5 映射表）；V2.5 Proactive → Phase 5；V2.6 Action Loop → Phase 4。
- 后续阶段号一律使用 **V1.0 的 Phase 0-8**，不再沿用 V2.x 命名，避免撞名。
- 「V2.5 判断失效复盘」是 H 评测护栏的一次评估层诊断（P1 stale → evaluator bug），见 [archive/v25-stale-invalidation-postmortem.md](archive/v25-stale-invalidation-postmortem.md)，不占产品阶段号。
