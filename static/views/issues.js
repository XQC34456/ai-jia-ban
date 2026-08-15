// 视图：风险地图 + 行动计划（主链收口：平铺问题 → 7 维风险地图，并落地可跟踪的行动计划）。
// 只读 Decision Layer build_issues 的统一输出（P0→P2 排序）+ action_plan 表，零财富计算，不接 LLM。
import { store, loadIssues, loadActionPlan, adoptAction, setActionStatus } from '../store.js';
import { navigate } from '../router.js';
import { SEV_TONE, SCENARIO_LABELS, ISSUE_DIM_ORDER, ISSUE_DIM_LABELS } from '../format.js';

const { onMounted, computed, ref } = Vue;

export const IssuesView = {
  setup() {
    onMounted(() => {
      loadIssues().catch(() => {});
      loadActionPlan().catch(() => {});
    });

    const issues = computed(() => (store.issues.data && store.issues.data.issues) || []);
    const counts = computed(() => {
      const c = { P0: 0, P1: 0, P2: 0 };
      for (const i of issues.value) if (c[i.severity] != null) c[i.severity]++;
      return c;
    });

    // 风险地图：按 7 维分组（有问题的维度列问题，健康维度显示灰态）。
    const dims = computed(() => {
      const map = {};
      for (const i of issues.value) {
        const t = i.type || 'other';
        (map[t] = map[t] || []).push(i);
      }
      return ISSUE_DIM_ORDER.map(k => ({
        key: k, label: ISSUE_DIM_LABELS[k] || k, items: map[k] || [],
      }));
    });

    // 行动计划（采纳的建议 + 完成状态）。
    const plans = computed(() => (store.actionPlan.data && store.actionPlan.data.plans) || []);
    const adoptedSet = computed(() => {
      const s = new Set();
      for (const p of plans.value) if (p.status === 'todo') s.add(p.issue_id + '|' + p.action);
      return s;
    });
    const planError = ref(null);

    function sevTone(s) { return SEV_TONE[s] || ''; }
    function scenarioLabel(r) { return SCENARIO_LABELS[r.scenario] || '调整'; }
    // 下一步：切换到对应沙盘场景（默认参数），不反推任何金额。
    function simulate(r) { store.sandbox.preset = r.scenario; navigate('sandbox'); }
    function statusLabel(s) { return { todo: '待办', done: '已完成', skipped: '已跳过' }[s] || s; }
    function planTone(s) { return s === 'done' ? 'plan-done' : s === 'skipped' ? 'plan-skip' : ''; }

    async function adopt(i, r) {
      planError.value = null;
      try {
        await adoptAction({ issue_id: i.issue_id, action: r.action, detail: r.detail });
      } catch (e) { planError.value = e.message || '采纳失败'; }
    }
    async function toggle(p) {
      planError.value = null;
      const next = p.status === 'done' ? 'todo' : 'done';
      try { await setActionStatus(p.id, next); }
      catch (e) { planError.value = e.message || '更新失败'; }
    }

    return {
      store, issues, counts, dims, plans, adoptedSet, planError,
      sevTone, scenarioLabel, simulate, statusLabel, planTone, adopt, toggle,
    };
  },
  template: `
    <div class="view view-sm">
      <p class="lead">风险问题由确定性规则引擎（Decision Layer）检测并按 P0 → P2 排序，非 LLM 生成。可采纳建议进入「行动计划」跟踪。</p>

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

        <!-- 风险地图：按 7 维分组 -->
        <div v-if="issues.length" class="risk-map">
          <div class="map-title">家庭财务风险地图</div>
          <div v-for="d in dims" :key="d.key" class="dim-block">
            <div class="dim-head">
              <span class="dim-label">{{ d.label }}</span>
              <span v-if="d.items.length" class="dim-count">{{ d.items.length }} 个问题</span>
              <span v-else class="dim-healthy">✓ 健康</span>
            </div>
            <div v-for="i in d.items" :key="i.issue_id" class="panel issue-panel">
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
                  <button v-if="!adoptedSet.has(i.issue_id + '|' + r.action)"
                          class="btn-mini rec-adopt" @click="adopt(i, r)">＋ 采纳</button>
                  <span v-else class="rec-adopted">已加入计划</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 行动计划：可勾选完成 -->
        <div class="panel plan-panel">
          <div class="insight-recs-title">我的行动计划</div>
          <div v-if="planError" class="err-box"><span>{{ planError }}</span></div>
          <div v-if="!plans.length" class="empty-hint">还没有采纳任何建议。去上方风险地图点「＋ 采纳」。</div>
          <div v-for="p in plans" :key="p.id" class="plan-item" :class="planTone(p.status)">
            <input type="checkbox" class="plan-check" :checked="p.status === 'done'" @change="toggle(p)" />
            <div class="plan-body">
              <div class="plan-action" :class="{ done: p.status === 'done' }">{{ p.action }}</div>
              <div v-if="p.detail" class="plan-detail">{{ p.detail }}</div>
            </div>
            <span class="plan-status">{{ statusLabel(p.status) }}</span>
          </div>
        </div>
      </template>
    </div>`,
};
