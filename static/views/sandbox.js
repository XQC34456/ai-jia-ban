// 视图：情景沙盘（Phase 3 迁移 sandbox.js）：模拟 → 对比 → 返回，零前端财富计算。
// 铁律：本页 100% 消费 POST /api/wealth/scenario/{name}/compare 的返回；
//       wealth_score / RFR / NWC 等结论全部由后端 apply_scenario → build_overview 重算，前端只做展示与差值着色。
import { store, loadActionPlan, adoptAction } from '../store.js';
import { api, ApiError } from '../api.js';
import { fmtMoney, LIMITATION_LABELS } from '../format.js';
import { interpret } from '../lib/scenario-interpret.js';
import { navigate } from '../router.js';

const { reactive, computed, ref, onMounted } = Vue;

// 差值着色：dti 下降为优、房产占比中性不着色、其余上升为优。
const UP_GOOD = new Set(['net_worth', 'wealth_score', 'rfr', 'nwc', 'cashflow', 'liquidity', 'goal_completion']);

function fmtValue(v, unit) {
  if (v == null) return '—';
  switch (unit) {
    case 'money': return fmtMoney(v);
    case 'pct': return (Number(v) * 100).toFixed(1) + '%';
    case 'ratio': return Number(v).toFixed(2);
    case 'months': return Number(v).toFixed(1) + ' 月';
    case 'score': return Number(v).toFixed(0);
    default: return Number(v).toFixed(2);
  }
}
function fmtDelta(d, unit) {
  if (d == null) return '';
  const sign = d > 0 ? '+' : '';
  switch (unit) {
    case 'money': return sign + fmtMoney(d);
    case 'pct': return sign + (Number(d) * 100).toFixed(1) + 'pp';
    case 'ratio': return sign + Number(d).toFixed(2);
    case 'months': return sign + Number(d).toFixed(1) + ' 月';
    default: return sign + Number(d).toFixed(2);
  }
}
function deltaTone(key, d) {
  if (d == null || key === 'real_estate_pct' || Math.abs(d) < 1e-9) return '';
  const good = UP_GOOD.has(key) ? d > 0 : d < 0;
  return good ? 'pos' : 'neg';
}

// 场景 schema（字段驱动表单，参数即后端 apply 原语入参）
const ASSET_CLASS_OPTIONS = [
  { v: 'cash', l: '现金' }, { v: 'fixed_income', l: '固收' }, { v: 'equity', l: '权益' },
  { v: 'real_estate', l: '房产' }, { v: 'alternative', l: '另类' }, { v: 'other', l: '其他' },
];
const SCENARIOS = {
  buy_house: {
    label: '买房', desc: '模拟购入房产：首付从现金扣减，新增房贷与房产资产。',
    fields: [
      { key: 'price', label: '房价（元）', type: 'number', def: 3000000, step: 10000 },
      { key: 'down_payment_ratio', label: '首付比例（0~1）', type: 'number', def: 0.3, step: 0.05 },
      { key: 'loan_rate', label: '贷款利率（%）', type: 'number', def: 3.5, step: 0.1 },
      { key: 'loan_years', label: '贷款年限（年）', type: 'number', def: 30, step: 1 },
    ],
  },
  prepay: {
    label: '提前还贷', desc: '用现金提前偿还房贷本金，缩短年限或减少月供。',
    fields: [
      { key: 'prepay_amount', label: '提前还款额（元）', type: 'number', def: 500000, step: 10000 },
      { key: 'method', label: '方式', type: 'select', def: 'shorten',
        options: [{ v: 'shorten', l: '缩短年限（月供不变）' }, { v: 'reduce_payment', l: '减少月供（年限不变）' }] },
    ],
  },
  invest: {
    label: '投资', desc: '从现金划出一笔资金投入指定资产大类。',
    fields: [
      { key: 'amount', label: '投资金额（元）', type: 'number', def: 300000, step: 10000 },
      { key: 'to_class', label: '投向资产大类', type: 'select', def: 'equity', options: ASSET_CLASS_OPTIONS },
    ],
  },
  income_change: {
    label: '收入变化', desc: '统一调整所有收入现金流（× 1+pct_change）。',
    fields: [
      { key: 'pct_change', label: '收入变动幅度（如 0.1 = +10%）', type: 'number', def: 0.1, step: 0.05 },
    ],
  },
};
const SCENARIO_KEYS = Object.keys(SCENARIOS);

function defaultParams(name) {
  const p = {};
  for (const f of SCENARIOS[name].fields) p[f.key] = f.def;
  return p;
}

export const SandboxView = {
  setup() {
    // P1 回流：加载既有行动计划，判断哪些模拟方案已加入（避免重复采纳）。
    onMounted(() => { loadActionPlan().catch(() => {}); });

    // 预选场景（来自「下一步」按钮的跨视图信号），只切换场景 + 默认参数，绝不反推金额。
    const preset = store.sandbox.preset;
    store.sandbox.preset = null;
    const initial = (preset && SCENARIOS[preset]) ? preset : 'buy_house';
    const st = reactive({
      scenario: initial,
      options: [{ id: 'A', params: defaultParams(initial) }],
      comparing: false,
      error: null,
      result: null,      // 后端 compare 原始返回 {baseline, options, comparison}
    });

    function pickScenario(key) {
      st.scenario = key;
      st.options = [{ id: 'A', params: defaultParams(key) }];
      st.result = null; st.error = null;
    }
    function addOption() {
      if (st.options.length >= 3) return;
      const id = String.fromCharCode(65 + st.options.length);   // A B C
      st.options.push({ id, params: defaultParams(st.scenario) });
    }
    function removeOption(i) {
      if (st.options.length <= 1) return;
      st.options.splice(i, 1);
      st.options.forEach((o, idx) => { o.id = String.fromCharCode(65 + idx); });
      st.result = null;
    }

    async function runCompare() {
      st.error = null; st.comparing = true; st.result = null;
      try {
        const body = {
          options: st.options.map(o => ({ id: o.id, name: '方案 ' + o.id, params: { ...o.params } })),
        };
        st.result = await api(`/api/wealth/scenario/${st.scenario}/compare`, {
          method: 'POST', body, token: store.auth.token,
        });
      } catch (e) {
        st.error = e.message;
        if (e instanceof ApiError && e.status === 403) st.error += '（VIP 专属功能，可在下方一键升级）';
      } finally {
        st.comparing = false;
      }
    }

    async function upgrade() {
      try {
        await api('/api/upgrade', { method: 'POST', token: store.auth.token });
        store.auth.tier = 'vip';
        st.error = null;
        await runCompare();
      } catch (e) { st.error = e.message; }
    }

    // —— 对比表（转置：指标 × 方案，全来自后端 comparison） ——
    const rows = computed(() => {
      const r = st.result;
      if (!r || !r.options || !r.options.length) return [];
      const first = (r.comparison && r.comparison[r.options[0].id]) || [];
      return first.map(base => ({
        key: base.key, label: base.label, unit: base.unit, baseline: base.baseline,
        cols: r.options.map(o => {
          const row = ((r.comparison && r.comparison[o.id]) || []).find(x => x.key === base.key);
          return { id: o.id, name: o.name || o.id, value: row ? row.option : null, delta: row ? row.delta : null };
        }),
      }));
    });

    // —— 决策解释层（纯前端叙事，只读 comparison + issues，绝不重算财富）——
    const interpretations = computed(() => {
      const r = st.result;
      if (!r || !r.options) return [];
      // 修复：后端 CompareOptionOverview 不含 params，summary 需要用户输入参数 →
      // 传客户端 st.options[i]（params 是入参非计算结果），overview 仍用后端返回。
      return r.options.map((o, i) => interpret(
        r.scenario, (st.options[i] || o), r.baseline, o.overview, (r.comparison && r.comparison[o.id]) || [],
      ));
    });

    // 是否已建档：净资产为 0 且无任何问题 → 判定为空数据（引导先建档）
    const hasData = computed(() => {
      const b = st.result && st.result.baseline;
      if (!b) return true;
      return !(b.net_worth === 0 && (!b.issues || !b.issues.length));
    });

    // 所有方案差异有限 → 显示「各方案差异不大」，绝不制造优劣
    const allNoDiff = computed(() => {
      const ints = interpretations.value;
      return ints.length > 0 && ints.every(i => i.position.key === 'no_diff');
    });

    function resetToBaseline() { st.result = null; st.error = null; }

    // —— P1 回流：模拟结论 → 真实决策（加入行动计划 / 问 AI 顾问评估）——
    // 模拟方案不映射风险问题（issue_id=null），作为独立行动计划项，与 Issues 建议去重互不干扰。
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

    const limitations = computed(() => {
      const ret = st.result && st.result.baseline && st.result.baseline.retirement;
      return (ret && ret.known_limitations) || [];
    });
    function limitationLabel(key) { return LIMITATION_LABELS[key] || key; }

    return {
      store, st, SCENARIOS, SCENARIO_KEYS, pickScenario, addOption, removeOption,
      runCompare, upgrade, rows, fmtValue, fmtDelta, deltaTone, fmtMoney,
      limitations, limitationLabel, interpretations, hasData, allNoDiff, resetToBaseline,
      planError, sandboxAdopted, actionLabel, adoptOption, askAdvisor,
    };
  },
  template: `
  <div class="view">
    <div class="sandbox-banner">
      <span class="sandbox-badge">沙盘模式</span>
      <span>下面的模拟只用于对比决策，<b>不会改动你的真实家庭数据</b>。</span>
    </div>
    <p class="lead">选择情景并配置 1~3 个方案，统一由后端 apply_scenario → build_overview 重算财富，这里只负责展示对比。</p>

    <!-- 情景选择 -->
    <div class="tabs">
      <button v-for="k in SCENARIO_KEYS" :key="k" class="tab"
              :class="{ active: st.scenario === k }" @click="pickScenario(k)">
        {{ SCENARIOS[k].label }}
      </button>
    </div>
    <p class="desc">{{ SCENARIOS[st.scenario].desc }}</p>

    <!-- 方案配置 -->
    <div class="opts">
      <div v-for="(opt, i) in st.options" :key="opt.id" class="opt-card">
        <div class="opt-head">
          <span class="opt-tag">方案 {{ opt.id }}</span>
          <button v-if="st.options.length > 1" class="btn-mini" @click="removeOption(i)">移除</button>
        </div>
        <div class="opt-fields">
          <label v-for="f in SCENARIOS[st.scenario].fields" :key="f.key" class="field">
            <span class="f-label">{{ f.label }}</span>
            <input v-if="f.type === 'number'" type="number" v-model.number="opt.params[f.key]" :step="f.step" />
            <select v-else v-model="opt.params[f.key]">
              <option v-for="o in f.options" :key="o.v" :value="o.v">{{ o.l }}</option>
            </select>
          </label>
        </div>
      </div>
      <button v-if="st.options.length < 3" class="add-opt" @click="addOption">＋ 添加方案</button>
    </div>

    <div class="actions">
      <button class="btn-primary" :disabled="st.comparing" @click="runCompare">
        {{ st.comparing ? '对比中…' : (st.result ? '重新对比' : '开始对比') }}
      </button>
    </div>

    <div v-if="st.error" class="err-box">
      <span>{{ st.error }}</span>
      <button v-if="store.auth.tier !== 'vip'" class="btn-upgrade" @click="upgrade">一键升级 VIP</button>
    </div>

    <!-- 对比结果 -->
    <section v-if="st.result" class="result">
      <div class="result-head">
        <h2>对比结果 · {{ SCENARIOS[st.scenario].label }}</h2>
        <div class="result-head-actions">
          <div class="baseline-chip">当前净资产 {{ fmtMoney(st.result.baseline.net_worth) }} · 财富评分 {{ fmtValue(st.result.baseline.wealth_score, 'score') }}</div>
          <button class="btn-ghost" @click="resetToBaseline">返回基线</button>
        </div>
      </div>

      <!-- 空数据引导（0 数据 → 先建档） -->
      <div v-if="!hasData" class="state-empty">
        <h3>还没有家庭财务数据</h3>
        <p>沙盘需要先知道「现在是什么样」，才能对比「改变之后会怎样」。请先到「家庭数据」页完成建档。</p>
      </div>

      <!-- 差异有限提示（顾问感：不制造优劣） -->
      <div v-if="hasData && allNoDiff" class="state-no-diff">
        各方案与当前状态差异有限，暂无明显优劣，可调整参数后再看。
      </div>

      <div v-if="planError" class="err-box"><span>{{ planError }}</span></div>

      <!-- 决策叙事卡（发生了什么 / 定位 / 风险 / 问题变化，全部只读后端返回） -->
      <div v-if="hasData" class="interp-grid">
        <div v-for="(ip, i) in interpretations" :key="st.result.options[i].id" class="interp-card">
          <div class="interp-head">
            <span class="opt-tag">方案 {{ st.result.options[i].id }}</span>
            <span class="pos-badge" :class="'pos-' + ip.position.key">{{ ip.position.label }}</span>
          </div>
          <div class="interp-summary">{{ ip.summary }}</div>
          <div class="interp-headline">{{ ip.headline }}</div>
          <div v-if="ip.changes.length" class="interp-changes">
            <span v-for="c in ip.changes" :key="c.key" class="change-chip" :class="deltaTone(c.key, c.delta)">
              {{ c.label }} <b>{{ fmtDelta(c.delta, c.unit) }}</b>
            </span>
          </div>
          <div v-if="ip.risk" class="interp-risk">⚠ {{ ip.risk }}</div>
          <div v-if="ip.issueDelta.resolved.length || ip.issueDelta.added.length" class="issue-delta">
            <div v-if="ip.issueDelta.resolved.length" class="issue-resolved">
              <span class="issue-label">已消除</span>
              <span v-for="t in ip.issueDelta.resolved" :key="t" class="issue-chip">{{ t }}</span>
            </div>
            <div v-if="ip.issueDelta.added.length" class="issue-new">
              <span class="issue-label">新增风险</span>
              <span v-for="t in ip.issueDelta.added" :key="t" class="issue-chip">{{ t }}</span>
            </div>
          </div>
          <!-- P1 回流：看完模拟 → 变成真实决策（加入行动计划 / 问 AI 顾问评估） -->
          <div v-if="hasData && !allNoDiff" class="interp-actions">
            <button v-if="!sandboxAdopted.has(actionLabel(st.result.options[i].id))"
                    class="btn-mini rec-adopt" @click="adoptOption(st.result.options[i].id, ip.summary)">＋ 加入行动计划</button>
            <span v-else class="rec-adopted">已加入计划</span>
            <button class="btn-mini" @click="askAdvisor(st.result.options[i].id, ip.summary)">问 AI 顾问评估 →</button>
          </div>
        </div>
      </div>

      <table v-if="hasData" class="cmp-table">
        <thead>
          <tr>
            <th>指标</th>
            <th class="num">当前</th>
            <th v-for="o in st.result.options" :key="o.id" class="num">{{ o.name || o.id }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.key">
            <td class="metric">{{ r.label }}</td>
            <td class="num base">{{ fmtValue(r.baseline, r.unit) }}</td>
            <td v-for="c in r.cols" :key="c.id" class="num">
              <div class="val">{{ fmtValue(c.value, r.unit) }}</div>
              <div class="delta" :class="deltaTone(r.key, c.delta)">{{ fmtDelta(c.delta, r.unit) }}</div>
            </td>
          </tr>
        </tbody>
      </table>

      <p v-if="hasData" class="foot-note">差值 = 方案值 − 当前值。财富评分 / RFR / NWC 均由后端重算，本页未复制任何财富公式。</p>

      <div v-if="hasData && limitations.length" class="limits-note">
        <div class="limits-title">⚠️ 模型能力边界（方案变化不会消除以下假设）</div>
        <ul>
          <li v-for="k in limitations" :key="k">{{ limitationLabel(k) }}</li>
        </ul>
      </div>
    </section>
  </div>`,
};
