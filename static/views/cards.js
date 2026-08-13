// 驾驶舱卡片组件（从 cockpit.js 迁移）：只读 overview 对象渲染，零财富计算。
// 派生 computed 仅做格式化/着色/排序，绝不复算任何财富结论。
import { fmtRatio, CLASS_ORDER, CLASS_LABELS, CLASS_COLORS, FINANCIAL_CLASSES, SEV_TONE } from '../format.js';

export const HealthScoreCard = {
  props: { o: Object },
  computed: {
    tone() {
      const s = this.o && this.o.wealth_score;
      if (s == null) return 'neutral';
      return s >= 80 ? 'good' : s >= 60 ? 'warn' : 'bad';
    },
  },
  template: `
    <div class="card card-score">
      <div class="card-title">财富健康度</div>
      <div class="score-big" :class="tone">{{ o.wealth_score }}</div>
      <div class="score-level" :class="tone">{{ o.wealth_level }}</div>
    </div>`,
};

export const NetWorthCard = {
  props: { o: Object },
  template: `
    <div class="card">
      <div class="card-title">净资产</div>
      <div class="big-num">{{ $money(o.net_worth) }}</div>
      <div class="kv"><span>总资产</span><b>{{ $money(o.total_assets) }}</b></div>
      <div class="kv"><span>总负债</span><b>{{ $money(o.total_liabilities) }}</b></div>
      <div class="kv"><span>流动现金</span><b>{{ $money(o.liquid_assets) }}</b></div>
    </div>`,
};

export const CashflowCard = {
  props: { o: Object },
  computed: {
    surplusTone() { return (this.o.cashflow.surplus ?? 0) >= 0 ? 'pos' : 'neg'; },
    srTone() {
      const sr = this.o.cashflow.savings_rate;
      if (sr == null) return '';
      return sr < 0.2 ? 'neg' : 'pos';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">现金流（月）</div>
      <div class="kv"><span>月收入</span><b>{{ $money(o.cashflow.income) }}</b></div>
      <div class="kv"><span>月支出</span><b>{{ $money(o.cashflow.expense) }}</b></div>
      <div class="kv"><span>月结余</span><b :class="surplusTone">{{ $money(o.cashflow.surplus) }}</b></div>
      <div class="kv"><span>储蓄率</span><b :class="srTone">{{ $pct(o.cashflow.savings_rate) }}</b></div>
    </div>`,
};

export const AllocationCard = {
  props: { o: Object },
  computed: {
    classList() {
      const cls = (this.o.asset_allocation && this.o.asset_allocation.classes) || {};
      return CLASS_ORDER.map(k => {
        const entry = cls[k];
        const pct = (entry && typeof entry.pct === 'number') ? entry.pct
                  : (typeof entry === 'number' ? entry : 0);
        return { key: k, label: CLASS_LABELS[k], color: CLASS_COLORS[k], pct };
      });
    },
    fitnessTone() {
      const f = this.o.allocation_fitness;
      if (f == null) return '';
      return f >= 80 ? 'pos' : f >= 60 ? 'warn' : 'neg';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">资产配置 <span class="fitness" :class="fitnessTone">适配度 {{ o.allocation_fitness }}</span></div>
      <div class="alloc-bar">
        <div v-for="c in classList" :key="c.key" class="alloc-seg"
             :style="{ width: (c.pct*100) + '%', background: c.color }" :title="c.label + ' ' + $pct(c.pct)"></div>
      </div>
      <div class="alloc-legend">
        <div v-for="c in classList" :key="c.key" class="legend-item">
          <span class="dot" :style="{ background: c.color }"></span>
          <span class="lbl">{{ c.label }}</span><b>{{ $pct(c.pct) }}</b>
        </div>
      </div>
      <a href="#/health" class="card-link">查看配置体检 →</a>
    </div>`,
};

export const RetirementCard = {
  props: { o: Object },
  computed: {
    r() { return this.o.retirement; },
    quadrantTone() {
      const q = this.r && this.r.quadrant;
      if (q === '养老健康') return 'pos';
      if (q === '未知') return '';
      return 'neg';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">养老准备</div>
      <div v-if="!r" class="empty-hint">录入年龄与支出后可测算养老准备</div>
      <template v-else>
        <div class="kv"><span>RFR（可投资口径）</span><b>{{ fmtRatio(r.rfr) }}</b></div>
        <div class="kv"><span>NWC（净资产口径）</span><b>{{ fmtRatio(r.nwc) }}</b></div>
        <div class="quadrant" :class="quadrantTone">{{ r.quadrant }}</div>
        <div class="kv"><span>退休可投资资产</span><b>{{ $money(r.investable_at_retirement) }}</b></div>
        <div class="kv"><span>退休净资产</span><b>{{ $money(r.net_worth_at_retirement) }}</b></div>
        <div class="kv"><span>退休需求现值</span><b>{{ $money(r.retirement_need_pv) }}</b></div>
      </template>
    </div>`,
  methods: { fmtRatio },
};

export const DebtCard = {
  props: { o: Object },
  computed: {
    dtiTone() {
      const d = this.o.debt.dti;
      if (d == null) return '';
      return d > 0.5 ? 'neg' : d > 0.3 ? 'warn' : 'pos';
    },
  },
  template: `
    <div class="card">
      <div class="card-title">负债</div>
      <div class="kv"><span>总负债</span><b>{{ $money(o.debt.total_debt) }}</b></div>
      <div class="kv"><span>月供</span><b>{{ $money(o.debt.monthly_payment) }}</b></div>
      <div class="kv"><span>DTI（月供/收入）</span><b :class="dtiTone">{{ $pct(o.debt.dti) }}</b></div>
      <div class="kv"><span>保障（保额/年收入）</span><b>{{ fmtRatio(o.protection.coverage_ratio) }}</b></div>
    </div>`,
  methods: { fmtRatio },
};

export const GoalsCard = {
  props: { o: Object },
  template: `
    <div class="card card-goals">
      <div class="card-title">家庭目标</div>
      <div v-if="!o.goals || !o.goals.length" class="empty-hint">尚未设置家庭目标</div>
      <div v-for="g in o.goals" :key="g.goal_id" class="goal-row">
        <div class="goal-top"><b>{{ g.name }}</b><span class="goal-type">{{ g.type }}</span></div>
        <div class="goal-progress"><i :style="{ width: (Math.min(g.coverage,1)*100) + '%' }"></i></div>
        <div class="goal-meta">目标 {{ $money(g.target_amount) }} · 已备 {{ $money(g.current_saved) }} · {{ $pct(g.coverage) }}</div>
      </div>
    </div>`,
};

// AI 家办顾问 · 主动洞察：确定性 build_issues（P0→P2），本阶段不接 LLM。
export const InsightPanel = {
  props: { o: Object },
  computed: {
    issues() { return this.o.issues || []; },
    recommendations() { return this.o.recommendations || []; },
  },
  template: `
    <div class="card card-insight">
      <div class="card-title">AI 家办顾问 · 主动洞察</div>
      <div class="insight-sub">确定性规则引擎 · 优先级 P0 → P2</div>
      <div v-if="!issues.length" class="empty-hint">暂无重大财富问题，家庭财务稳健 🎉</div>
      <template v-else>
        <div v-for="i in issues" :key="i.issue_id" class="insight-item">
          <span class="sev" :class="sevTone(i.severity)">{{ i.severity }}</span>
          <div class="insight-body">
            <div class="insight-title">{{ i.title }}</div>
            <div class="insight-finding" v-if="i.finding">{{ i.finding }}</div>
          </div>
        </div>
        <div v-if="recommendations.length" class="insight-recs">
          <div class="insight-recs-title">建议动作</div>
          <div v-for="r in recommendations" :key="r.recommendation_id || r.action" class="rec-item">
            <span class="rec-action">{{ r.action }}</span>
            <span class="rec-detail">{{ r.detail }}</span>
          </div>
        </div>
      </template>
    </div>`,
  methods: { sevTone: (s) => SEV_TONE[s] || '' },
};
