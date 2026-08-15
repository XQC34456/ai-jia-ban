// 视图：家庭目标（Phase 4 迁移，读 store.goals 切片 → /api/wealth/goals）。
// 只读后端 build_goals 返回的 GoalOut 统一列表，零财富计算（金额/缺口/覆盖度全部来自后端）。
import { store, loadGoals } from '../store.js';
import { fmtMoney, fmtPct } from '../format.js';
import { GoalProgress } from '../charts.js';
import { navigate } from '../router.js';

const { onMounted, computed } = Vue;

const PRIORITY_LABELS = { 1: '高', 2: '中', 3: '低' };

export const GoalsView = {
  components: { GoalProgress },
  setup() {
    onMounted(() => { loadGoals().catch(() => {}); });

    const goals = computed(() => (store.goals.data && store.goals.data.goals) || []);

    // P1 决策闭环出口：看完目标 → 问顾问怎么办。Phase 1b 改结构化上下文：
    //   payload 只带标识（goal_id/goal_type），缺口/每月需存等数字由 Engine 重算（T4），
    //   绝不把页面聚合数字塞进 payload 或预填问题（避免第二条计算源 / 编造风险）。
    function askAdvisor(g) {
      store.chat.draft = '这个目标怎么完成？';
      store.chat.advisorContext = {
        source: 'goals',
        intent_hint: 'CHECK_GOALS',
        payload: { goal_id: g.goal_id, goal_type: g.type },
      };
      navigate('chat');
    }

    return { store, goals, fmtMoney, fmtPct, PRIORITY_LABELS, askAdvisor };
  },
  template: `
    <div class="view">
      <p class="lead">家庭目标由目标引擎统一测算（金额 / 日期 / 每月需存 / 缺口 / 覆盖度 / 优先级），口径与后端一致。</p>

      <div v-if="store.goals.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.goals.error" class="state-hint error">{{ store.goals.error }}</div>

      <template v-else>
        <div v-if="!goals.length" class="card">
          <div class="empty-hint">尚未设置家庭目标。可到「AI 顾问」对话建档，例如「给孩子准备教育金，目标 100 万」。</div>
        </div>

        <section v-else class="panel">
          <div class="card-title">目标完成进度 · 哪个最落后？</div>
          <goal-progress :data="goals" />
        </section>

        <div v-for="g in goals" :key="g.goal_id" class="panel">
          <div class="goal-top">
            <b>{{ g.name }}</b>
            <span class="goal-type">{{ g.type }}</span>
          </div>
          <div class="goal-progress"><i :style="{ width: (Math.min(g.coverage, 1) * 100) + '%' }"></i></div>
          <div class="kv-grid">
            <div class="kv"><span>目标金额</span><b>{{ fmtMoney(g.target_amount) }}</b></div>
            <div class="kv"><span>已备资金</span><b>{{ fmtMoney(g.current_saved) }}</b></div>
            <div class="kv"><span>资金缺口</span><b>{{ fmtMoney(g.gap) }}</b></div>
            <div class="kv"><span>覆盖度</span><b>{{ fmtPct(g.coverage) }}</b></div>
            <div class="kv"><span>每月需存</span><b>{{ fmtMoney(g.monthly_needed) }}</b></div>
            <div class="kv"><span>目标日期</span><b>{{ g.target_date || '未设期限' }}</b></div>
            <div class="kv"><span>优先级</span><b>{{ PRIORITY_LABELS[g.priority] || '—' }}</b></div>
            <div class="kv"><span>目标类型</span><b>{{ g.goal_kind === 'cashflow' ? '现金流型' : '一次性' }}</b></div>
          </div>
          <div class="goal-actions">
            <button class="btn-mini" @click="askAdvisor(g)">问顾问 · 这个目标怎么完成？</button>
          </div>
        </div>
      </template>
    </div>`,
};
