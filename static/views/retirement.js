// 视图：退休规划（Phase 1 从 cockpit 拆出：养老四象限 + 预测 + 能力边界）。
// 只读 store.overview 的 retirement 区块，零计算。
import { store, ensureOverview } from '../store.js';
import { RetirementCard } from './cards.js';
import { RetirementGap } from '../charts.js';
import { LIMITATION_LABELS, fmtMoney } from '../format.js';
import { navigate } from '../router.js';

const { onMounted, computed } = Vue;

export const RetirementView = {
  components: { RetirementCard, RetirementGap },
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });

    const limitations = computed(() => {
      const r = store.overview && store.overview.retirement;
      return (r && r.known_limitations) || [];
    });
    function limitationLabel(k) { return LIMITATION_LABELS[k] || k; }

    // P1 决策闭环出口：看完退休缺口 → 问顾问怎么办。数字只读后端 retirement 块，零计算。
    function askAdvisor() {
      const r = store.overview && store.overview.retirement;
      const inv = r ? fmtMoney(r.investable_at_retirement) : '—';
      const need = r ? fmtMoney(r.retirement_need_pv) : '—';
      store.chat.draft = '我的退休准备缺口怎么补？当前退休可投资资产 ' + inv
        + '，退休需求现值 ' + need + '，请帮我看看怎么办。';
      navigate('chat');
    }

    return { store, limitations, limitationLabel, askAdvisor };
  },
  template: `
    <div class="view view-sm">
      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
      <template v-else-if="store.overview">
        <section class="panel">
          <div class="card-title">退休缺口 · 资产能否覆盖退休需求？</div>
          <retirement-gap :data="store.overview.retirement" />
        </section>
        <retirement-card :o="store.overview" />
        <div class="panel">
          <button class="btn-mini" @click="askAdvisor">问顾问 · 我的退休缺口怎么办？</button>
        </div>
        <div v-if="limitations.length" class="card">
          <div class="card-title">模型能力边界</div>
          <ul class="limits-list">
            <li v-for="k in limitations" :key="k">{{ limitationLabel(k) }}</li>
          </ul>
        </div>
      </template>
    </div>`,
};
