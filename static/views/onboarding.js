// 冷启动 Humanization：3 步向导（认识家庭 → 粗画像 → 60 秒反馈）。
// 铁律：不落库、不接 LLM、只消费 POST /api/onboarding/preview；
//      财富数字（wealth_score/net_worth/issues）全部由后端 build_overview 实算。
//      反馈明确声明「仅演示，非用户真实财务数据」。
import { store } from '../store.js';
import { api } from '../api.js';
import { fmtMoney } from '../format.js';
import { navigate } from '../router.js';

const { reactive, ref, computed } = Vue;

const INTERESTS = [
  { key: 'asset', label: '买房 / 投资', desc: '首付、房贷、钱生钱' },
  { key: 'goal', label: '养老 / 教育', desc: '退休金、教育金储备' },
  { key: 'safety', label: '现金流 / 负债', desc: '月光、债务压力' },
  { key: 'curious', label: '只是随便看看', desc: '先了解一下' },
];
const DIMENSIONS = [
  { key: 'assets', label: '家庭资产', hint: '房子、存款、投资加起来' },
  { key: 'income', label: '每月收入', hint: '全家月入大概多少' },
  { key: 'debt', label: '家庭负债', hint: '房贷、车贷、信用卡' },
  { key: 'savings', label: '每月结余', hint: '每月能存下多少' },
];
const LEVELS = [
  { v: 'high', l: '很多' }, { v: 'mid', l: '一般' },
  { v: 'low', l: '很少' }, { v: 'unknown', l: '不知道' },
];
// issue type → 领域人话（用于「最大变化空间」解释，纯文案映射，非财富计算）
const TYPE_LABEL = {
  cashflow: '现金流', liquidity: '应急资金', debt: '负债',
  allocation: '资产配置', retirement: '养老', goals: '家庭目标', decision: '闲置资金',
};

export const OnboardingView = {
  setup(_, { emit }) {
    const step = ref(1);
    const interests = reactive({});
    const levels = reactive({ assets: 'unknown', income: 'unknown', debt: 'unknown', savings: 'unknown' });
    const busy = ref(false);
    const error = ref(null);
    const preview = ref(null);

    function next() { step.value++; }
    function back() { step.value = 2; }
    async function runPreview() {
      busy.value = true; error.value = null;
      try {
        preview.value = await api('/api/onboarding/preview', {
          method: 'POST', token: store.auth.token,
          body: { interests: Object.keys(interests).filter(k => interests[k]), profile: { ...levels } },
        });
      } catch (e) { error.value = e.message; }
      finally { busy.value = false; step.value = 3; }
    }
    function finish(goData) {
      localStorage.setItem('onboarded', '1');
      store.onboarded = true;
      emit('done');
      if (goData) navigate('data');
    }

    const o = computed(() => preview.value && preview.value.overview);
    const topIssues = computed(() => {
      const is = o.value && o.value.issues;
      return (is || []).slice(0, 3);
    });
    // 「最大变化空间」解释：取前 2 个问题的领域，去重后拼成人话。
    const focusAreas = computed(() => {
      const seen = [];
      for (const iss of topIssues.value) {
        const label = TYPE_LABEL[iss.type];
        if (label && !seen.includes(label)) seen.push(label);
        if (seen.length >= 2) break;
      }
      return seen;
    });
    const focusText = computed(() => {
      const a = focusAreas.value;
      if (!a.length) return '';
      return '按这个家庭情况看，你现在最大的变化空间可能在「' + a.join('」和「') + '」上。';
    });

    return {
      step, interests, levels, busy, error, preview, o, topIssues, focusText,
      INTERESTS, DIMENSIONS, LEVELS, next, back, runPreview, finish, fmtMoney,
    };
  },
  template: `
  <div class="onboard-mask">
    <div class="onboard-card">
      <div class="onboard-step">第 {{ step }} / 3 步</div>

      <!-- Step 1：认识你的家庭 -->
      <template v-if="step === 1">
        <h2>先认识一下你的家庭 👋</h2>
        <p class="onboard-sub">你最近最关心哪方面？可多选，选错了也没关系。</p>
        <div class="interest-grid">
          <button v-for="it in INTERESTS" :key="it.key" class="interest-card"
                  :class="{ active: interests[it.key] }" @click="interests[it.key] = !interests[it.key]">
            <b>{{ it.label }}</b><span>{{ it.desc }}</span>
          </button>
        </div>
        <button class="btn-primary" @click="next">下一步</button>
      </template>

      <!-- Step 2：粗画像（不知道也没关系） -->
      <template v-else-if="step === 2">
        <h2>大概描述一下你的家庭</h2>
        <p class="onboard-sub">不用精确，凭感觉选就行——「不知道」也没关系。</p>
        <div v-for="d in DIMENSIONS" :key="d.key" class="dim-row">
          <div class="dim-head"><b>{{ d.label }}</b><span>{{ d.hint }}</span></div>
          <div class="level-pills">
            <button v-for="lv in LEVELS" :key="lv.v" class="level-pill"
                    :class="{ active: levels[d.key] === lv.v }" @click="levels[d.key] = lv.v">{{ lv.l }}</button>
          </div>
        </div>
        <div v-if="error" class="form-error">{{ error }}</div>
        <button class="btn-primary" :disabled="busy" @click="runPreview">{{ busy ? '正在生成…' : '看看我的家庭画像' }}</button>
      </template>

      <!-- Step 3：60 秒反馈 -->
      <template v-else>
        <h2>这是你现在的家庭画像</h2>
        <template v-if="o">
          <div class="profile-hero">
            <div class="profile-score"><b>{{ o.wealth_score }}</b><span>财富评分</span></div>
            <div class="profile-net">净资产 {{ fmtMoney(o.net_worth) }}<span class="profile-level">{{ o.wealth_level }}</span></div>
          </div>
          <p v-if="focusText" class="profile-focus">{{ focusText }}</p>
          <div class="profile-issues" v-if="topIssues.length">
            <div class="profile-issues-title">先留意这 {{ topIssues.length }} 件事</div>
            <div v-for="(iss, i) in topIssues" :key="iss.issue_id" class="profile-issue">
              <span class="issue-rank">{{ i + 1 }}</span>{{ iss.title }}
            </div>
          </div>
          <p class="onboard-note">这只是根据你刚才选的典型情况做的演示，换成你的真实数据，结论可能完全不同。</p>
        </template>
        <div v-else-if="error" class="form-error">{{ error }}</div>
        <div class="onboard-cta">
          <button class="btn-primary" @click="finish(true)">录入我的真实数据</button>
          <button class="btn-ghost" @click="back">换一个家庭情况看看</button>
          <button class="btn-link" @click="finish(false)">先看看产品</button>
        </div>
      </template>
    </div>
  </div>`,
};
