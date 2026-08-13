// 财富沙盘（C3）：模拟 → 对比 → 返回，零前端财富计算。
// 铁律：本页 100% 消费 POST /api/wealth/scenario/{name}/compare 的返回；
//       wealth_score / RFR / NWC 等结论全部由后端 apply_scenario → build_overview 重算，前端只做展示与差值着色。
import { store, loggedIn, login, register, logout, loadOverview } from './store.js';
import { api, ApiError } from './api.js';

const { createApp, reactive, computed, onMounted } = Vue;

// ---------- 展示工具（纯格式化，不产生财富结论） ----------
function fmtMoney(n) {
  if (n == null || n === '') return '—';
  const v = Number(n);
  const sign = v < 0 ? '-' : '';
  const a = Math.abs(v);
  if (a >= 100000000) return sign + (a / 100000000).toFixed(2) + ' 亿';
  if (a >= 10000) return sign + (a / 10000).toFixed(1) + ' 万';
  return sign + a.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
}
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

// 差值着色：dti 下降为优、房产占比中性不着色、其余上升为优。
const UP_GOOD = new Set(['net_worth', 'wealth_score', 'rfr', 'nwc', 'cashflow', 'liquidity', 'goal_completion']);
function deltaTone(key, d) {
  if (d == null || key === 'real_estate_pct' || Math.abs(d) < 1e-9) return '';
  const good = UP_GOOD.has(key) ? d > 0 : d < 0;
  return good ? 'pos' : 'neg';
}

// ---------- 模型能力边界（透传后端 KNOWN_LIMITATIONS，本页不隐藏） ----------
const LIMITATION_LABELS = {
  retirement_debt_service_not_included: '退休测算未把既有房贷的月供清偿安排纳入',
  goal_retirement_semantic_overlap: '养老目标与退休测算在口径上存在部分重叠',
  other_asset_liquidity_assumption: '「其他」类资产按不可即时变现处理（流动性假设）',
};

// ---------- 场景 schema（字段驱动表单，参数即后端 apply 原语入参） ----------
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

// ---------- 根组件 ----------
const App = {
  setup() {
    const auth = reactive({ mode: 'login', username: '', password: '', error: '' });
    const st = reactive({
      scenario: 'buy_house',
      options: [{ id: 'A', params: defaultParams('buy_house') }],
      comparing: false,
      error: null,
      result: null,      // 后端 compare 原始返回 {baseline, options, comparison}
    });

    async function submit() {
      auth.error = '';
      try {
        if (auth.mode === 'login') await login(auth.username, auth.password);
        else await register(auth.username, auth.password);
        await loadOverview();
      } catch (e) { auth.error = e.message; }
    }

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

    onMounted(() => { if (loggedIn.value) loadOverview().catch(() => {}); });

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

    const limitations = computed(() => {
      const ret = st.result && st.result.baseline && st.result.baseline.retirement;
      return (ret && ret.known_limitations) || [];
    });
    function limitationLabel(key) { return LIMITATION_LABELS[key] || key; }

    return {
      store, loggedIn, auth, submit, logout, st,
      SCENARIOS, SCENARIO_KEYS, pickScenario, addOption, removeOption,
      runCompare, upgrade, rows, fmtValue, fmtDelta, deltaTone, fmtMoney,
      limitations, limitationLabel,
    };
  },
  template: `
  <div class="sandbox">
    <div v-if="!loggedIn" class="auth-mask">
      <div class="auth-card">
        <div class="auth-title"><span class="logo">🏠</span> AI家办 · 财富沙盘</div>
        <div class="auth-sub">{{ auth.mode === 'login' ? '登录后模拟家庭财富决策' : '创建你的家庭财富账户' }}</div>
        <div v-if="auth.error" class="auth-error">{{ auth.error }}</div>
        <input v-model="auth.username" placeholder="用户名" autocomplete="username" />
        <input v-model="auth.password" type="password" placeholder="密码（至少 6 位）" autocomplete="current-password" @keyup.enter="submit" />
        <button class="btn-primary" @click="submit">{{ auth.mode === 'login' ? '登 录' : '注 册' }}</button>
        <div class="auth-switch">
          <a @click="auth.mode = auth.mode === 'login' ? 'register' : 'login'; auth.error = ''">
            {{ auth.mode === 'login' ? '没有账号？免费注册' : '已有账号？去登录' }}
          </a>
        </div>
      </div>
    </div>

    <template v-else>
      <header class="topbar">
        <div class="brand"><span class="logo">🏠</span> AI家办 <span class="brand-sub">财富沙盘</span></div>
        <div class="topbar-right">
          <a href="/static/cockpit.html" class="btn-ghost">← 返回驾驶舱</a>
          <span class="user">{{ store.auth.username }}</span>
          <span class="tier" :class="{ vip: store.auth.tier === 'vip' }">{{ store.auth.tier === 'vip' ? 'VIP' : '免费版' }}</span>
          <button class="btn-ghost" @click="logout">退出</button>
        </div>
      </header>

      <main class="wrap">
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
            {{ st.comparing ? '对比中…' : '开始对比' }}
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
            <div class="baseline-chip">当前净资产 {{ fmtMoney(st.result.baseline.net_worth) }} · 财富评分 {{ fmtValue(st.result.baseline.wealth_score, 'score') }}</div>
          </div>

          <table class="cmp-table">
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

          <p class="foot-note">差值 = 方案值 − 当前值。财富评分 / RFR / NWC 均由后端重算，本页未复制任何财富公式。</p>

          <div v-if="limitations.length" class="limits-note">
            <div class="limits-title">⚠️ 模型能力边界（方案变化不会消除以下假设）</div>
            <ul>
              <li v-for="k in limitations" :key="k">{{ limitationLabel(k) }}</li>
            </ul>
          </div>
        </section>
      </main>
    </template>
  </div>`,
};

const app = createApp(App);
app.mount('#app');
