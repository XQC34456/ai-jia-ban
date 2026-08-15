// 视图：AI 顾问（Phase 4 迁移 vanilla app.js 的「对话建档 + 决策模拟 + 深度报告」）。
// 铁律：
//   - 对话建档走 /api/agent/chat → /api/confirm，决策走 /api/decision，报告走 /api/report；
//     本页只展示后端返回，不计算任何财富结论。
//   - 建档落地（type=applied）后只「失效缓存」，由其它视图按需重拉（确保财富结论始终来自后端）。
import { store, upgrade, adoptAction, loadActionPlan } from '../store.js';
import { api, ApiError } from '../api.js';
import { fmtMoney, fmtPct, fmtRatio } from '../format.js';
import { HealthRadar, CashflowChart, AllocationDonut, DebtGauge, ProtectionGap, GoalProgress, RetirementGap, ScenarioCompare } from '../charts.js';

const { reactive, ref, computed, nextTick, onMounted } = Vue;

// ---------- 五层回答：图表组件名 → charts.js 组件（只读 props.data，零计算） ----------
const CHART_COMPONENTS = {
  radar: HealthRadar,
  cashflow: CashflowChart,
  allocation: AllocationDonut,
  debt: DebtGauge,
  protection: ProtectionGap,
  goals: GoalProgress,
  retirement: RetirementGap,
  scenario_compare: ScenarioCompare,
};
function chartComponent(name) { return CHART_COMPONENTS[name] || null; }

// 关键变化值格式化（口径与 overview.js 的 INVAL_UNIT 对齐）
const INVAL_UNIT = {
  cashflow_surplus: 'money', total_coverage: 'money',
  dti: 'pct', real_estate_pct: 'pct',
  rfr: 'ratio', liquidity_months: 'months', insurance_count: 'count',
};
function fmtChangeVal(r) {
  const kind = INVAL_UNIT[r.key];
  const f = (v) => {
    if (v == null) return '—';
    switch (kind) {
      case 'money': return fmtMoney(v);
      case 'pct': return fmtPct(v);
      case 'ratio': return fmtRatio(v);
      case 'months': return v + ' 个月';
      case 'count': return v + ' 份';
      default: return String(v);
    }
  };
  return f(r.before) + ' → ' + f(r.after);
}

// ---------- 深度报告：markdown → HTML（先转义，再套用 ## / - / ** 三种轻量标记） ----------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function fmtMd(s) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}
function renderAdvice(md) {
  const lines = String(md || '').split('\n');
  let html = '', inList = false;
  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h4>${fmtMd(line.slice(3).trim())}</h4>`;
    } else if (line.trim().startsWith('- ')) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${fmtMd(line.trim().slice(2))}</li>`;
    } else if (line.trim()) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<p>${fmtMd(line.trim())}</p>`;
    }
  }
  if (inList) html += '</ul>';
  return html;
}

// ---------- 决策模拟场景（字段即 /api/decision 入参，口径与后端 run_scenario 对齐） ----------
const DECISION_SCENARIOS = {
  buy_house: {
    label: '买房',
    fields: [
      { key: 'price', label: '房价（元）', type: 'number', def: 3000000, step: 10000 },
      { key: 'down_payment_ratio', label: '首付比例（0~1）', type: 'number', def: 0.3, step: 0.05 },
      { key: 'loan_rate', label: '贷款利率（年，%）', type: 'number', def: 3.5, step: 0.1 },
      { key: 'loan_years', label: '贷款年限（年）', type: 'number', def: 30, step: 1 },
      { key: 'current_rent', label: '当前每月租金（元）', type: 'number', def: 0, step: 100 },
      { key: 'house_growth', label: '房产年增值率（%）', type: 'number', def: 0, step: 0.5 },
      { key: 'horizon_years', label: '模拟年限（年）', type: 'number', def: 10, step: 1 },
    ],
  },
  prepay: {
    label: '提前还贷',
    fields: [
      { key: 'prepay_amount', label: '提前还款金额（元）', type: 'number', def: 500000, step: 10000 },
      { key: 'method', label: '还款方式', type: 'select', def: 'shorten',
        options: [{ v: 'shorten', l: '缩短年限（月供不变）' }, { v: 'reduce_payment', l: '减少月供（年限不变）' }] },
    ],
  },
};
const SCENARIO_KEYS = Object.keys(DECISION_SCENARIOS);

export const ChatView = {
  setup() {
    const input = ref('');
    const chatInputEl = ref(null);
    const sending = ref(false);
    const chatError = ref('');

    // P1 跨视图预填：Goals/Retirement/Sandbox 的「问顾问」写入一次性草稿，落到输入框后立即清空。
    // 一次性消费——离开聊天页再回来不会残留旧问题。
    if (store.chat.draft) { input.value = store.chat.draft; store.chat.draft = null; }

    // —— 行动计划（P1.4：⑤下一步可采纳，与风险问题页共用 issue_id+action 去重）——
    const planError = ref(null);
    const adoptedSet = computed(() => {
      const s = new Set();
      const plans = (store.actionPlan.data && store.actionPlan.data.plans) || [];
      for (const p of plans) if (p.status === 'todo') s.add(p.issue_id + '|' + p.action);
      return s;
    });
    onMounted(() => { loadActionPlan().catch(() => {}); });
    async function adoptFromChat(ap) {
      planError.value = null;
      try {
        await adoptAction({ issue_id: ap.issue_id, action: ap.action, detail: ap.detail });
      } catch (e) { planError.value = e.message || '采纳失败'; }
    }

    // —— 决策模拟 ——
    const decisionOpen = ref(false);
    const decisionScenario = ref('buy_house');
    const decisionParams = reactive({});
    const decisionResult = ref(null);
    const decisionBusy = ref(false);
    const decisionError = ref('');

    // —— 深度报告 ——
    const reportOpen = ref(false);
    const report = ref(null);
    const reportBusy = ref(false);
    const reportError = ref('');

    function resetDecisionParams() {
      for (const k of Object.keys(decisionParams)) delete decisionParams[k];
      for (const f of DECISION_SCENARIOS[decisionScenario.value].fields) decisionParams[f.key] = f.def;
    }

    function invalidateCaches() {
      store.overview = null;
      store.goals.data = null;
      store.issues.data = null;
    }

    async function scrollChat() {
      await nextTick();
      const el = document.querySelector('.chat-scroll');
      if (el) el.scrollTop = el.scrollHeight;
    }

    // —— 对话 ——
    async function send() {
      const text = input.value.trim();
      if (!text || sending.value) return;
      input.value = '';
      store.chat.messages.push({ who: 'user', text });
      sending.value = true; chatError.value = '';
      scrollChat();
      try {
        const d = await api('/api/agent/chat', { method: 'POST', body: { message: text }, token: store.auth.token });
        if (d.type === 'confirm') {
          store.chat.messages.push({ type: 'confirm', pendingId: d.pending_id, message: d.message, items: d.items, groups: d.groups || [], resolved: false });
        } else {
          store.chat.messages.push({ who: 'bot', agent: d });
        }
      } catch (e) {
        chatError.value = e.message || '请求失败';
      } finally {
        sending.value = false;
        scrollChat();
      }
    }

    async function confirm(msg, ok) {
      if (msg.resolved) return;
      msg.resolved = true;
      try {
        const d = await api('/api/confirm', { method: 'POST', body: { pending_id: msg.pendingId, confirmed: ok }, token: store.auth.token });
        store.chat.messages.push({ who: 'bot', text: d.message });
        if (d.type === 'applied') invalidateCaches();
      } catch (e) {
        chatError.value = e.message || '确认失败';
      } finally {
        scrollChat();
      }
    }

    function onKey(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    }

    // —— 结构化追问（P1.3）：系统缺数检测出的问题 → 点一下回填输入框，直接作答 ——
    function fillInput(q) {
      input.value = q;
      nextTick(() => { if (chatInputEl.value) chatInputEl.value.focus(); });
    }

    // —— 决策 ——
    const isVip = () => store.auth.tier === 'vip';

    function openDecision() {
      decisionError.value = '';
      if (!isVip()) { decisionError.value = '决策模拟是 VIP 专属功能，升级后解锁。'; return; }
      decisionScenario.value = 'buy_house';
      resetDecisionParams();
      decisionResult.value = null;
      decisionOpen.value = true;
    }
    function pickDecisionScenario(k) {
      decisionScenario.value = k;
      resetDecisionParams();
      decisionResult.value = null;
      decisionError.value = '';
    }
    async function runDecision() {
      decisionBusy.value = true; decisionError.value = ''; decisionResult.value = null;
      try {
        decisionResult.value = await api('/api/decision', {
          method: 'POST',
          body: { scenario: decisionScenario.value, params: { ...decisionParams } },
          token: store.auth.token,
        });
      } catch (e) {
        decisionError.value = e.message;
        if (e instanceof ApiError && e.status === 403) decisionError.value += '（VIP 专属功能）';
      } finally {
        decisionBusy.value = false;
      }
    }
    async function doUpgrade() {
      try { await upgrade(); decisionError.value = ''; reportError.value = ''; }
      catch (e) { /* 忽略：升级失败提示留在对应 err-box */ }
    }

    // —— 报告 ——
    function openReport() {
      reportError.value = '';
      if (!isVip()) { reportError.value = '深度报告是 VIP 专属功能，升级后解锁。'; return; }
      report.value = null;
      reportOpen.value = true;
      loadReport();
    }
    async function loadReport() {
      reportBusy.value = true; reportError.value = '';
      try {
        report.value = await api('/api/report', { token: store.auth.token });
      } catch (e) {
        reportError.value = e.message;
        if (e instanceof ApiError && e.status === 403) reportError.value += '（VIP 专属功能）';
      } finally {
        reportBusy.value = false;
      }
    }

    // 报告派生（纯展示，零计算）
    const reportAdvice = computed(() => (report.value ? renderAdvice(report.value.advice) : ''));
    const reportMembers = computed(() => {
      const ms = report.value && report.value.members;
      if (!ms || !ms.length) return '未录入';
      return ms.map(p => `${p.name}${p.relation ? '（' + p.relation + '）' : ''}${p.age ? ' · ' + p.age + '岁' : ''}`).join('、');
    });
    const reportAllocation = computed(() => (report.value && report.value.asset_allocation) || []);
    const reportGoals = computed(() => {
      const s = report.value && report.value.snapshot;
      return (s && s.goals) || [];
    });
    const reportProblems = computed(() => (report.value && report.value.problems) || []);

    // 决策/报告通用格式化
    function fmtVal(r, v) {
      if (v == null) return '—';
      if (r.money) return fmtMoney(v);
      if (r.months) return v + ' 个月';
      if (r.pct) return (Number(v) * 100).toFixed(1) + '%';
      return Number(v).toLocaleString('zh-CN');
    }
    function fmtMetric(x) {
      if (x.value == null) return '—';
      switch (x.unit) {
        case 'pct': return (Number(x.value) * 100).toFixed(1) + '%';
        case 'months': return x.value + ' 个月';
        case 'ratio': return Number(x.value).toFixed(2) + '×';
        case 'score': return Number(x.value).toFixed(0) + ' 分';
        case 'money': return fmtMoney(x.value);
        default: return Number(x.value).toLocaleString('zh-CN');
      }
    }
    function summaryLabel(s) { return s.money ? fmtMoney(s.value) : String(s.value); }

    // 保存报告：把已渲染的报告导出为自包含 HTML 文件（下载），不接打印机、不依赖后端/依赖库。
    // 只抓取已渲染 DOM（.report-body），数字仍是后端报告字段，零新增计算。
    const REPORT_CSS = `
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
             background: #F7F6F3; color: #23201D; line-height: 1.6; padding: 32px 16px; }
      .report { max-width: 720px; margin: 0 auto; background: #FFFFFF; border-radius: 12px;
                padding: 32px; box-shadow: 0 1px 3px rgba(30,26,22,.06), 0 8px 24px rgba(30,26,22,.06); }
      header { border-bottom: 2px solid #F2DDB8; padding-bottom: 16px; margin-bottom: 20px; }
      h1 { font-size: 22px; }
      .meta { font-size: 13px; color: #6B6560; margin-top: 6px; }
      h4 { font-size: 15px; margin: 20px 0 10px; color: #B45309; }
      .rp-meta { font-size: 12px; color: #6B6560; border-bottom: 1px solid #E7E2DA; padding-bottom: 10px; }
      .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
      .stat { background: #F7F6F3; border: 1px solid #E7E2DA; border-radius: 8px; padding: 10px 12px; }
      .stat label { display: block; font-size: 12px; color: #6B6560; margin-bottom: 2px; }
      .stat b { font-size: 16px; font-weight: 700; }
      .stat.hl { background: #FEF3E2; border-color: #F2DDB8; }
      .stat.hl b { color: #B45309; }
      .rp-alloc { display: flex; flex-direction: column; gap: 8px; }
      .kv { display: flex; justify-content: space-between; align-items: baseline; }
      .kv span { color: #6B6560; }
      .kv b { font-weight: 600; }
      .rp-problem { border-left: 3px solid #D97706; padding: 8px 12px; background: #F7F6F3;
                    border-radius: 6px; font-size: 13px; margin-bottom: 8px; }
      .rp-advice-line { color: #6B6560; margin-top: 4px; }
      .goal-row { border-top: 1px solid #E7E2DA; padding-top: 8px; margin-top: 8px; }
      .goal-top { display: flex; justify-content: space-between; align-items: center; }
      .goal-need { font-size: 12px; color: #6B6560; }
      .goal-progress { height: 6px; border-radius: 4px; background: #EFECE6; overflow: hidden; margin: 6px 0 4px; }
      .goal-progress i { display: block; height: 100%; background: #D97706; }
      .goal-meta { font-size: 12px; color: #6B6560; }
      .rp-advice h4 { font-size: 14px; margin-top: 6px; }
      .rp-advice ul { margin: 4px 0; padding-left: 18px; }
      .rp-advice p { margin: 6px 0; }
      .rp-disclaimer { font-size: 12px; color: #6B6560; border-top: 1px solid #E7E2DA;
                       padding-top: 12px; margin-top: 16px; }
      .empty-hint { color: #6B6560; font-size: 13px; padding: 8px 0; }
      @media print { body { background: #fff; padding: 0; } .report { box-shadow: none; } }
    `;
    function saveReport() {
      const body = document.querySelector('.report-body');
      if (!body || !report.value) return;
      const family = report.value.family_name || '家庭财富';
      const title = family + ' · 家庭财富报告';
      const date = report.value.generated_at || '';
      const doc = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(title)}</title>
<style>${REPORT_CSS}</style>
</head>
<body>
<article class="report">
  <header><h1>${escapeHtml(title)}</h1><p class="meta">生成日期：${escapeHtml(date)}</p></header>
  ${body.innerHTML}
</article>
</body>
</html>`;
      const blob = new Blob([doc], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = family + '-家庭财富报告.html';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }

    return {
      store, input, sending, chatError, send, confirm, onKey, fillInput,
      planError, adoptedSet, adoptFromChat,
      DECISION_SCENARIOS, SCENARIO_KEYS,
      decisionOpen, decisionScenario, decisionParams, decisionResult, decisionBusy, decisionError,
      openDecision, pickDecisionScenario, runDecision, doUpgrade,
      reportOpen, report, reportBusy, reportError, openReport, loadReport,
      reportAdvice, reportMembers, reportAllocation, reportGoals, reportProblems,
      fmtMoney, fmtVal, fmtMetric, summaryLabel, saveReport,
      chartComponent, fmtChangeVal,
    };
  },
  template: `
  <div class="view chat-view">
    <div class="chat-head">
      <div class="chat-title">
        <h2>AI 家办顾问</h2>
        <p class="lead">直接描述家庭情况，确认后自动建档；也可一键生成深度报告、做决策模拟。</p>
      </div>
      <div class="chat-actions">
        <button class="btn-ghost" @click="openReport">📄 深度报告</button>
        <button class="btn-ghost" @click="openDecision">🧭 决策模拟</button>
      </div>
    </div>

    <div v-if="reportError && !reportOpen" class="err-box">
      <span>{{ reportError }}</span>
      <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="doUpgrade">一键升级 VIP</button>
    </div>
    <div v-if="decisionError && !decisionOpen" class="err-box">
      <span>{{ decisionError }}</span>
      <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="doUpgrade">一键升级 VIP</button>
    </div>
    <div v-if="chatError" class="err-box"><span>{{ chatError }}</span></div>

    <div class="chat-scroll card">
      <div v-if="!store.chat.messages.length" class="chat-empty">
        👋 你好，我是你的 AI 家办顾问。<br />
        试着告诉我你的家庭情况，例如：「我月收入 3.8 万，房贷 3000，房租 5000，车贷 3500，孩子学费 3000，生活费 5000」。
      </div>
      <div v-for="(m, idx) in store.chat.messages" :key="idx">
        <div v-if="m.type === 'confirm'" class="chat-confirm">
          <div class="chat-confirm-text">{{ m.message }}</div>
          <div v-if="m.groups && m.groups.length" class="confirm-groups">
            <div v-for="(g, gi) in m.groups" :key="gi" class="confirm-group">
              <div class="confirm-group-head">{{ g.icon }} {{ g.label }}</div>
              <ul class="confirm-group-items"><li v-for="(it, i) in g.items" :key="i">{{ it }}</li></ul>
            </div>
          </div>
          <ul v-else><li v-for="(it, i) in m.items" :key="i">{{ it }}</li></ul>
          <div class="chat-confirm-actions">
            <template v-if="!m.resolved">
              <button class="btn-primary btn-sm" @click="confirm(m, true)">确认</button>
              <button class="btn-ghost btn-sm" @click="confirm(m, false)">取消</button>
            </template>
            <span v-else class="muted">已处理</span>
          </div>
        </div>
        <div v-else-if="m.agent" class="chat-agent">
          <!-- V2.6 五层回答：①结论→②关键变化→③财务画像→④我的判断→⑤下一步 -->
          <template v-if="m.agent.layers">
            <div v-if="m.agent.layers.conclusion" class="layer-conclusion">
              <span class="layer-step">① 结论</span>
              <div class="layer-conclusion-text">{{ m.agent.layers.conclusion }}</div>
            </div>

            <div v-if="m.agent.layers.changes && m.agent.layers.changes.length" class="layer-block">
              <div class="layer-step">② 关键变化</div>
              <div class="layer-changes">
                <span v-for="(c, i) in m.agent.layers.changes" :key="i" class="change-chip">
                  {{ c.label }}：{{ fmtChangeVal(c) }}
                </span>
              </div>
            </div>

            <div v-if="m.agent.layers.charts && m.agent.layers.charts.length" class="layer-block">
              <div class="layer-step">③ 财务画像</div>
              <div v-for="(b, i) in m.agent.layers.charts" :key="i" class="layer-chart-block">
                <div class="layer-chart-q">{{ b.question }}</div>
                <component :is="chartComponent(b.chart)" :data="b.data" />
              </div>
            </div>

            <div v-if="m.agent.layers.judgment || m.agent.summary" class="layer-block">
              <div class="layer-step">④ 我的判断</div>
              <div class="agent-finding">{{ m.agent.layers.judgment || m.agent.summary }}</div>
            </div>

            <div v-if="(m.agent.layers.action_plans && m.agent.layers.action_plans.length) || (m.agent.layers.action_plan && m.agent.layers.action_plan.length)" class="layer-block">
              <div class="layer-step">⑤ 下一步</div>
              <div v-if="planError" class="err-box"><span>{{ planError }}</span></div>
              <!-- P1.4：可采纳结构（新链路） -->
              <div v-if="m.agent.layers.action_plans && m.agent.layers.action_plans.length" class="actionplan-list">
                <div v-for="(ap, i) in m.agent.layers.action_plans" :key="i" class="actionplan-item">
                  <div class="actionplan-text">
                    <span class="actionplan-action">{{ ap.action }}</span>
                    <span v-if="ap.detail" class="actionplan-detail">{{ ap.detail }}</span>
                  </div>
                  <button v-if="!adoptedSet.has(ap.issue_id + '|' + ap.action)"
                          class="btn-mini rec-adopt" @click="adoptFromChat(ap)">＋ 采纳</button>
                  <span v-else class="rec-adopted">已加入计划</span>
                </div>
              </div>
              <!-- 旧扁平兜底（旧缓存无 action_plans） -->
              <div v-else class="agent-next">
                <span v-for="(a, i) in m.agent.layers.action_plan" :key="i" class="chip">{{ a }}</span>
              </div>
            </div>

            <div v-if="m.agent.vip_boundary" class="vip-boundary">
              <div class="vip-boundary-label">🔒 进一步分析（VIP）</div>
              <div class="vip-boundary-text">{{ m.agent.vip_boundary }}</div>
              <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="doUpgrade">一键升级 VIP</button>
            </div>

            <div v-if="m.agent.follow_up_questions && m.agent.follow_up_questions.length" class="layer-block">
              <div class="layer-step">⑥ 还差这些信息</div>
              <div class="followup-list">
                <button v-for="(f, i) in m.agent.follow_up_questions" :key="i"
                  class="followup-chip" :title="f.reason" @click="fillInput(f.question)">
                  {{ f.question }}
                </button>
              </div>
            </div>
          </template>

          <!-- 旧扁平渲染兜底（无 layers：澄清/拒绝/错误，或旧缓存） -->
          <template v-else>
            <div class="agent-intent">{{ m.agent.summary }}</div>
            <div v-if="m.agent.finding" class="agent-finding">{{ m.agent.finding }}</div>
            <ul v-if="m.agent.metrics && m.agent.metrics.length" class="agent-metrics">
              <li v-for="(x, i) in m.agent.metrics" :key="i">
                <b>{{ x.label }}</b> {{ fmtMetric(x) }}
                <span class="src" :title="x.source">{{ x.source }}</span>
              </li>
            </ul>
            <ul v-if="m.agent.recommendations && m.agent.recommendations.length" class="agent-recs">
              <li v-for="(r, i) in m.agent.recommendations" :key="i">{{ r }}</li>
            </ul>
            <div v-if="m.agent.next_actions && m.agent.next_actions.length" class="agent-next">
              <span v-for="(a, i) in m.agent.next_actions" :key="i" class="chip">{{ a }}</span>
            </div>
            <div v-if="m.agent.vip_boundary" class="vip-boundary">
              <div class="vip-boundary-label">🔒 进一步分析（VIP）</div>
              <div class="vip-boundary-text">{{ m.agent.vip_boundary }}</div>
              <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="doUpgrade">一键升级 VIP</button>
            </div>
          </template>
        </div>
        <div v-else class="chat-msg" :class="m.who">{{ m.text }}</div>
      </div>
      <div v-if="sending" class="chat-msg bot">思考中…</div>
    </div>

    <div class="chat-input-row">
      <textarea ref="chatInputEl" v-model="input" class="chat-input" rows="2"
        placeholder="输入家庭情况或问题…（Enter 发送，Shift+Enter 换行）" @keydown="onKey"></textarea>
      <button class="btn-primary" :disabled="sending || !input.trim()" @click="send">发送</button>
    </div>

    <!-- 决策模拟弹窗 -->
    <div v-if="decisionOpen" class="modal-mask" @click.self="decisionOpen = false">
      <div class="modal">
        <div class="modal-head">
          <span class="modal-title">决策模拟</span>
          <button class="modal-close" @click="decisionOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="lead">配置参数后，后端 /api/decision 返回 A/B 两方案对比；本页只展示，不计算结论。
            <a href="#/sandbox" @click="decisionOpen = false">更多情景（投资 / 收入变化）→ 情景沙盘</a>
          </p>
          <div class="tabs">
            <button v-for="k in SCENARIO_KEYS" :key="k" class="tab"
                    :class="{ active: decisionScenario === k }" @click="pickDecisionScenario(k)">
              {{ DECISION_SCENARIOS[k].label }}
            </button>
          </div>
          <div class="modal-form">
            <label v-for="f in DECISION_SCENARIOS[decisionScenario].fields" :key="f.key" class="field">
              <span class="f-label">{{ f.label }}</span>
              <input v-if="f.type === 'number'" type="number" v-model.number="decisionParams[f.key]" :step="f.step" />
              <select v-else v-model="decisionParams[f.key]">
                <option v-for="o in f.options" :key="o.v" :value="o.v">{{ o.l }}</option>
              </select>
            </label>
          </div>
          <div class="actions">
            <button class="btn-primary" :disabled="decisionBusy" @click="runDecision">
              {{ decisionBusy ? '模拟中…' : '开始模拟' }}
            </button>
          </div>
          <div v-if="decisionError" class="err-box">
            <span>{{ decisionError }}</span>
            <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="doUpgrade">一键升级 VIP</button>
          </div>

          <section v-if="decisionResult" class="result">
            <div v-if="decisionResult.error" class="err-box"><span>{{ decisionResult.error }}</span></div>
            <template v-else>
              <div v-if="decisionResult.summary && decisionResult.summary.length" class="stat-grid">
                <div v-for="(s, i) in decisionResult.summary" :key="i" class="stat">
                  <label>{{ s.label }}</label><b>{{ summaryLabel(s) }}</b>
                </div>
              </div>
              <table class="cmp-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th class="num">方案A · {{ decisionResult.plan_a_label }}</th>
                    <th class="num">方案B · {{ decisionResult.plan_b_label }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in decisionResult.rows" :key="i" :class="{ 'hl-row': r.highlight }">
                    <td class="metric">{{ r.label }}</td>
                    <td class="num">{{ fmtVal(r, r.a) }}</td>
                    <td class="num val">{{ fmtVal(r, r.b) }}</td>
                  </tr>
                </tbody>
              </table>
              <div class="decision-conclusion">💡 {{ decisionResult.conclusion }}</div>
            </template>
          </section>
        </div>
      </div>
    </div>

    <!-- 深度报告弹窗 -->
    <div v-if="reportOpen" class="modal-mask" @click.self="reportOpen = false">
      <div class="modal modal-lg report-modal">
        <div class="modal-head">
          <span class="modal-title">{{ report ? (report.family_name + ' · 家庭财富报告') : '深度报告' }}</span>
          <div class="modal-head-actions">
            <button v-if="report" class="btn-ghost btn-sm" @click="saveReport">💾 保存报告</button>
            <button class="modal-close" @click="reportOpen = false">✕</button>
          </div>
        </div>
        <div class="modal-body">
          <div v-if="reportBusy" class="state-hint">报告生成中…</div>
          <div v-else-if="reportError" class="err-box">
            <span>{{ reportError }}</span>
            <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="doUpgrade">一键升级 VIP</button>
          </div>
          <div v-else-if="report" class="report-body">
            <div class="rp-meta">生成日期：{{ report.generated_at }}　|　成员：{{ reportMembers }}</div>

            <h4>一、家庭概览</h4>
            <div class="stat-grid">
              <div class="stat"><label>总资产</label><b>{{ fmtMoney(report.snapshot.total_assets) }}</b></div>
              <div class="stat"><label>总负债</label><b>{{ fmtMoney(report.snapshot.total_liabilities) }}</b></div>
              <div class="stat hl"><label>净资产</label><b>{{ fmtMoney(report.snapshot.net_worth) }}</b></div>
              <div class="stat"><label>月收入</label><b>{{ fmtMoney(report.snapshot.monthly_income) }}</b></div>
              <div class="stat"><label>月支出</label><b>{{ fmtMoney(report.snapshot.monthly_expense) }}</b></div>
              <div class="stat"><label>月结余</label><b>{{ fmtMoney(report.snapshot.monthly_surplus) }}</b></div>
              <div class="stat"><label>安全边际</label><b>{{ report.snapshot.safety_margin && report.snapshot.safety_margin.score != null ? report.snapshot.safety_margin.score + ' 分 · ' + report.snapshot.safety_margin.level : '—' }}</b></div>
              <div class="stat"><label>应急月数</label><b>{{ report.snapshot.emergency_months != null ? report.snapshot.emergency_months + ' 个月' : '—' }}</b></div>
            </div>

            <h4>二、资产配置</h4>
            <div v-if="reportAllocation.length" class="rp-alloc">
              <div v-for="a in reportAllocation" :key="a.type" class="kv">
                <span>{{ a.type }}</span>
                <b>{{ fmtMoney(a.value) }} · {{ a.pct }}%</b>
              </div>
            </div>
            <div v-else class="empty-hint">暂无资产数据</div>

            <h4>三、健康体检</h4>
            <div v-if="reportProblems.length">
              <div v-for="(p, i) in reportProblems" :key="i" class="rp-problem">
                <b>{{ i + 1 }}. {{ p.title }}</b><br />{{ p.why }}
                <div class="rp-advice-line">建议：{{ p.advice }}</div>
              </div>
            </div>
            <div v-else class="empty-hint">暂未发现明显风险</div>

            <h4>四、目标规划</h4>
            <div v-if="reportGoals.length">
              <div v-for="(g, i) in reportGoals" :key="i" class="goal-row">
                <div class="goal-top">
                  <b>{{ g.name }}</b>
                  <span class="goal-need">{{ g.monthly_needed != null ? '每月需存 ' + fmtMoney(g.monthly_needed) : '未设期限' }}</span>
                </div>
                <div class="goal-progress"><i :style="{ width: (Math.min(g.progress || 0, 1) * 100) + '%' }"></i></div>
                <div class="goal-meta">已存 {{ fmtMoney(g.current_saved) }} / 目标 {{ fmtMoney(g.target_amount) }} · 缺口 {{ fmtMoney(g.gap) }}</div>
              </div>
            </div>
            <div v-else class="empty-hint">暂无目标</div>

            <h4>五、综合建议</h4>
            <div class="rp-advice" v-html="reportAdvice"></div>

            <div class="rp-disclaimer">本报告由 AI 自动生成，仅供参考，不构成任何投资、信贷、保险或法律建议。</div>
          </div>
        </div>
      </div>
    </div>
  </div>`,
};
