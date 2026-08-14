// 视图：风险问题（Phase 4 迁移，读 store.issues 切片 → /api/wealth/issues）。
// 只读 Decision Layer build_issues 的统一输出（P0→P2 排序），零财富计算，不接 LLM。
import { store, loadIssues } from '../store.js';
import { navigate } from '../router.js';
import { SEV_TONE, SCENARIO_LABELS } from '../format.js';

const { onMounted, computed } = Vue;

export const IssuesView = {
  setup() {
    onMounted(() => { loadIssues().catch(() => {}); });

    const issues = computed(() => (store.issues.data && store.issues.data.issues) || []);
    const counts = computed(() => {
      const c = { P0: 0, P1: 0, P2: 0 };
      for (const i of issues.value) if (c[i.severity] != null) c[i.severity]++;
      return c;
    });

    function sevTone(s) { return SEV_TONE[s] || ''; }
    function scenarioLabel(r) { return SCENARIO_LABELS[r.scenario] || '调整'; }
    // 下一步：切换到对应沙盘场景（默认参数），不反推任何金额。
    function simulate(r) { store.sandbox.preset = r.scenario; navigate('sandbox'); }

    return { store, issues, counts, sevTone, scenarioLabel, simulate };
  },
  template: `
    <div class="view view-sm">
      <p class="lead">风险问题由确定性规则引擎（Decision Layer）检测并按 P0 → P2 排序，非 LLM 生成。</p>

      <div v-if="store.issues.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.issues.error" class="state-hint error">{{ store.issues.error }}</div>

      <template v-else>
        <div v-if="issues.length" class="panel">
          <div class="kv-grid">
            <div class="kv"><span>问题总数</span><b>{{ issues.length }}</b></div>
            <div class="kv"><span>P0（紧急）</span><b class="bad">{{ counts.P0 }}</b></div>
            <div class="kv"><span>P1（关注）</span><b class="warn">{{ counts.P1 }}</b></div>
            <div class="kv"><span>P2（观察）</span><b>{{ counts.P2 }}</b></div>
          </div>
        </div>

        <div v-if="!issues.length" class="card">
          <div class="empty-hint">暂无重大财富问题，家庭财务稳健 🎉</div>
        </div>

        <div v-for="i in issues" :key="i.issue_id" class="panel">
          <div class="insight-item">
            <span class="sev" :class="sevTone(i.severity)">{{ i.severity }}</span>
            <div class="insight-body">
              <div class="insight-title">{{ i.title }}</div>
              <div class="insight-finding" v-if="i.finding">{{ i.finding }}</div>
              <ul v-if="i.reason && i.reason.length" class="reason-list">
                <li v-for="(r, idx) in i.reason" :key="idx">{{ r }}</li>
              </ul>
            </div>
          </div>
          <div v-if="i.recommendations && i.recommendations.length" class="insight-recs">
            <div class="insight-recs-title">建议动作</div>
            <div v-for="r in i.recommendations" :key="r.recommendation_id || r.action" class="rec-item">
              <span class="rec-action">{{ r.action }}</span>
              <span class="rec-detail">{{ r.detail }}</span>
              <button v-if="r.scenario" class="btn-mini rec-sim" @click="simulate(r)">
                模拟「{{ scenarioLabel(r) }}」→
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>`,
};
