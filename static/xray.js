// 配置 X-Ray（C2）：100% 消费 /api/wealth/overview，零前端财富计算。
// 铁律：每个数字/结论都来自 API 已返回字段；API 没有的字段显示「暂无数据」，不自行推导。
import { store, loggedIn, login, register, logout, loadOverview } from './store.js';

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
function fmtPct(r) { return r == null ? '—' : (Number(r) * 100).toFixed(1) + '%'; }
function fmtNum(r, d) { return r == null ? '—' : Number(r).toFixed(d == null ? 2 : d); }
function pctOr0(v) { return v == null ? 0 : Math.min(100, Math.max(0, Number(v) * 100)); }

const FIN = ['cash', 'fixed_income', 'equity'];   // 可配置金融资产：目标/偏差只覆盖这三类
const FIN_LABELS = { cash: '现金', fixed_income: '固收', equity: '权益' };
const FIN_COLORS = { cash: '#34c759', fixed_income: '#5ac8fa', equity: '#ff9500' };
const DEV_LABELS = { below: '低于目标', above: '高于目标', in_range: '达标' };
const DEV_TONE = { below: 'dev-below', above: 'dev-above', in_range: 'dev-ok' };

const CLASS_ORDER = ['cash', 'fixed_income', 'equity', 'real_estate', 'alternative', 'other'];
const CLASS_LABELS = { cash: '现金', fixed_income: '固收', equity: '权益', real_estate: '房产', alternative: '另类', other: '其他' };
const CLASS_COLORS = { cash: '#34c759', fixed_income: '#5ac8fa', equity: '#ff9500', real_estate: '#af52de', alternative: '#ffcc00', other: '#8e8e93' };

const App = {
  setup() {
    const auth = reactive({ mode: 'login', username: '', password: '', error: '' });
    const sandboxHint = reactive({ show: false });

    async function submit() {
      auth.error = '';
      try {
        if (auth.mode === 'login') await login(auth.username, auth.password);
        else await register(auth.username, auth.password);
        await loadOverview();
      } catch (e) { auth.error = e.message; }
    }
    async function reload() {
      store.error = null;
      try { await loadOverview(); } catch (e) { /* 错误已入 store.error */ }
    }
    onMounted(() => { if (loggedIn.value) reload(); });

    const o = computed(() => store.overview);

    // —— 以下全部来自 API，不计算 ——
    const classes = computed(() => {
      const c = (o.value && o.value.asset_allocation && o.value.asset_allocation.classes) || {};
      return CLASS_ORDER.map(k => {
        const e = c[k];
        return {
          key: k, label: CLASS_LABELS[k], color: CLASS_COLORS[k],
          pct: (e && typeof e.pct === 'number') ? e.pct : 0,
          value: (e && typeof e.value === 'number') ? e.value : 0,
        };
      });
    });
    const target = computed(() => (o.value && o.value.allocation_target) || {});
    const concentration = computed(() =>
      (o.value && o.value.asset_allocation && o.value.asset_allocation.concentration) || {});
    const fitness = computed(() => o.value && o.value.allocation_fitness);
    const liquidity = computed(() => (o.value && o.value.liquidity) || {});
    const allocIssue = computed(() =>
      ((o.value && o.value.issues) || []).find(i => i.type === 'allocation') || null);
    const deviation = computed(() =>
      (allocIssue.value && allocIssue.value.metric && allocIssue.value.metric.deviation) || null);
    const adjustments = computed(() =>
      (allocIssue.value && allocIssue.value.recommendations) || []);
    const issueReasons = computed(() =>
      (allocIssue.value && allocIssue.value.reason) || []);

    function finPct(k) {
      const fp = (o.value && o.value.asset_allocation && o.value.asset_allocation.financial_pct) || {};
      return fp[k];
    }
    function tgtPct(k) { return target.value[k]; }
    function devLabel(k) { const d = deviation.value; return (d && d[k]) ? (DEV_LABELS[d[k]] || d[k]) : null; }
    function devTone(k) { const d = deviation.value; return (d && d[k]) ? (DEV_TONE[d[k]] || '') : ''; }

    return {
      store, loggedIn, auth, submit, reload, logout, o,
      classes, target, concentration, fitness, liquidity,
      deviation, adjustments, issueReasons,
      finPct, tgtPct, devLabel, devTone, pctOr0,
      fmtMoney, fmtPct, fmtNum, FIN, FIN_LABELS, FIN_COLORS, sandboxHint,
    };
  },
  template: `
  <div class="xray">
    <div v-if="!loggedIn" class="auth-mask">
      <div class="auth-card">
        <div class="auth-title"><span class="logo">🏠</span> AI家办 · 配置 X-Ray</div>
        <div class="auth-sub">{{ auth.mode === 'login' ? '登录后查看资产配置深度分析' : '创建你的家庭财富账户' }}</div>
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
        <div class="brand"><span class="logo">🏠</span> AI家办 <span class="brand-sub">配置 X-Ray</span></div>
        <div class="topbar-right">
          <a href="/static/cockpit.html" class="btn-ghost">← 返回驾驶舱</a>
          <span class="user">{{ store.auth.username }}</span>
          <button class="btn-ghost" @click="reload">↻ 刷新</button>
          <button class="btn-ghost" @click="logout">退出</button>
        </div>
      </header>

      <main v-if="store.loading" class="state-hint">加载中…</main>
      <main v-else-if="store.error" class="state-hint error">{{ store.error }}</main>
      <main v-else-if="o" class="wrap">
        <!-- ① 当前配置 -->
        <section class="panel">
          <h2>① 当前配置</h2>
          <div class="alloc-bar">
            <div v-for="c in classes" :key="c.key" class="alloc-seg"
                 :style="{ width: (c.pct*100) + '%', background: c.color }" :title="c.label"></div>
          </div>
          <div class="alloc-legend">
            <div v-for="c in classes" :key="c.key" class="legend-item">
              <span class="dot" :style="{ background: c.color }"></span>
              <span>{{ c.label }}</span>
              <b>{{ fmtMoney(c.value) }}</b>
              <span class="muted">{{ fmtPct(c.pct) }}</span>
            </div>
          </div>
          <div class="note">金融资产口径（现金/固收/权益）：
            <span v-for="k in FIN" :key="k" class="chip" :style="{ borderColor: FIN_COLORS[k] }">
              {{ FIN_LABELS[k] }} {{ fmtPct(finPct(k)) }}
            </span>
          </div>
        </section>

        <!-- ② 个性化目标 -->
        <section class="panel">
          <h2>② 个性化目标 <span class="fitness">适配度 {{ fitness == null ? '—' : fitness }}</span></h2>
          <div v-if="target && Object.keys(target).length" class="target-row">
            <div v-for="k in FIN" :key="k" class="target-item">
              <div class="t-label">{{ FIN_LABELS[k] }}</div>
              <div class="t-val" :style="{ color: FIN_COLORS[k] }">{{ fmtPct(tgtPct(k)) }}</div>
            </div>
          </div>
          <div v-else class="empty-hint">暂无数据（未生成个性化目标）</div>
          <div class="note">目标仅覆盖可配置金融资产；房产/另类/其他由集中度与流动性单独评估。</div>
        </section>

        <!-- ③ 当前 vs 目标 -->
        <section class="panel">
          <h2>③ 当前 vs 目标</h2>
          <div v-for="k in FIN" :key="k" class="cmp-row">
            <div class="cmp-head">
              <span>{{ FIN_LABELS[k] }}</span>
              <span class="cmp-nums">当前 <b>{{ fmtPct(finPct(k)) }}</b> · 目标 <b>{{ fmtPct(tgtPct(k)) }}</b></span>
            </div>
            <div class="cmp-bar">
              <div class="cmp-fill" :style="{ width: pctOr0(finPct(k)) + '%', background: FIN_COLORS[k] }"></div>
              <div v-if="tgtPct(k) != null" class="cmp-marker" :style="{ left: (tgtPct(k)*100) + '%' }"></div>
            </div>
          </div>
        </section>

        <!-- ④ 偏离判断 -->
        <section class="panel">
          <h2>④ 偏离判断</h2>
          <div v-if="deviation" class="dev-row">
            <div v-for="k in FIN" :key="k" class="dev-chip" :class="devTone(k)">
              {{ FIN_LABELS[k] }} · {{ devLabel(k) }}
            </div>
          </div>
          <div v-else class="empty-hint">配置适配度达标，无待处理偏离（引擎未返回偏离明细）</div>
        </section>

        <!-- ⑤ 集中度 -->
        <section class="panel">
          <h2>⑤ 集中度</h2>
          <div class="kv-grid">
            <div class="kv"><span>HHI（赫芬达尔指数）</span><b>{{ fmtNum(concentration.hhi) }}</b></div>
            <div class="kv"><span>最大单项占比</span><b>{{ fmtPct(concentration.top_asset_pct) }}</b></div>
            <div class="kv"><span>房产占比</span><b>{{ fmtPct(concentration.real_estate_pct) }}</b></div>
            <div class="kv"><span>单只股票占比</span><b>{{ fmtPct(concentration.single_stock_pct) }}</b></div>
          </div>
          <ul v-if="issueReasons.length" class="reason-list">
            <li v-for="(r, i) in issueReasons" :key="i">{{ r }}</li>
          </ul>
        </section>

        <!-- ⑥ 流动性 -->
        <section class="panel">
          <h2>⑥ 流动性</h2>
          <div class="kv-grid">
            <div class="kv"><span>流动现金</span><b>{{ fmtMoney(liquidity.liquid_assets) }}</b></div>
            <div class="kv"><span>应急月数</span><b>{{ liquidity.emergency_months == null ? '—' : liquidity.emergency_months + ' 个月' }}</b></div>
          </div>
        </section>

        <!-- ⑦ 调仓动作 -->
        <section class="panel">
          <h2>⑦ 调仓动作</h2>
          <div v-if="adjustments.length" class="adj-list">
            <div v-for="(r, i) in adjustments" :key="i" class="adj-card">
              <div class="adj-action">{{ r.action }}</div>
              <div class="adj-detail">{{ r.detail }}</div>
              <div v-if="r.scenario" class="adj-scenario">可触发情景：{{ r.scenario }}</div>
            </div>
          </div>
          <div v-else class="empty-hint">暂无调仓建议（配置已达标）</div>
        </section>

        <!-- 进入沙盘 -->
        <section class="panel action-panel">
          <button class="btn-primary" @click="sandboxHint.show = true">调整我的资产配置</button>
          <div v-if="sandboxHint.show" class="warn-note">
            ⏳ 财富沙盘将在 C3 开放——调整后的财富评分 / RFR / NWC 统一由 apply_scenario → build_overview 计算，本页不提前预测。
          </div>
        </section>
      </main>
    </template>
  </div>`,
};

const app = createApp(App);
app.mount('#app');
