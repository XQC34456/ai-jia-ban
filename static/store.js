// 前端单一事实源：Vue reactive 单例。
// overview 只来自 /api/wealth/overview；任何派生 computed 只做展示，绝不产生财富结论。
import { api } from './api.js';

const { reactive, computed } = Vue;

export const store = reactive({
  auth: { token: localStorage.getItem('token') || null, username: '', tier: 'free' },
  overview: null,      // 全量驾驶舱状态（唯一数据源）
  loading: false,
  error: null,
});

function applySession(r) {
  store.auth.token = r.token;
  store.auth.username = r.username;
  store.auth.tier = r.tier;
  localStorage.setItem('token', r.token);
}

export async function login(username, password) {
  const r = await api('/api/login', { method: 'POST', body: { username, password } });
  applySession(r);
  return r;
}

export async function register(username, password) {
  const r = await api('/api/register', { method: 'POST', body: { username, password } });
  applySession(r);
  return r;
}

export function logout() {
  store.auth.token = null;
  store.auth.username = '';
  store.auth.tier = 'free';
  store.overview = null;
  localStorage.removeItem('token');
}

export async function loadOverview() {
  store.loading = true;
  store.error = null;
  try {
    store.overview = await api('/api/wealth/overview', { token: store.auth.token });
  } catch (e) {
    store.error = e.message;
    if (e.status === 401) { store.auth.token = null; localStorage.removeItem('token'); }
    throw e;
  } finally {
    store.loading = false;
  }
}

// ---------- 派生（纯展示：格式化/阈值着色，不重算财富） ----------

export const loggedIn = computed(() => !!store.auth.token);

export const scoreTone = computed(() => {
  const s = store.overview && store.overview.wealth_score;
  if (s == null) return 'neutral';
  return s >= 80 ? 'good' : s >= 60 ? 'warn' : 'bad';
});
