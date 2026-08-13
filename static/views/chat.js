// 视图：AI 顾问（Phase 4 迁移 vanilla app.js 的「对话建档 + 决策模拟 + 深度报告」）。
// 铁律：
//   - 对话建档走 /api/chat → /api/confirm，决策走 /api/decision，报告走 /api/report；
//     本页只展示后端返回，不计算任何财富结论。
//   - 建档落地（type=applied）后只「失效缓存」，由其它视图按需重拉（确保财富结论始终来自后端）。
import { store, upgrade } from '../store.js';
import { api, ApiError } from '../api.js';
import { fmtMoney } from '../format.js';

const { reactive, ref, computed, nextTick } = Vue;

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
    const sending = ref(false);
    const chatError = ref('');

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
        const d = await api('/api/chat', { method: 'POST', body: { message: text }, token: store.auth.token });
        if (d.type === 'confirm') {
          store.chat.messages.push({ type: 'confirm', pendingId: d.pending_id, message: d.message, items: d.items, resolved: false });
        } else {
          store.chat.messages.push({ who: 'bot', text: d.message });
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
    function summaryLabel(s) { return s.money ? fmtMoney(s.value) : String(s.value); }

    function printReport() { window.print(); }

    return {
      store, input, sending, chatError, send, confirm, onKey,
      DECISION_SCENARIOS, SCENARIO_KEYS,
      decisionOpen, decisionScenario, decisionParams, decisionResult, decisionBusy, decisionError,
      openDecision, pickDecisionScenario, runDecision, doUpgrade,
      reportOpen, report, reportBusy, reportError, openReport, loadReport,
      reportAdvice, reportMembers, reportAllocation, reportGoals, reportProblems,
      fmtMoney, fmtVal, summaryLabel, printReport,
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
        试着告诉我你的家庭情况，例如：「我月薪 2 万，老婆 1 万 5，房贷月供 8000，存款 50 万」。
      </div>
      <div v-for="(m, idx) in store.chat.messages" :key="idx">
        <div v-if="m.type === 'confirm'" class="chat-confirm">
          <div class="chat-confirm-text">{{ m.message }}</div>
          <ul><li v-for="(it, i) in m.items" :key="i">{{ it }}</li></ul>
          <div class="chat-confirm-actions">
            <template v-if="!m.resolved">
              <button class="btn-primary btn-sm" @click="confirm(m, true)">确认</button>
              <button class="btn-ghost btn-sm" @click="confirm(m, false)">取消</button>
            </template>
            <span v-else class="muted">已处理</span>
          </div>
        </div>
        <div v-else class="chat-msg" :class="m.who">{{ m.text }}</div>
      </div>
      <div v-if="sending" class="chat-msg bot">思考中…</div>
    </div>

    <div class="chat-input-row">
      <textarea v-model="input" class="chat-input" rows="2"
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
            <button v-if="report" class="btn-ghost btn-sm" @click="printReport">🖨 打印</button>
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
