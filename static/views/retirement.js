// 视图：退休规划（Phase 1 从 cockpit 拆出：养老四象限 + 预测 + 能力边界）。
// 只读 store.overview 的 retirement 区块，零计算。
import { store, ensureOverview } from '../store.js';
import { RetirementCard } from './cards.js';
import { RetirementGap } from '../charts.js';
import { LIMITATION_LABELS } from '../format.js';
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

    // P1 决策闭环出口：看完退休缺口 → 问顾问怎么办。Phase 1b 改结构化上下文：
    //   数字（RFR/NWC/缺口）由 Engine 重算，绝不塞进 payload 或预填问题（T4）。
    function askAdvisor() {
      store.chat.draft = '我的退休准备够不够？';
      store.chat.advisorContext = {
        source: 'retirement',
        intent_hint: 'CHECK_RETIREMENT',
        payload: {},
      };
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
