// 视图：资产配置（Phase 1 从 cockpit 拆出：6 大类占比 + 金融目标 vs 当前）。
// 只读 store.overview 的 asset_allocation / allocation_fitness / allocation_target，零计算。
import { store, ensureOverview } from '../store.js';
import { AllocationCard } from './cards.js';
import { CLASS_LABELS, CLASS_COLORS, FINANCIAL_CLASSES } from '../format.js';

const { onMounted, computed } = Vue;

export const AllocationView = {
  components: { AllocationCard },
  setup() {
    onMounted(() => { ensureOverview().catch(() => {}); });

    const finCompare = computed(() => {
      const o = store.overview;
      if (!o) return [];
      const financial = (o.asset_allocation && o.asset_allocation.financial_pct) || {};
      const target = o.allocation_target || {};
      return FINANCIAL_CLASSES.map(k => ({
        key: k,
        label: CLASS_LABELS[k],
        color: CLASS_COLORS[k],
        current: typeof financial[k] === 'number' ? financial[k] : 0,
        target: typeof target[k] === 'number' ? target[k] : null,
      }));
    });

    return { store, finCompare };
  },
  template: `
    <div class="view">
      <div v-if="store.loading" class="state-hint">加载中…</div>
      <div v-else-if="store.error" class="state-hint error">{{ store.error }}</div>
      <template v-else-if="store.overview">
        <allocation-card :o="store.overview" />
        <div class="card">
          <div class="card-title">可配置金融资产 · 目标 vs 当前</div>
          <div class="fin-row" v-for="f in finCompare" :key="f.key">
            <span class="fin-lbl"><span class="dot" :style="{ background: f.color }"></span>{{ f.label }}</span>
            <div class="fin-bar"><i :style="{ width: (f.current*100) + '%', background: f.color }"></i></div>
            <span class="fin-val">当前 {{ $pct(f.current) }} · 目标 {{ $pct(f.target) }}</span>
          </div>
          <div class="fin-note">目标口径为现金/固收/权益在「金融资产合计」中的占比；房产/另类/其他不计入。</div>
        </div>
      </template>
    </div>`,
};
