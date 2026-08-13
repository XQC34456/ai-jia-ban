// 视图：退休规划（Phase 1 从 cockpit 拆出：养老四象限 + 预测 + 能力边界）。
// 只读 store.overview 的 retirement 区块，零计算。
import { store, ensureOverview } from '../store.js';
import { RetirementCard } from './cards.js';
import { LIMITATION_LABELS } from '../format.js';

const { onMounted, computed } = Vue;

export const RetirementView = {
  components: { RetirementCard },
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });

    const limitations = computed(() => {
      const r = store.overview && store.overview.retirement;
      return (r && r.known_limitations) || [];
    });
    function limitationLabel(k) { return LIMITATION_LABELS[k] || k; }

    return { store, limitations, limitationLabel };
  },
  template: `
    <div class="view">
      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
      <template v-else-if="store.overview">
        <retirement-card :o="store.overview" />
        <div v-if="limitations.length" class="card">
          <div class="card-title">模型能力边界</div>
          <ul class="limits-list">
            <li v-for="k in limitations" :key="k">{{ limitationLabel(k) }}</li>
          </ul>
        </div>
      </template>
    </div>`,
};
