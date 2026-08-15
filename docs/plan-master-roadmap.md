# AI家办 · 主开发路线图（Master Roadmap）

> 本文件是**唯一的主计划总纲**。**主体 = AI 顾问（Plan D），即整个产品的操作系统入口。**
> 所有功能（Engine / Decision / Cockpit / X-Ray / Sandbox / Data / Goals / Reports / Reminders）一律**服务顾问**，冲突时以本文件为准。
>
> 定位：**家庭财富决策操作系统 —— AI 顾问是主入口与决策中枢，不是聊天窗口。**

---

## 0. 核心原则（铁律，任何阶段不得违反）

| # | 原则 |
|---|---|
| P1 | 财富数字一律由 Wealth Engine / Decision 计算，LLM 绝不计算、绝不编造 |
| P2 | 四者绝不越权：Engine 计算 / Agent 组织 / LLM 语言 / UI 呈现 |
| P3 | 确认之前绝不写数据库 |
| P4 | 所有数字可追溯到 Wealth Engine（`MetricRef.source` 硬门禁） |
| P5 | 一个阶段一个边界，不做「顺手改别的」 |

---

## 1. 目标用户（已钉死）

**主 persona：30–45 岁双职工家庭**

- 有房贷 + 孩子，买房 / 教育 / 养老三线并行
- 有真实决策压力，但没预算请真人理财师
- 有财务焦虑、没时间学 → 需要「敢用、看懂、信、行动」

**心理画像（为什么留下）**：*「我不缺赚钱能力，但越来越不知道重大资金决策该怎么做。」*

> AI家办要解决的不是「算不清账」，而是「决策焦虑 + 无人可问」。见 [spec-ux-humanization.md](spec-ux-humanization.md)。

---

## 2. 北极星指标（Plan D 升级）

**北极星：**「**一次有效财富决策完成率**」= 用户提出真实财富问题 → AI 理解 → 必要时追问 → 调用正确数据/模型 → 给出有依据的方案 → 用户完成一次决策的比例。

- 聊天不是价值，**决策才是**。这是 AI 顾问作为「决策中枢」的唯一验收。

**aha moment（前置转化）：**「画像 → 首次 AI 对话」= 新用户 7 日内完成财富画像并触发 ≥1 次顾问对话。

- 保留它衡量 onboarding 是否成功，但它只是「到达」，不是「产生价值」。

**辅助指标**：建档完成率（测铁律⑦）、沙盘周使用次数（测铁律⑤）、7 日留存。

---

## 3. 当前基线（已冻结，勿再大改）

| 阶段 | 内容 | 状态 |
|---|---|---|
| C3 / C3.5 | 财富沙盘 + 场景契约冻结 | ✅ |
| A1 → A4 | Agent Contract / Tool / Runtime / API | ✅ |
| C5 | 统一 App Shell（8 视图） | ✅ |
| C6 | AI 顾问统一收口（建档吸收 + 七意图 + 确定性产出） | ✅ 冻结 `f227c95` |
| 4.1 展示层 | 体检横幅 / 为什么 / 下一步按钮 / 沙盘模式提示 / 冷启动向导 | ✅ 5 commit |
| **P1 联动** | Advisor×Engine×Chart×Action：确定性基线 → 情景证据图 → 结构化追问 → 建议采纳闭环 | ✅ 516 pytest |
| **P2 内测** | 埋点（8 类事件）→ P2-A 价值前置（Free→VIP 先基础判断再边界） | ✅ 539 pytest |

- 测试：**pytest 539 passed · node 12 passed**
- **冻结契约**：A1–A4、Wealth Engine、Decision、API Schema、Agent Runtime —— 后续阶段一律不修改。
- **内测基线 + 暂缓清单**：见 [internal-beta-baseline.md](internal-beta-baseline.md)（内测阶段口径）。

> **底层已足够支撑真正的 AI Advisor。下一阶段不再堆页面，只做「大脑」（Plan D）。**

---

## 4. 主体：Plan D — AI Wealth Advisor Core（唯一主线）

> **审计结论（见 [archive/advisor-architecture-audit.md](archive/advisor-architecture-audit.md)）**：当前 AI 顾问是 Level 0，
> 骨架全对，缺「理解 / 上下文 / 记忆 / 对话」四个引擎。这不是文案问题，是最高优先级的产品问题。

**主体定位**：AI 顾问 = 主产品。其余全是顾问的器官——

| 器官 | 角色 |
|------|------|
| Wealth Engine | 顾问的「计算大脑」 |
| Decision Layer | 顾问的「风险判断系统」 |
| Cockpit / X-Ray / Sandbox | 顾问的「可视化工具」 |
| Family Data | 顾问的「家庭档案」 |
| Goals / Reports / Reminders | 顾问推动用户行动的「执行系统」 |

**核心铁律延续**：LLM 可以生成文字、组织上下文、决定查什么，但**数字永远来自 Engine 返回 + `MetricRef.source` 硬闸**。

分 6 个阶段（V2.1→V2.6），每阶段独立验收，全程不碰 Engine/Decision 冻结契约：

| 阶段 | 目标 | 服务用户 | 前置 | 状态 |
|------|------|----------|------|------|
| **V2.1** Context Engine | 组装五块 Wealth Context 注入 provider | 回答「针对你家」 | 审计（D0） | ✅ |
| **V2.2** Tool Calling | 10 个只读 tool + function-calling | 会调用而非背诵 | V2.1 | ✅ |
| **V2.3** Advisor Brain | 状态机 + 六步 SOP + 修复 EXPLAIN_RESULT 死分支 | 顾问感 + 有效对话 | V2.1+V2.2 | ✅ |
| **V2.4** Conversation Memory | 对话历史 + 决策历史 + L4 偏好 | 追问不失忆 | V2.3 | ✅ |
| **V2.5** Proactive Advisor | 登录即主动提醒（需调度器） | 主动陪伴 | V2.4 | 📦 暂缓 |
| **V2.6** Action Loop | `create_action` 形成计划/提醒/复盘 | 推动行动 | V2.4 | 📦 暂缓 |

> **H（Evaluation）不是阶段，是贯穿 V2.1→V2.6 的护栏**：30~50 条黄金场景，保证改提示词不破坏财富正确性。

---

## 5. 分支：服务顾问的四类（认清分支）

> 每个分支必须回答「服务顾问哪个阶段」，否则不做。

| 分支 | 状态 | 服务顾问哪一阶段 |
|------|------|-----------------|
| **4.1 人性化（展示层）** | ✅ 已完成 5 commit | 服务 **V2.3**（Advisor Brain 的前端骨架） |
| **4.1 收尾**（下一步按钮化 / 沙盘决策历史） | ⏸ 暂停 | 等 **V2.3/V2.4** 定下 `next_actions` 语义后再做，避免返工 |
| **冷启动** | ✅ 已完成 | 服务 **V2.1**（新用户 60 秒内进入首次对话，喂饱上下文） |
| **数据治理**（health_check→build_issues 统一口径 / 死字段清理） | 📦 暂缓 | 服务 **V2.1**（让 LLM 看到干净、一致的数据） |
| **沙盘** | ✅ 冻结 | 是顾问的**能力底座**，V2.2/V2.6 调用它完成「模拟」 |

---

## 6. 测试闸门：B1 / B2

- **B1 手工体验**：7 类意图逐条验证。
- **B2 极限测试**：错误参数 / 缺失参数 / 不存在场景 / 免费调 VIP / LLM 返回错误 JSON / 超时 / 并发……
  - AI 可以笨、可以拒绝、可以让用户补充信息，**但绝不能编造财富数字**。

---

## 7. 数据安全基线（测试版之前，必做）

- 加密存储 + 最小权限 + 数据导出 / 隐私政策 / 数据出境告知（个保法）→ 📦 暂缓（公网开放前必做）。
- 删除权 → 内测三件套补丁中落地，见 [internal-beta-baseline.md](internal-beta-baseline.md) §4。
- 密钥安全：`LLM_API_KEY` 不落前端、不入库、不随响应回传 → ✅ 已完成。

---

## 8. 测试版 MVP → 真实用户

- 以「北极星指标 + 辅助指标」为验收标准，不是「感觉」。
- 真实用户 → 问题收集 → **归因到指标再改**。

---

## 9. 正式版基础设施（后期）

AI Gateway → 多 Provider → 缓存/限流/队列 → 数据库 → 长期记忆 → 主动风险监控 → 商业化。

> 你的服务器承担「AI 调度和产品逻辑」，模型算力交给模型厂商。扩的是 API/Provider/Queue/Cache/DB，不重写 Agent。

---

## 10. 路线图总览

```text
【已冻结】 C3 → A1 → A2 → A3.1 → A3.2 → A4 → C5 → C6 → 4.1 展示层
【主体】   Plan D = AI Advisor V2：V2.1(上下文) → V2.2(工具) → V2.3(大脑) → V2.4(记忆) → V2.5(主动) → V2.6(行动)
【P1 联动】 Advisor×Engine×Chart×Action：确定性基线 → 情景证据图 → 结构化追问 → 建议采纳闭环 ✅
【P2 内测】 观察期：埋点 ✅ → P2-A 价值前置 ✅ → 观察 2~4 周 → P2-B 对标 → P2-C UI 复盘
【后续】   C3 Wealth Sandbox → V2.5 主动提醒 → V2.6 行动闭环 → 正式版基础设施
【护栏】   H 评测贯穿始终
【闸门】   B1/B2 → 数据安全基线
【测试版】 MVP → 真实用户 → 指标验收
【正式版】 基础设施 → 商业化
```

---

## 11. 后续更新计划（当前排队）

> 内测观察期：先让埋点跑 2~4 周，用真实用户行为决定下一步，不堆功能。

| 顺序 | 计划 | 目标 | 触发条件 |
|------|------|------|----------|
| 1 | **P2-B** 对标 DeepSeek/豆包 | 固定 prompt + rubric 真实跑，落点「谁能给出可追溯数字」 | 埋点跑 2~4 周后有真实数据 |
| 2 | **P2-C** UI 信息架构复盘 | 每个页面「数据→判断→图表→行动」闭环 | P2-B 之后 |
| 3 | **C3** Wealth Sandbox | 情景沙盘能力底座 | P2 收口后 |
| 4 | **V2.5** Proactive Advisor | 登录即主动提醒（需调度器） | 留存数据支撑 |
| 5 | **V2.6** Action Loop | create_action 计划/提醒/复盘 | V2.5 之后 |
| 6 | 正式版基础设施 | AI Gateway / 多 Provider / 缓存限流 / 商业化 | 测试版验证后 |

---

## 文档结构（唯一主体 + 少数分支）

| 文档 | 角色 |
|------|------|
| `plan-master-roadmap.md`（本文件） | **唯一总纲** |
| `plan-ai-advisor-core-architecture.md` | **唯一主体计划**（Plan D，D0→D5 展开） |
| `archive/advisor-architecture-audit.md` | 审计输入（Level 0 → 5 依据，D0 成果） |
| `spec-ux-humanization.md` | 人性化规范（分支 D3 的验收依据） |
| `api-contract-v1.md` | 冻结契约参考 |
| `testing-guide.md` | 测试入口 |
| `docs/archive/` | 已完成的历史计划（25 个） |
