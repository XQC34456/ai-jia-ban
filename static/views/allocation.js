// 视图：资产配置（配置诊断页，承接原「财富健康」页的配置体检内容）。
// 只读 store.overview 的 asset_allocation / allocation_fitness / allocation_target / concentration，零计算。
import { store, ensureOverview } from '../store.js';
import { navigate } from '../router.js';
import { fmtMoney, CLASS_ORDER, CLASS_LABELS, CLASS_COLORS, FINANCIAL_CLASSES } from '../format.js';
import { AllocationDonut } from '../charts.js';

const { onMounted, computed } = Vue;

const FIN = ['cash', 'fixed_income', 'equity'];
const FIN_LABELS = { cash: '现金', fixed_income: '固收', equity: '权益' };
const FIN_COLORS = { cash: '#34c759', fixed_income: '#5ac8fa', equity: '#ff9500' };
const DEV_LABELS = { below: '低于目标', above: '高于目标', in_range: '达标' };
const DEV_TONE = { below: 'dev-below', above: 'dev-above', in_range: 'dev-ok' };

function fmtPct1(r) { return r == null ? '—' : (Number(r) * 100).toFixed(1) + '%'; }
function fmtNum(r, d) { return r == null ? '—' : Number(r).toFixed(d == null ? 2 : d); }
function pctOr0(v) { return v == null ? 0 : Math.min(100, Math.max(0, Number(v) * 100)); }

export const AllocationView = {
  components: { AllocationDonut },
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });

    const o = computed(() => store.overview);

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
    function goChat() {
      // Phase 1b：结构化上下文（配置页 → 顾问），配置指标由 Engine 重算，payload 不塞数字。
      store.chat.draft = '为什么这么配置？';
      store.chat.advisorContext = {
        source: 'allocation',
        intent_hint: 'CHECK_ALLOCATION',
        payload: {},
      };
      navigate('chat');
    }

    return {
      store, o, classes, target, concentration, fitness, liquidity,
      deviation, adjustments, issueReasons,
      finPct, tgtPct, devLabel, devTone, pctOr0, goChat,
      fmtMoney, fmtPct: fmtPct1, fmtNum, FIN, FIN_LABELS, FIN_COLORS,
    };
  },
  template: `
  <div class="view view-sm">
    <div v-if="store.loading" class="state-hint">加载中…</div>
    <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
    <template v-else-if="o">
      <!-- ① 资产驾驶舱 -->
      <section class="panel">
        <h2>① 资产驾驶舱</h2>
        <allocation-donut :data="o.asset_allocation.classes" />
        <div class="kv-grid">
          <div class="kv"><span>总资产</span><b>{{ fmtMoney(o.total_assets) }}</b></div>
          <div class="kv"><span>净资产</span><b>{{ fmtMoney(o.net_worth) }}</b></div>
          <div class="kv"><span>总负债</span><b>{{ fmtMoney(o.total_liabilities) }}</b></div>
          <div class="kv"><span>流动现金</span><b>{{ fmtMoney(o.liquid_assets) }}</b></div>
        </div>
      </section>

      <!-- ② 当前配置 -->
      <section class="panel">
        <h2>② 当前配置</h2>
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

      <!-- ③ 个性化目标 -->
      <section class="panel">
        <h2>③ 个性化目标 <span class="fitness">适配度 {{ fitness == null ? '—' : fitness }}</span></h2>
        <div v-if="target && Object.keys(target).length" class="target-row">
          <div v-for="k in FIN" :key="k" class="target-item">
            <div class="t-label">{{ FIN_LABELS[k] }}</div>
            <div class="t-val" :style="{ color: FIN_COLORS[k] }">{{ fmtPct(tgtPct(k)) }}</div>
          </div>
        </div>
        <div v-else class="empty-hint">暂无数据（未生成个性化目标）</div>
        <div class="note">目标仅覆盖可配置金融资产；房产/另类/其他由集中度与流动性单独评估。</div>
      </section>

      <!-- ④ 当前 vs 目标 -->
      <section class="panel">
        <h2>④ 当前 vs 目标</h2>
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

      <!-- ⑤ 偏离判断 -->
      <section class="panel">
        <h2>⑤ 偏离判断</h2>
        <div v-if="deviation" class="dev-row">
          <div v-for="k in FIN" :key="k" class="dev-chip" :class="devTone(k)">
            {{ FIN_LABELS[k] }} · {{ devLabel(k) }}
          </div>
        </div>
        <div v-else class="empty-hint">配置适配度达标，无待处理偏离（引擎未返回偏离明细）</div>
      </section>

      <!-- ⑥ 集中度 -->
      <section class="panel">
        <h2>⑥ 集中度</h2>
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

      <!-- ⑦ 流动性 -->
      <section class="panel">
        <h2>⑦ 流动性</h2>
        <div class="kv-grid">
          <div class="kv"><span>流动现金</span><b>{{ fmtMoney(liquidity.liquid_assets) }}</b></div>
          <div class="kv"><span>应急月数</span><b>{{ liquidity.emergency_months == null ? '—' : liquidity.emergency_months + ' 个月' }}</b></div>
        </div>
      </section>

      <!-- ⑧ 调仓动作 -->
      <section class="panel">
        <h2>⑧ 调仓动作</h2>
        <div v-if="adjustments.length" class="adj-list">
          <div v-for="(r, i) in adjustments" :key="i" class="adj-card">
            <div class="adj-action">{{ r.action }}</div>
            <div class="adj-detail">{{ r.detail }}</div>
            <div v-if="r.scenario" class="adj-scenario">可触发情景：{{ r.scenario }}</div>
          </div>
        </div>
        <div v-else class="empty-hint">暂无调仓建议（配置已达标）</div>
      </section>

      <!-- 进入沙盘 / 问顾问 -->
      <section class="panel action-panel">
        <a href="#/sandbox" class="btn-primary btn-link">调整我的资产配置 → 财富沙盘</a>
        <button class="btn-mini" @click="goChat">问顾问 · 为什么这么配置？</button>
        <p class="warn-note">
          调整后的财富评分 / RFR / NWC 统一由沙盘的 apply_scenario → build_overview 计算，本页不提前预测。
        </p>
      </section>
    </template>
  </div>`,
};
