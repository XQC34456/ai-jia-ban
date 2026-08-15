// 视图：财富健康（7 维健康雷达页）。
// 只读 store.overview.dimensions（Task 1.1 暴露的确定性 7 维评分）+ 现金流/负债/保障区块，零财富计算。
import { store, ensureOverview } from '../store.js';
import { navigate } from '../router.js';
import { fmtMoney, fmtPct } from '../format.js';
import { HealthRadar, CashflowChart, CashflowBreakdown, DebtGauge, DebtDetail, ProtectionGap, ProtectionMembers } from '../charts.js';

const { onMounted, computed } = Vue;

const DIM_LABELS = {
  cashflow: '现金流', liquidity: '流动性', debt: '负债', protection: '保障',
  allocation: '配置', goals: '目标', retirement: '养老',
};

export const HealthView = {
  components: { HealthRadar, CashflowChart, CashflowBreakdown, DebtGauge, DebtDetail, ProtectionGap, ProtectionMembers },
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });

    const o = computed(() => store.overview);
    const dims = computed(() => (o.value && o.value.dimensions) || []);
    // 维度明细：最弱的排前面，一眼看到「哪维最弱」。
    const dimsSorted = computed(() => [...dims.value].sort((a, b) => (a.score ?? 0) - (b.score ?? 0)));
    const weakCount = computed(() => dims.value.filter(d => d.score < 60).length);
    // 瀑布图数据：只读后端算好的固定/弹性总额，前端零求和。
    const cashflowBreakdown = computed(() => {
      const b = (o.value && o.value.cashflow && o.value.cashflow.breakdown) || {};
      return {
        income: o.value && o.value.cashflow ? o.value.cashflow.income : 0,
        fixed: b.fixed_total,
        elastic: b.elastic_total,
        surplus: o.value && o.value.cashflow ? o.value.cashflow.surplus : 0,
      };
    });

    function dimLabel(name) { return DIM_LABELS[name] || name; }
    function scoreTone(s) { return s >= 80 ? 'pos' : s >= 60 ? 'warn' : 'neg'; }
    function scoreColor(s) { return s >= 80 ? '#34c759' : s >= 60 ? '#ffcc00' : '#ff3b30'; }
    function ratioText(r) { return r == null ? '—' : Number(r).toFixed(1) + ' 倍'; }
    function goChat() { navigate('chat'); }

    return {
      store, o, dims, dimsSorted, weakCount, cashflowBreakdown,
      dimLabel, scoreTone, scoreColor, ratioText, goChat,
      fmtMoney, fmtPct,
    };
  },
  template: `
    <div class="view">
      <p class="lead">财富健康度由确定性引擎按 7 个维度加权计算（现金流/流动性/负债/保障/配置/目标/养老），非 LLM 生成。薄弱维度（评分 &lt;60）高亮。</p>

      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>

      <template v-else-if="o">
        <!-- ① 健康总览 -->
        <div class="panel health-top">
          <div class="health-score">
            <div class="score-big" :class="scoreTone(o.wealth_score)">{{ o.wealth_score }}</div>
            <div class="score-level" :class="scoreTone(o.wealth_score)">{{ o.wealth_level }}</div>
          </div>
          <div class="health-meta">
            <div v-if="weakCount" class="health-weak">有 {{ weakCount }} 个维度偏弱，建议优先关注</div>
            <div v-else class="health-weak ok">7 个维度整体健康 🎉</div>
            <button class="btn-mini" @click="goChat">问顾问 · 这份健康报告怎么理解？</button>
          </div>
        </div>

        <!-- ② 7 维雷达图 -->
        <section class="panel">
          <div class="card-title">家庭财务健康雷达</div>
          <health-radar :data="dims" />
        </section>

        <!-- ③ 维度明细（最弱优先） -->
        <section class="panel">
          <div class="card-title">维度明细</div>
          <div v-for="d in dimsSorted" :key="d.name" class="dim-row">
            <div class="dim-head">
              <span class="dim-name">{{ dimLabel(d.name) }}</span>
              <span class="dim-score" :class="scoreTone(d.score)">{{ d.score }}</span>
            </div>
            <div class="dim-bar"><i :style="{ width: (d.score||0) + '%', background: scoreColor(d.score) }"></i></div>
            <div v-if="d.reasons && d.reasons.length" class="dim-reasons">
              <span v-for="(r, i) in d.reasons" :key="i" class="dim-reason">{{ r }}</span>
            </div>
          </div>
        </section>

        <!-- ④ 重点下钻：现金流 -->
        <section class="panel">
          <div class="card-title">现金流 · 钱去哪了？</div>
          <cashflow-chart :data="o.cashflow" />
          <cashflow-breakdown :data="cashflowBreakdown" />
          <div class="kv-grid">
            <div class="kv"><span>月收入</span><b>{{ fmtMoney(o.cashflow.income) }}</b></div>
            <div class="kv"><span>月支出</span><b>{{ fmtMoney(o.cashflow.expense) }}</b></div>
            <div class="kv"><span>月结余</span><b :class="(o.cashflow.surplus??0)>=0?'pos':'neg'">{{ fmtMoney(o.cashflow.surplus) }}</b></div>
            <div class="kv"><span>储蓄率</span><b>{{ fmtPct(o.cashflow.savings_rate) }}</b></div>
          </div>
          <button class="btn-mini" @click="goChat">问顾问 · 我的现金流健康吗？</button>
        </section>

        <!-- ⑤ 重点下钻：负债 -->
        <section class="panel">
          <div class="card-title">负债 · 债务危险吗？</div>
          <debt-gauge :data="o.debt" />
          <debt-detail v-if="o.debt.items && o.debt.items.length" :data="o.debt.items" />
          <div class="kv-grid">
            <div class="kv"><span>总负债</span><b>{{ fmtMoney(o.debt.total_debt) }}</b></div>
            <div class="kv"><span>月供</span><b>{{ fmtMoney(o.debt.monthly_payment) }}</b></div>
            <div class="kv"><span>DTI（月供/收入）</span><b>{{ fmtPct(o.debt.dti) }}</b></div>
          </div>
          <button class="btn-mini" @click="goChat">问顾问 · 我的负债压力大吗？</button>
        </section>

        <!-- ⑥ 重点下钻：保障 -->
        <section class="panel">
          <div class="card-title">保障 · 出事扛不扛得住？</div>
          <protection-gap :data="o.protection" />
          <protection-members v-if="o.protection.members && o.protection.members.length" :data="o.protection.members" />
          <div class="kv-grid">
            <div class="kv"><span>保险份数</span><b>{{ o.protection.insurance_count }} 份</b></div>
            <div class="kv"><span>总保额</span><b>{{ fmtMoney(o.protection.total_coverage) }}</b></div>
            <div class="kv"><span>年保费</span><b>{{ fmtMoney(o.protection.total_premium) }}</b></div>
            <div class="kv"><span>保额/年收入</span><b>{{ ratioText(o.protection.coverage_ratio) }}</b></div>
          </div>
          <button class="btn-mini" @click="goChat">问顾问 · 我的保障够不够？</button>
        </section>
      </template>
    </div>`,
};
