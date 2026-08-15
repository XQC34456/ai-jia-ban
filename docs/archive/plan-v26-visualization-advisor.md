# V2.6 · 可视化解释层 + IA 调整 + 顾问结构化 实施计划

> **Goal:** 把产品从「套金融 Prompt 的聊天机器人」升级为「AI 家庭财务驾驶舱」——顾问是大脑、页面是仪表盘、Engine 是计算器官。
> **铁律:** 数字一律确定性计算（Engine/Decision 已算好），前端只读+渲染，LLM 只做理解/推理/表达。

**参考矩阵:** [product-matrix-v26.md](product-matrix-v26.md)（页面×指标×图表×问题×顾问入口×行动入口 + 缺口清单）

**Tech Stack:** ECharts 5 (CDN, 无构建) · Vue 3 (CDN, 现有) · 后端零 Engine 计算改动。

---

## 已锁定的信息架构（用户已确认）

- **`health` = 7 维财富健康全景**：雷达图 + 现金流/流动性/负债/保障/配置/养老/目标 各维下钻，薄弱维高亮。
- **`allocation` = 资产配置诊断**：承接现有 health.js 的「配置体检」内容 + 环形图 + 当前vs目标 + 调仓模拟。
- **现金流/负债/保障 不单独建 nav 页**，作为 health 的下钻区块。
- **导航保持 9 项不变。**

> ⚠️ 两套「7 维」严格区分：雷达图用**健康 7 维**（score.py WEIGHTS，含 protection）；风险地图用**检测 7 类型**（detect.py，含 decision/闲置资金）。不串用。

---

## 全局约束

1. 数字一律确定性计算，前端不新增任何财富计算。
2. 不为加图而加图——每张图回答一个明确财务问题；顾问回答中图表由用户问题触发。
3. 不碰 Engine 核心逻辑；唯一后端改动是「暴露已算好的 `dimensions`」。
4. 每步完成后自我验证（跑测试 + 浏览器截图审查）。
5. 图表写成可复用证据块组件，dashboard 与顾问共用，避免两份实现。

---

## 6 个证据块（图表组件）定义

| # | 组件名 | 回答的财务问题 | 数据源（已存在） | 类型 | 归位（新 IA） |
|---|--------|--------------|----------------|------|-------------|
| ① | `HealthRadar` | 我家整体健不健康？哪维最弱？ | `overview.dimensions`（7维0-100+weight） | 雷达图 | `health` 顶部 |
| ② | `CashflowChart` | 钱去哪了？每月存多少？ | `overview.cashflow` | 瀑布图 | `health` 现金流下钻 |
| ③ | `AllocationDonut` | 钱放哪？配置合理吗？ | `overview.asset_allocation.classes` | 环形图 | `allocation` |
| ④ | `DebtGauge` | 债务危险吗？ | `overview.debt`{dti} | 仪表盘 | `health` 负债下钻 |
| ⑤ | `ProtectionGap` | 保障够不够？ | `overview.protection`{coverage_ratio} | 缺口对比条形 | `health` 保障下钻 |
| ⑥ | `GoalProgress` | 哪个目标落后？ | `overview.goals` | 横向进度条组 | `goals` |

---

## 任务分解

### Phase 1 · 地基（可视化解释层立起来）

**Task 1.1 — 后端暴露 dimensions（1 行 + 测试）**
- 文件：`app/services/overview.py`（`"wealth_score": ws["score"]` 处补 `"dimensions": ws["dimensions"]`）；`tests/test_services_overview.py`
- 验证：新增测试断言 `overview["dimensions"]` 含 7 项且含 `protection`；`pytest` 全绿。

**Task 1.2 — 引入 ECharts + 证据块组件工厂**
- 文件：`static/index.html`（加 ECharts CDN `<script>`）；新建 `static/charts.js`
- 内容：`charts.js` 导出 6 个 Vue 组件，`<div ref>` + onMounted 初始化 ECharts + watch 数据重渲染 + resize/dispose 生命周期 + 统一色板对齐 `CLASS_COLORS` + 空数据态。
- 验证：`node --check static/charts.js`；页面无 ECharts 未定义报错。

### Phase 2 · IA 调整 + 图表归位

**Task 2.1 — `health` 重构为 7 维健康雷达页**
- 文件：`static/views/health.js`
- 内容：顶部 `HealthRadar`；下方 现金流/负债/保障 三个下钻区块（`CashflowChart`/`DebtGauge`/`ProtectionGap` + 各自 key numbers + 薄弱维高亮 + 「问顾问」「加入计划」入口）；其余维度（流动性/配置/养老/目标）用评分条展示并链到对应页。
- 验证：截图审查雷达图 + 下钻区块。

**Task 2.2 — `allocation` 承接配置诊断**
- 文件：`static/views/allocation.js`
- 内容：`AllocationDonut` + 把现有 health.js 的「配置体检 7 段」（当前配置/个性化目标/当前vs目标/偏离/集中度/流动性/调仓动作）迁入；health.js 删除这 7 段。
- 验证：`node --check`；截图审查；确认 health 不再含配置体检内容。

**Task 2.3 — `goals`/`retirement`/`overview` 接入图表**
- 文件：`static/views/goals.js`（`GoalProgress`）、`static/views/retirement.js`（退休缺口对比）、`static/views/overview.js`（可选：健康雷达小图）
- 验证：截图审查三个视图。

### Phase 3 · 顾问 5 层结构化（Phase 1+2 验证通过后）

**Task 3.1 — chat 5 层骨架 + 按问题触发证据块**
- 文件：`static/views/chat.js`
- 内容：回答渲染为 ①结论→②关键变化→③财务画像(1~3 张证据块)→④我的判断(LLM)→⑤下一步(行动计划)。第 ③ 层按用户问题触发，不固定 6 张。

**Task 3.2 — 后端结构化响应契约**
- 文件：`app/agent/response.py` + `app/agent/*`
- 内容：把「系统层（结论/变化/画像/行动）」与「LLM 叙事层（判断）」分离；系统层复用 overview/dimensions/issues/review-status 的确定性数据，LLM 只写第 ④ 层。
- 验证：`advisor_eval` 回归 + 浏览器走「问→分层回答→采纳行动」完整路径。

---

## 建议执行顺序

Phase 1 → Phase 2 → Phase 3，每阶段完成后本地验证 + 用户确认，再进下一阶段。全程不推给朋友。
