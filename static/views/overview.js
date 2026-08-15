// 视图：家庭总览（Phase 1 迁移自 cockpit.js 的 KPI 卡 + AI 主动洞察）。
// 只读 store.overview；AI 洞察 = 确定性 build_issues（P0→P2），不接 LLM。
import { store, ensureOverview, loadReview } from '../store.js';
import { SEV_TONE, LEVEL_CONCLUSION, fmtMoney, fmtPct, fmtRatio } from '../format.js';
import { navigate } from '../router.js';
import { HealthRadar } from '../charts.js';
import { HealthScoreCard, NetWorthCard, CashflowCard, DebtCard, GoalsCard, InsightPanel } from './cards.js';

const { onMounted, computed } = Vue;

export const OverviewView = {
  components: { HealthRadar, HealthScoreCard, NetWorthCard, CashflowCard, DebtCard, GoalsCard, InsightPanel },
  setup() {
    onMounted(() => {
      ensureOverview().catch(() => {});
      loadReview().catch(() => {});
    });
    // 今日最重要的 3 件事（体检报告横幅的主角，铁律① 先结论后数字）
    const top3 = computed(() => ((store.overview && store.overview.priorities) || []).slice(0, 3));
    const bannerTone = computed(() => {
      const s = store.overview && store.overview.wealth_score;
      return s >= 80 ? 'lv-good' : s >= 60 ? 'lv-warn' : 'lv-bad';
    });
    function sevTone(s) { return SEV_TONE[s] || ''; }

    // —— 动态重评估横幅：上次判断失效 → 显示变化维度 + 去顾问重新评估 ——
    const staleBanner = computed(() => !!(store.review.data && store.review.data.status === 'stale'));
    const staleReasons = computed(() =>
      (store.review.data && store.review.data.stale_reasons) || []);
    const INVAL_UNIT = {
      cashflow_surplus: 'money', total_coverage: 'money',
      dti: 'pct', real_estate_pct: 'pct',
      rfr: 'ratio', liquidity_months: 'months', insurance_count: 'count',
    };
    function fmtChangeVal(r) {
      const kind = INVAL_UNIT[r.key];
      const f = (v) => {
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

    return { store, top3, bannerTone, LEVEL_CONCLUSION, sevTone,
             navigate, staleBanner, staleReasons, fmtChangeVal };
  },
  template: `
    <div class="view">
      <div v-if="staleBanner" class="stale-banner">
        <div class="stale-title">⚠️ 你的家庭数据已变化，上次建议可能已过时</div>
        <div v-if="staleReasons.length" class="stale-chips">
          <span v-for="r in staleReasons" :key="r.key" class="stale-chip">{{ r.label }}：{{ fmtChangeVal(r) }}</span>
        </div>
        <div v-else class="stale-fallback">判断依赖的关键数据已变化，建议重新评估</div>
        <button class="btn-primary btn-sm" @click="navigate('chat')">去 AI 顾问重新评估</button>
      </div>
      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
      <template v-else-if="store.overview">
        <div class="report-banner" :class="bannerTone">
          <div class="report-label">家庭体检报告</div>
          <template v-if="top3.length">
            <div class="report-top3-title">你的家庭现在最值得关注的 {{ top3.length }} 件事</div>
            <div class="report-top3-item" v-for="(p, i) in top3" :key="i">
              <span class="sev" :class="sevTone(p.severity)">{{ p.severity }}</span>{{ p.title }}
            </div>
          </template>
          <div v-else class="report-no-issue">目前没有发现重大财富问题，家庭财务稳健 🎉</div>
          <div class="report-status">
            <span>{{ LEVEL_CONCLUSION[store.overview.wealth_level] || '这是你当前的家庭财务画像' }}</span>
            <span class="report-score-inline">财富评分 {{ store.overview.wealth_score }}</span>
          </div>
        </div>
        <div class="kpi-grid">
          <health-score-card :o="store.overview" />
          <net-worth-card :o="store.overview" />
          <cashflow-card :o="store.overview" />
          <debt-card :o="store.overview" />
        </div>
        <section class="panel">
          <div class="card-title">财富健康 7 维雷达 <a href="#/health" class="card-link">查看各维下钻 →</a></div>
          <health-radar :data="store.overview.dimensions" />
        </section>
        <div class="section-grid">
          <goals-card :o="store.overview" />
          <insight-panel :o="store.overview" />
        </div>
      </template>
    </div>`,
};
