# P1 · 决策闭环（Goals/Retirement 出口 + Sandbox 回流）实施计划

> 上承 [ui-audit-2026-08-15.md](ui-audit-2026-08-15.md) P1 档（Goals/Retirement 加出口 + Sandbox 回现实引导）。
> **用户已钉死 P0 收口、不磨 UI；P1 重点 = 决策闭环，不是视觉升级。**
> **目标**：让用户看完「目标 / 退休 / 情景模拟」后自然走到「怎么办 / 做决定」，而不是停在一张分析图。
> **架构**：纯前端 5 文件改动（store.js + chat.js + goals.js + retirement.js + sandbox.js），零后端改动、零新增 CSS。复用既有组件与模式（`btn-mini`、`navigate`、`store.sandbox.preset` 跨视图信号）。

---

## Global Constraints（红线，本次一律遵守）

1. **铁律 P1/P2**：本改动零财富计算。所有数字只读后端返回，预填文字只做「组织既有数字」，不产生任何财富结论。
2. **零新增 CSS**：全部复用既有类（`.btn-mini`、`.goal-actions`→用普通 div、`.interp-actions`→用普通 div、`.rec-adopted`、`.empty-hint`、`.err-box`）。
3. **零后端改动**：`/api/agent/chat`、`/api/wealth/action-plan`、`/api/wealth/scenario/*/compare` 全部已存在。
4. **不堆按钮**（P0 教训）：每个页面只给**最少、最诚实**的出口。Goals/Retirement 各 1 个「问顾问」（预填问题），Sandbox 每个方案卡 2 个回流按钮（加入行动计划 / 问顾问评估）。
5. **冻结视觉**：圆角/阴影/颜色/卡片间距/动画一律不动。
6. **确认前不写库**：Sandbox「加入行动计划」只在用户点按钮时 `POST`，绝不自动写入。

---

## 核心机制：跨视图聊天预填（`store.chat.draft`）

> 现有「问顾问」按钮只 `navigate('chat')`，用户落进空聊天窗还得自己打字——这是「走到怎么办」的摩擦。加一个**一次性草稿信号**，与 `store.sandbox.preset`（跨视图「下一步」信号）同一模式，让预填问题落到聊天输入框，用户直接「发送」或稍作修改。

| 文件 | 改动 |
|------|------|
| `static/store.js` | `chat` 切片加 `draft: null` |
| `static/views/chat.js` | setup 读 `store.chat.draft` → 填 `input.value` 后清空 |

---

## 现状 → 目标

| 页面 | 现状 | 目标 |
|------|------|------|
| Goals | 每个目标卡 8 个 kv，纯只读，死胡同 | 每卡 1 个「问顾问 · 这个目标怎么完成？」（预填缺口上下文） |
| Retirement | 缺口图 + 养老卡 + 能力边界，纯只读 | 1 个「问顾问 · 我的退休缺口怎么办？」（预填退休数字） |
| Sandbox | 对比表 + 叙事卡，**停在一张图** | 每个方案卡加「加入行动计划」+「问 AI 顾问评估 →」，形成回流 |

---

## 改动明细（5 文件，无后端）

### Task 1 · 跨视图聊天预填机制

**`static/store.js`** —— `chat` 切片加 `draft`：

**现状**（store.js:32）：
```js
  chat: { messages: [], loading: false, error: null },
```
**改为**：
```js
  chat: { messages: [], loading: false, error: null, draft: null },
```

**`static/views/chat.js`** —— setup 消费 draft（放在 `const input = ref('');` 之后，chat.js:102）：

```js
    // P1 跨视图预填：Goals/Retirement/Sandbox 的「问顾问」写入一次性草稿，落到输入框
    if (store.chat.draft) { input.value = store.chat.draft; store.chat.draft = null; }
```

### Task 2 · Goals 出口（问顾问 · 预填）

**`static/views/goals.js`**：
1. import 加 `navigate`（`import { navigate } from '../router.js';`）。
2. setup 加一个预填函数：
```js
    function askAdvisor(g) {
      store.chat.draft = '我的目标「' + g.name + '」（' + g.type + '）目标金额 '
        + fmtMoney(g.target_amount) + '，已备 ' + fmtMoney(g.current_saved) + '，缺口 '
        + fmtMoney(g.gap) + '，每月需存 ' + fmtMoney(g.monthly_needed) + '，请帮我看看怎么完成最稳。';
      navigate('chat');
    }
```
3. return 加 `askAdvisor`。
4. 每张目标卡（`g` 循环内，kv-grid 之后）加 CTA：
```html
    <div class="goal-actions">
      <button class="btn-mini" @click="askAdvisor(g)">问顾问 · 这个目标怎么完成？</button>
    </div>
```

### Task 3 · Retirement 出口（问顾问 · 预填）

**`static/views/retirement.js`**：
1. import 加 `navigate`（`from '../router.js'`）+ `fmtMoney`（`from '../format.js'`）。
2. setup 加预填函数（数字全部来自 `store.overview.retirement`，只读）：
```js
    function askAdvisor() {
      const r = store.overview && store.overview.retirement;
      const inv = r ? fmtMoney(r.investable_at_retirement) : '—';
      const need = r ? fmtMoney(r.retirement_need_pv) : '—';
      store.chat.draft = '我的退休准备缺口怎么补？当前退休可投资资产 ' + inv
        + '，退休需求现值 ' + need + '，请帮我看看怎么办。';
      navigate('chat');
    }
```
3. return 加 `askAdvisor`。
4. `<retirement-card>` 之后加 CTA（能力边界之前）：
```html
    <div class="panel">
      <button class="btn-mini" @click="askAdvisor">问顾问 · 我的退休缺口怎么办？</button>
    </div>
```

### Task 4 · Sandbox 回流（加入行动计划 + 问顾问评估）

**`static/views/sandbox.js`**：
1. import 改：`import { store, loadActionPlan, adoptAction } from '../store.js';` + `import { navigate } from '../router.js';`
2. setup 顶部（`const preset = ...` 之前）加 `onMounted(() => { loadActionPlan().catch(() => {}); });`（需 `const { onMounted, reactive, computed } = Vue;` 加 `onMounted`）。
3. setup 加回流逻辑（issue_id=null → 独立行动计划项，与 Issues 建议去重不冲突）：
```js
    const planError = ref(null);
    const sandboxAdopted = computed(() => {
      const s = new Set();
      const plans = (store.actionPlan.data && store.actionPlan.data.plans) || [];
      for (const p of plans) if (p.status === 'todo') s.add(p.action);
      return s;
    });
    function actionLabel(optId) {
      return '模拟「' + SCENARIOS[st.scenario].label + '」方案 ' + optId;
    }
    async function adoptOption(optId, summary) {
      planError.value = null;
      try { await adoptAction({ issue_id: null, action: actionLabel(optId), detail: summary }); }
      catch (e) { planError.value = e.message || '采纳失败'; }
    }
    function askAdvisor(optId, summary) {
      store.chat.draft = '我模拟了「' + SCENARIOS[st.scenario].label + '」方案 ' + optId
        + '：' + summary + '。这对我的家庭财务意味着什么？你怎么看？';
      navigate('chat');
    }
```
（需 `const { onMounted, reactive, computed, ref } = Vue;`）
4. return 加 `planError, sandboxAdopted, actionLabel, adoptOption, askAdvisor`。
5. 每张 `interp-card`（`interp-head` 之后 / `issue-delta` 之后）加回流动作行，且**仅 `hasData && !allNoDiff` 时显示**：
```html
    <div v-if="hasData && !allNoDiff" class="interp-actions">
      <button v-if="!sandboxAdopted.has(actionLabel(st.result.options[i].id))"
              class="btn-mini rec-adopt" @click="adoptOption(st.result.options[i].id, ip.summary)">＋ 加入行动计划</button>
      <span v-else class="rec-adopted">已加入计划</span>
      <button class="btn-mini" @click="askAdvisor(st.result.options[i].id, ip.summary)">问 AI 顾问评估 →</button>
    </div>
```

---

## 验证（对齐「决策闭环」验收）

| 验收 | 验证方式 |
|------|----------|
| Goals 出口 | 目标卡有「问顾问」按钮；点击后 chat 输入框**已预填**目标上下文 |
| Retirement 出口 | 退休页有「问顾问」按钮；点击后 chat 预填退休数字 |
| Sandbox 回流 | 对比结果每方案卡有「加入行动计划」+「问 AI 顾问评估」；点击「加入行动计划」→ action_plan 落一条（issue_id=null）→ **Overview ⑤ 与 Issues 计划面板同时可见** |
| 回流不伪造 | 加入行动计划只发生在用户点击时；预填文字全来自后端既有数字 |
| 无回归 | pytest 541（零后端改动）+ node 15 |

### 执行验证步骤
1. **回归**：`python -m pytest -q`（预期 541）+ `node --test tests/js/*.test.js`（预期 15）。
2. **部署**：`python D:\Claude_Code\deploy_update.py`（健康检查 `{"ok":true}`）。
3. **Playwright 真机全流程**（对手机公网 URL）：
   - 注册测试用户 → 灌数据（person + 收入 + 支出 + 资产 + **一个目标**）
   - Goals 页：断言「问顾问」按钮存在 → 点击 → chat 输入框非空且含目标名
   - Retirement 页：断言「问顾问」按钮存在 → 点击 → chat 预填含「退休」
   - Sandbox：选「投资」→ 开始对比 → 断言方案卡有回流按钮 → 点「加入行动计划」→ 查 action_plan 多一条 → Overview ⑤ 显示该项 → Issues 计划面板显示该项
   - 截图：Goals / Retirement / Sandbox 结果（375 + 桌面）
4. **提交**：单独 commit（消息如 `feat(p1): Goals/Retirement 问顾问出口 + Sandbox 决策回流（预填聊天草稿机制）`）+ push。

---

## 明确不做（本次范围外，全部冻结）

- ❌ 圆角 / 阴影 / 颜色 / 卡片间距 / 动画（P2 前全部冻结）
- ❌ Goal→场景的模糊映射模拟按钮（「怎么办」交给有工具的顾问，不硬造）
- ❌ 后端任何改动
- ❌ 导航 / 组件库 / 视觉风格
