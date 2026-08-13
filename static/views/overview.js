// 视图：家庭总览（Phase 1 迁移自 cockpit.js 的 KPI 卡 + AI 主动洞察）。
// 只读 store.overview；AI 洞察 = 确定性 build_issues（P0→P2），不接 LLM。
import { store, ensureOverview } from '../store.js';
import { HealthScoreCard, NetWorthCard, CashflowCard, DebtCard, GoalsCard, InsightPanel } from './cards.js';

const { onMounted } = Vue;

export const OverviewView = {
  components: { HealthScoreCard, NetWorthCard, CashflowCard, DebtCard, GoalsCard, InsightPanel },
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });
    return { store };
  },
  template: `
    <div class="view">
      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
      <template v-else-if="store.overview">
        <div class="kpi-grid">
          <health-score-card :o="store.overview" />
          <net-worth-card :o="store.overview" />
          <cashflow-card :o="store.overview" />
          <debt-card :o="store.overview" />
        </div>
        <div class="section-grid">
          <goals-card :o="store.overview" />
          <insight-panel :o="store.overview" />
        </div>
      </template>
    </div>`,
};
