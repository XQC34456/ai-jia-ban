// 统一 App Shell：Topbar + Sidebar + Main（hash 路由视图容器）+ 登录门。
// 铁律：本文件只做「壳」的布局与导航，不做任何财富计算；数据一律来自 store 各切片。
import { store, loggedIn, login, register, logout, upgrade } from './store.js';
import { currentRoute, navigate } from './router.js';
import { VIEWS, NAV_ITEMS } from './views/index.js';
import { icon } from './icons.js';
import { fmtMoney, fmtPct } from './format.js';

const { createApp, ref, computed, onMounted } = Vue;

const currentView = computed(() => VIEWS[currentRoute.value] || VIEWS.overview);
const currentLabel = computed(() => {
  const item = NAV_ITEMS.find((n) => n.route === currentRoute.value);
  return item ? item.label : '家庭总览';
});

// ---------- 登录 / 注册 ----------
const LoginView = {
  setup() {
    const mode = ref('login');
    const username = ref('');
    const password = ref('');
    const err = ref('');
    const busy = ref(false);
    async function submit() {
      if (!username.value.trim() || !password.value) { err.value = '请填写用户名和密码'; return; }
      busy.value = true; err.value = '';
      try {
        if (mode.value === 'login') await login(username.value.trim(), password.value);
        else await register(username.value.trim(), password.value);
      } catch (e) {
        err.value = e.message || '操作失败';
      } finally { busy.value = false; }
    }
    return { mode, username, password, err, busy, submit };
  },
  template: `
    <div class="login-mask">
      <div class="login-card">
        <div class="login-brand"><span class="brand-logo">🏠</span><div><h1>AI 家办</h1><p>家庭财富智管家</p></div></div>
        <div class="login-sub">{{ mode === 'login' ? '登录后管理你的家庭财富' : '注册即开始管理你的家庭财富' }}</div>
        <div class="form-error" v-if="err">{{ err }}</div>
        <label class="field"><span>用户名</span><input v-model="username" placeholder="字母/数字/中文" autocomplete="username" /></label>
        <label class="field"><span>密码</span><input v-model="password" type="password" placeholder="至少 6 位" autocomplete="current-password" /></label>
        <button class="btn-primary" :disabled="busy" @click="submit">{{ busy ? '请稍候…' : (mode === 'login' ? '登 录' : '注 册') }}</button>
        <div class="login-switch">
          <span v-if="mode === 'login'">还没有账号？<a @click="mode='register';err=''">免费注册</a></span>
          <span v-else>已有账号？<a @click="mode='login';err=''">去登录</a></span>
        </div>
      </div>
    </div>`,
};

// ---------- 顶栏 ----------
const Topbar = {
  setup() {
    const llm = ref(null);   // true=已接入 / false=兜底
    onMounted(async () => {
      try {
        const h = await fetch('/api/health').then((r) => r.json());
        llm.value = !!h.llm;
      } catch { llm.value = false; }
    });
    return { store, currentLabel, logout, upgrade, llm };
  },
  template: `
    <header class="topbar">
      <div class="brand"><span class="brand-logo">🏠</span><b>AI 家办</b></div>
      <div class="breadcrumb">首页 <span class="sep">/</span> <em>{{ currentLabel }}</em></div>
      <div class="topbar-right">
        <span class="llm-badge">{{ llm == null ? 'AI 引擎：检测中…' : (llm ? 'AI 引擎：已接入大模型' : 'AI 引擎：规则兜底') }}</span>
        <span class="user-name">{{ store.auth.username }}</span>
        <span :class="store.auth.tier === 'vip' ? 'tag-vip' : 'tag-free'">{{ store.auth.tier === 'vip' ? 'VIP' : '免费' }}</span>
        <button v-if="store.auth.tier !== 'vip'" class="btn-ghost" @click="upgrade()">升级 VIP</button>
        <button class="btn-ghost" @click="logout()">退出</button>
      </div>
    </header>`,
};

// ---------- 侧边栏 ----------
const Sidebar = {
  props: { items: Array, current: String },
  setup() {
    return { navigate, icon };
  },
  template: `
    <nav class="sidebar">
      <a v-for="it in items" :key="it.route" class="nav-item" :class="{ active: current === it.route }"
         @click="navigate(it.route)">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round" v-html="icon(it.icon)"></svg>
        <span>{{ it.label }}</span>
      </a>
    </nav>`,
};

// ---------- 根组件 ----------
const App = {
  components: { LoginView, Topbar, Sidebar },
  setup() {
    return { loggedIn, currentView, currentRoute, NAV_ITEMS };
  },
  template: `
    <login-view v-if="!loggedIn"></login-view>
    <div v-else class="shell">
      <topbar></topbar>
      <div class="shell-body">
        <sidebar :items="NAV_ITEMS" :current="currentRoute"></sidebar>
        <main class="shell-main"><component :is="currentView"></component></main>
      </div>
    </div>`,
};

const app = createApp(App);
// 全局展示格式化（纯格式化，不产生财富结论），供卡片模板 $money / $pct 使用。
app.config.globalProperties.$money = fmtMoney;
app.config.globalProperties.$pct = fmtPct;
app.mount('#app');
