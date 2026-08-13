// 财富驾驶舱（C1）：100% 消费 /api/wealth/overview，前端零财富计算。
import { store, loggedIn, login, register, logout, loadOverview } from './store.js';

const { createApp, reactive, onMounted } = Vue;

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
function fmtPct(r) { return r == null ? '—' : (Number(r) * 100).toFixed(0) + '%'; }
function fmtRatio(r) { return r == null ? '—' : Number(r).toFixed(2); }

const CLASS_ORDER = ['cash', 'fixed_income', 'equity', 'real_estate', 'alternative', 'other'];
const CLASS_LABELS = { cash: '现金', fixed_income: '固收', equity: '权益', real_estate: '房产', alternative: '另类', other: '其他' };
const CLASS_COLORS = { cash: '#34c759', fixed_income: '#5ac8fa', equity: '#ff9500', real_estate: '#af52de', alternative: '#ffcc00', other: '#8e8e93' };
const SEV_TONE = { P0: 'sev-p0', P1: 'sev-p1', P2: 'sev-p2' };

// ---------- 卡片组件 ----------

const HealthScoreCard = {
  props: { o: Object },
  computed: {
    tone() {
      const s = this.o && this.o.wealth_score;
      if (s == null) return 'neutral';
      return s >= 80 ? 'good' : s >= 60 ? 'warn' : 'bad';
    },
  },
  template: `
    <div class="card card-score">
      <div class="card-title">财富健康度</div>
      <div class="score-big" :class="tone">{{ o.wealth_score }}</div>
      <div class="score-level" :class="tone">{{ o.wealth_level }}</div>
    </div>`,
};

const NetWorthCard = {
  props: { o: Object },
  template: `
    <div class="card">
      <div class="card-title">净资产</div>
      <div class="big-num">{{ $money(o.net_worth) }}</div>
      <div class="kv"><span>总资产</span><b>{{ $money(o.total_assets) }}</b></div>
      <div class="kv"><span>总负债</span><b>{{ $money(o.total_liabilities) }}</b></div>
      <div class="kv"><span>流动现金</span><b>{{ $money(o.liquid_assets) }}</b></div>
    </div>`,
};

const CashflowCard = {
  props: { o: Object },
  computed: {
    surplusTone() { return (this.o.cashflow.surplus ?? 0) >= 0 ? 'pos' : 'neg'; },
    srTone() {
      const sr = this.o.cashflow.savings_rate;
      if (sr == null) return '';
      return sr < 0.2 ? 'neg' : 'pos';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">现金流（月）</div>
      <div class="kv"><span>月收入</span><b>{{ $money(o.cashflow.income) }}</b></div>
      <div class="kv"><span>月支出</span><b>{{ $money(o.cashflow.expense) }}</b></div>
      <div class="kv"><span>月结余</span><b :class="surplusTone">{{ $money(o.cashflow.surplus) }}</b></div>
      <div class="kv"><span>储蓄率</span><b :class="srTone">{{ $pct(o.cashflow.savings_rate) }}</b></div>
    </div>`,
};

const AllocationCard = {
  props: { o: Object },
  computed: {
    classList() {
      const cls = (this.o.asset_allocation && this.o.asset_allocation.classes) || {};
      return CLASS_ORDER.map(k => {
        const entry = cls[k];
        const pct = (entry && typeof entry.pct === 'number') ? entry.pct
                  : (typeof entry === 'number' ? entry : 0);
        return { key: k, label: CLASS_LABELS[k], color: CLASS_COLORS[k], pct };
      });
    },
    fitnessTone() {
      const f = this.o.allocation_fitness;
      if (f == null) return '';
      return f >= 80 ? 'pos' : f >= 60 ? 'warn' : 'neg';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">资产配置 <span class="fitness" :class="fitnessTone">适配度 {{ o.allocation_fitness }}</span></div>
      <div class="alloc-bar">
        <div v-for="c in classList" :key="c.key" class="alloc-seg"
             :style="{ width: (c.pct*100) + '%', background: c.color }" :title="c.label + ' ' + $pct(c.pct)"></div>
      </div>
      <div class="alloc-legend">
        <div v-for="c in classList" :key="c.key" class="legend-item">
          <span class="dot" :style="{ background: c.color }"></span>
          <span class="lbl">{{ c.label }}</span><b>{{ $pct(c.pct) }}</b>
        </div>
      </div>
    </div>`,
};

const RetirementCard = {
  props: { o: Object },
  computed: {
    r() { return this.o.retirement; },
    quadrantTone() {
      const q = this.r && this.r.quadrant;
      if (q === '养老健康') return 'pos';
      if (q === '未知') return '';
      return 'neg';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">养老准备</div>
      <div v-if="!r" class="empty-hint">录入年龄与支出后可测算养老准备</div>
      <template v-else>
        <div class="kv"><span>RFR（可投资口径）</span><b>{{ fmtRatio(r.rfr) }}</b></div>
        <div class="kv"><span>NWC（净资产口径）</span><b>{{ fmtRatio(r.nwc) }}</b></div>
        <div class="quadrant" :class="quadrantTone">{{ r.quadrant }}</div>
        <div class="kv"><span>退休可投资资产</span><b>{{ $money(r.investable_at_retirement) }}</b></div>
        <div class="kv"><span>退休净资产</span><b>{{ $money(r.net_worth_at_retirement) }}</b></div>
        <div class="kv"><span>退休需求现值</span><b>{{ $money(r.retirement_need_pv) }}</b></div>
        <div class="limits" v-if="r.known_limitations && r.known_limitations.length">
          <span v-for="l in r.known_limitations" :key="l" class="limit-tag">{{ l }}</span>
        </div>
      </template>
    </div>`,
  methods: { fmtRatio },
};

const DebtCard = {
  props: { o: Object },
  computed: {
    dtiTone() {
      const d = this.o.debt.dti;
      if (d == null) return '';
      return d > 0.5 ? 'neg' : d > 0.3 ? 'warn' : 'pos';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">负债</div>
      <div class="kv"><span>总负债</span><b>{{ $money(o.debt.total_debt) }}</b></div>
      <div class="kv"><span>月供</span><b>{{ $money(o.debt.monthly_payment) }}</b></div>
      <div class="kv"><span>DTI（月供/收入）</span><b :class="dtiTone">{{ $pct(o.debt.dti) }}</b></div>
      <div class="kv"><span>保障（保额/年收入）</span><b>{{ fmtRatio(o.protection.coverage_ratio) }}</b></div>
    </div>`,
  methods: { fmtRatio },
};

const GoalsCard = {
  props: { o: Object },
  template: `
    <div class="card card-goals">
      <div class="card-title">家庭目标</div>
      <div v-if="!o.goals || !o.goals.length" class="empty-hint">尚未设置家庭目标</div>
      <div v-for="g in o.goals" :key="g.goal_id" class="goal-row">
        <div class="goal-top"><b>{{ g.name }}</b><span class="goal-type">{{ g.type }}</span></div>
        <div class="goal-progress"><i :style="{ width: (Math.min(g.coverage,1)*100) + '%' }"></i></div>
        <div class="goal-meta">目标 {{ $money(g.target_amount) }} · 已备 {{ $money(g.current_saved) }} · {{ $pct(g.coverage) }}</div>
      </div>
    </div>`,
};

const TopIssuesCard = {
  props: { o: Object },
  computed: {
    top() { return (this.o.issues || []).slice(0, 3); },
  },
  template: `
    <div class="card card-issues">
      <div class="card-title">优先处理（Top 3）</div>
      <div v-if="!top.length" class="empty-hint">暂无重大财富问题 🎉</div>
      <div v-for="i in top" :key="i.issue_id" class="issue-row">
        <span class="sev" :class="sevTone(i.severity)">{{ i.severity }}</span>
        <div class="issue-body">
          <div class="issue-title">{{ i.title }}</div>
          <div class="issue-finding" v-if="i.finding">{{ i.finding }}</div>
        </div>
      </div>
    </div>`,
  methods: { sevTone: (s) => SEV_TONE[s] || '' },
};

// ---------- 根组件 ----------

const App = {
  setup() {
    const auth = reactive({ mode: 'login', username: '', password: '', error: '' });

    async function submit() {
      auth.error = '';
      try {
        if (auth.mode === 'login') await login(auth.username, auth.password);
        else await register(auth.username, auth.password);
        await loadOverview();
      } catch (e) {
        auth.error = e.message;
      }
    }

    async function reload() {
      store.error = null;
      try { await loadOverview(); } catch (e) { /* 错误已入 store.error */ }
    }

    onMounted(() => {
      if (loggedIn.value) reload();
    });

    return { store, loggedIn, auth, submit, reload, logout };
  },
  template: `
    <div class="cockpit">
      <div v-if="!loggedIn" class="auth-mask">
        <div class="auth-card">
          <div class="auth-title"><span class="logo">🏠</span> AI家办 · 财富驾驶舱</div>
          <div class="auth-sub">{{ auth.mode === 'login' ? '登录后查看家庭财富全景' : '创建你的家庭财富账户' }}</div>
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
          <div class="brand"><span class="logo">🏠</span> AI家办 <span class="brand-sub">财富驾驶舱</span></div>
          <div class="topbar-right">
            <span class="user">{{ store.auth.username }}</span>
            <span class="tier" :class="{ vip: store.auth.tier === 'vip' }">{{ store.auth.tier === 'vip' ? 'VIP' : '免费版' }}</span>
            <button class="btn-ghost" @click="reload">↻ 刷新</button>
            <button class="btn-ghost" @click="logout">退出</button>
          </div>
        </header>

        <main v-if="store.loading" class="state-hint">加载中…</main>
        <main v-else-if="store.error" class="state-hint error">{{ store.error }}</main>
        <main v-else-if="store.overview" class="grid">
          <HealthScoreCard :o="store.overview" />
          <NetWorthCard :o="store.overview" />
          <CashflowCard :o="store.overview" />
          <AllocationCard :o="store.overview" />
          <RetirementCard :o="store.overview" />
          <DebtCard :o="store.overview" />
          <GoalsCard :o="store.overview" />
          <TopIssuesCard :o="store.overview" />
        </main>
      </template>
    </div>`,
};

const app = createApp(App);
app.config.globalProperties.$money = fmtMoney;
app.config.globalProperties.$pct = fmtPct;
app.component('HealthScoreCard', HealthScoreCard);
app.component('NetWorthCard', NetWorthCard);
app.component('CashflowCard', CashflowCard);
app.component('AllocationCard', AllocationCard);
app.component('RetirementCard', RetirementCard);
app.component('DebtCard', DebtCard);
app.component('GoalsCard', GoalsCard);
app.component('TopIssuesCard', TopIssuesCard);
app.mount('#app');
