# Plan D — AI Advisor V2（主体计划）

> 唯一主体计划。**AI 顾问 = 产品主入口、决策中枢；其余所有模块（Engine / Decision / Cockpit / X-Ray / Sandbox / Data / Goals / Reports / Reminders）都是顾问的能力底座和行动工具。**
> 依据 [advisor-architecture-audit.md](advisor-architecture-audit.md) + [plan-master-roadmap.md](plan-master-roadmap.md) §4。
> V2.1→V2.6 每阶段的**分阶段 plan 挂在本文之下**，不再散落独立文件。

---

## 0. 定位（一句话）

> **「一个长期理解这个家庭，并帮助这个家庭做财富决策的 AI 操作系统。」**

不是「一个能回答财富问题的 AI 聊天窗」。核心反转：**不是「页面调用 AI」，而是「AI 顾问调用整个财富系统」。**

---

## 1. 北极星漏斗（V2 升级）

以前「画像 → 首次对话」只衡量「到达」，不衡量「价值」。V2 换成**决策漏斗**：

```
首次理解率 → 有效对话率 → 决策模拟率 → 方案采纳率 → 行动完成率 → 长期留存
```

- **北极星**：有效对话率（AI 真的理解用户，而非答非所问）→ 决策模拟率（用户愿意让 AI 跑方案）。
- **价值发生**：方案采纳率 + 行动完成率（用户因为顾问做出了一个更好的决策）。
- **辅助**：建档完成率、7 日留存。
- 每一层都能归因到具体阶段（见 §10），否则不做。

---

## 2. 冻结边界（任何阶段不得触碰）

| 冻结项 | 位置 | 理由 |
|--------|------|------|
| Engine（财富计算） | app/engine/、app/services/ `build_overview` / `compare_scenarios` | 数字唯一真相源 |
| Decision（问题检测） | app/decision/ `build_issues` | 判断唯一真相源 |
| 场景契约 C3.5 | app/schemas/scenario.py | 新增场景必须改这里 + contract test 逼同步 |
| Agent 输出 Schema A1 | app/schemas/agent.py `AgentResponse` / `MetricRef` | 防编造硬闸，只扩不减 |
| A2 工具只读 + VIP 门 | app/agent/tools.py | 工具 = 获取事实，绝不计算 |

---

## 3. 顾问的 7 个核心能力

| # | 能力 | 落点 |
|---|------|------|
| ① 家庭财富记忆 | 知道「我是谁/资产/负债/目标/风险偏好/历史决策」，形成 Wealth Context | V2.1 + V2.4 |
| ② 主动理解（不等人问） | 「钱没怎么涨」→ 诊断资产结构，而非灌投资鸡汤 | V2.3 |
| ③ 主动追问 | 信息不足不硬答，追问最少必要信息 | V2.3 |
| ④ 自动调用工具 | DeepSeek 拥有 10 个工具，不自答 | V2.2 |
| ⑤ 做决策不做计算 | 「300 万还贷？」→ 调 scenario，数字全来自 Engine | V2.2 + V2.3 |
| ⑥ 解释数字（不甩 RFR=0.43） | 翻译成「退休准备偏紧，房产占比高、金融资产不足」 | V2.3 |
| ⑦ 推动行动 | 建议 → 方案 → 模拟 → 用户选 → 行动 | V2.6 |

---

## 4. 顾问记忆：Wealth Context 五块

| Context | 内容 | 来源 |
|---------|------|------|
| Family Context | 成员/年龄/收入/支出/资产/负债/保险 | Family Data |
| Financial Context | 财富全景/现金流/配置/养老 | Engine 输出 |
| Decision Context | 当前问题/风险（P0→P2） | Decision Layer |
| Goal Context | 退休/买房/教育/传承目标 | Goal Engine |
| Conversation Context | 历史对话 + 决策历史 + 偏好（L4） | **Advisor Memory（新增）** |

> 前四块是既有数据，V2.1 负责「组装成 LLM 可读 context」；Conversation Context 是 V2.4 的新增。

---

## 5. Advisor Tools（10 个，标注已有/新增）

| # | Tool | 底层能力 | 状态 |
|---|------|----------|------|
| 1 | `get_family_profile` | `db.dump_family` | 已有，需暴露 |
| 2 | `get_wealth_overview` | `build_overview` | 已有（现 `get_overview`） |
| 3 | `get_wealth_issues` | `build_issues` | 已有（现 `get_issues`） |
| 4 | `get_cashflow` | `overview.cashflow` | 已有，读子字段 |
| 5 | `get_allocation` | `overview.asset_allocation` | 已有，读子字段 |
| 6 | `get_retirement` | `overview.retirement` | 已有，读子字段 |
| 7 | `get_goals` | `build_goals` | 已有（现 `get_goals`） |
| 8 | `run_scenario` | `compare_scenarios` 单方案 | 已有（现 `compare_scenario`） |
| 9 | `compare_scenarios` | `compare_scenarios` 多方案 | 已有 |
| 10 | `create_action` | Goals/Reminders 写入 | **新增，受 P3 约束** |

> 10 个里 9 个是「已有能力 + 暴露成 tool」，只有 `create_action` 新增，且必须走「确认卡片」（复用 `profile._PENDING`），满足 P3「确认前不写库」。

---

## 6. Advisor Policy（Tool Calling 不能乱）

| 用户表述 | 规则 |
|----------|------|
| 问数字（「财富评分多少」） | **必须调 Engine**，不自己报数 |
| 「我该不该 / 要不要」 | 先读家庭 → 读风险 → 必要时 Scenario |
| 信息不足 | **不猜，追问最少必要信息** |
| 纯知识（「什么是复利」） | 直接答，不调 Engine |

---

## 7. 决策循环六步 SOP（V2 核心，每次重要对话都走）

```
Understand  我理解你想做什么
   ↓
Diagnose    我看了一下你的家庭情况
   ↓
Explain     真正的问题是什么（不甩 RFR/NWC）
   ↓
Simulate    如果这么做，会发生什么（调 Engine）
   ↓
Recommend   我更倾向哪种方向，以及为什么
   ↓
Act         下一步可以做什么（按钮 / 行动）
```

---

## 8. AI 顾问状态机（V2.3 核心）

不是 `messages → DeepSeek → response`，而是三分支：

```
             用户消息
                ↓
         Intent Classifier
                ↓
  ┌─────────────┼─────────────┐
  ↓             ↓             ↓
闲聊咨询      财富问题      重大决策
  ↓             ↓             ↓
直接回答     读取 Context    深度分析
(不调Engine)     ↓          调用 Scenario
             判断缺失信息        ↓
                ↓           Engine 重算
              追问              ↓
                ↓          比较方案
              分析 ←──────────┘
                ↓
            解释结果
                ↓
             给下一步
```

- **闲聊咨询**（「什么是复利」）：直接答，不调 Engine。
- **财富问题**（「我财富评分多少」）：读 Context → 缺信息则追问 → 给答案。
- **重大决策**（「该不该买房」）：读 Context → 调 Scenario → Engine 重算 → 比较 → 解释。

---

## 9. 顾问人格与回复结构

**人格**：专业 + 克制 + 直接 + 有温度。
- 不说「根据相关数据显示」→ 说「我看了一下你的家庭情况」。
- 不说「您应该」→ 说「如果是我站在你这个家庭的位置」。
- 必须允许说「这个问题我现在不能直接判断」，然后说明缺什么——这反而提高可信度。

**固定回复骨架**（不自由发挥）：

```
结论 → 为什么 → 我看到的情况(数字+source) → 如果这样做 → 更值得比较(A/B/C) → [帮我比较]按钮
```

**回答长度分级**：数字查询短答 + 追问钩子；决策问题深度答；情绪表达（「压力很大」）先共情再诊断。

---

## 10. 阶段 V2.1 → V2.6

| 阶段 | 目标 | 关键产出 | 归因漏斗 | 冻结风险 |
|------|------|----------|----------|----------|
| **V2.1 Context Engine** | 让 AI 看见家庭 | 组装五块 Context 注入 provider | 首次理解率 | 低 |
| **V2.2 Tool Calling** | 给 DeepSeek 工具 | 10 个只读 tool + function-calling | 有效对话率 | 中 |
| **V2.3 Advisor Brain** | 决策脑 | 状态机 + 六步 SOP + 修复 EXPLAIN_RESULT 死分支 | 有效对话率 | 低 |
| **V2.4 Conversation Memory** | 长期记忆 | 对话历史 + 决策历史 + L4 偏好 | 长期留存 | 中 |
| **V2.5 Proactive Advisor** | 主动顾问 | 登录即提醒现金/目标变化（需调度器） | 长期留存 | 中 |
| **V2.6 Action Loop** | 行动闭环 | `create_action` 形成计划/提醒/复盘 | 方案采纳率+行动完成率 | 中 |

> **H（Evaluation）不是阶段，是贯穿 V2.1→V2.6 的护栏**：30~50 条黄金场景（含「为什么养老有问题→多存5000→不想多存」多轮链），每条断言「意图正确 + 数字正确 + source 正确 + 无编造」。
>
> V2.5 需要调度器（当前单进程 uvicorn 无），归为后期能力，不塞进早期。

---

## 11. 分支如何接入主线（完善产品 + 服务用户）

| 分支 | 接入点 |
|------|--------|
| 4.1 展示层（已完成） | V2.3 的前端骨架，不重做 |
| 4.1 收尾（下一步按钮 / 决策历史） | 待 V2.3/V2.4 定下 `next_actions` 语义后并入 |
| 冷启动（已完成） | 服务 V2.1，新用户 60 秒进入首次对话 |
| 数据治理 | V2.1 之前做，保证 LLM 看到干净数据 |
| 沙盘（已冻结） | V2.2/V2.6 的「模拟」能力底座，不再是独立主角 |

> Cockpit / X-Ray / Sandbox 全部降级为「顾问的眼睛、计算器、实验室」——顾问说「退休资金不足」→ 用户点「看看退休情况」→ Cockpit 打开对应面板。

---

## 12. 执行纪律

1. **先 TDD 再实现**：每阶段先写验收测试（B2 极限 + H 评测），红了再写代码。
2. **一阶段一 commit**：全量回归通过才进下一阶段。
3. **冻结契约零触碰**：需改 Engine/Decision/Schema 就停下报上来。
4. **两错加规则**：同一错误犯 2 次，回写 CLAUDE.md 红线或 gotchas。

---

## 13. 启动顺序

```
数据治理（轻） → V2.1(Context) → V2.2(Tool) → V2.3(Brain) → V2.4(Memory) → V2.6(Action) → V2.5(Proactive·后期)
                                                                    H 评测从 V2.1 起累积，贯穿全程
```

> 首阶段 **V2.1（Context Engine）**：风险最低、收益最直观，做完用户立刻感到「顾问懂我家」，且是 V2.2/V2.3 的地基。
