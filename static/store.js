// 前端单一事实源：Vue reactive 单例，按「切片」模块化组织。
// 铁律：
//   - overview 只来自 /api/wealth/overview；goals / issues / sandbox / chat 各有独立切片与端点，
//     不把所有数据硬塞进 overview。
//   - 任何派生 computed 只做展示（格式化/排序/筛选/着色），绝不产生财富结论。
//   - 向后兼容：store.auth / store.overview / store.loading / store.error 保留给未迁移的
//     cockpit/sandbox/xray 使用（迁移完成后统一收进各自切片）。
import { api } from './api.js';

const { reactive, computed } = Vue;

export const store = reactive({
  auth: { token: localStorage.getItem('token') || null, username: '', tier: 'free' },

  // —— 切片：驾驶舱核心（唯一财富事实源；loading/error 为向后兼容别名）——
  overview: null,
  loading: false,
  error: null,

  // —— 切片：家庭目标（独立端点，lazy load）——
  goals: { data: null, loading: false, error: null },

  // —— 切片：风险问题（独立端点，lazy load）——
  issues: { data: null, loading: false, error: null },

  // —— 切片：情景沙盘（单次模拟 + 多方案对比）——
  sandbox: { result: null, comparison: null, loading: false, error: null },

  // —— 切片：AI 顾问对话（Phase 4 迁移 vanilla chat 后启用）——
  chat: { messages: [], loading: false, error: null },
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
  store.goals.data = null;
  store.issues.data = null;
  store.sandbox.result = null;
  store.sandbox.comparison = null;
  store.chat.messages = [];
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

export async function upgrade() {
  const r = await api('/api/upgrade', { method: 'POST', token: store.auth.token });
  store.auth.tier = r.tier || 'vip';
  return r;
}

export async function loadGoals() {
  store.goals.loading = true;
  store.goals.error = null;
  try {
    store.goals.data = await api('/api/wealth/goals', { token: store.auth.token });
  } catch (e) {
    store.goals.error = e.message;
    throw e;
  } finally {
    store.goals.loading = false;
  }
}

export async function loadIssues() {
  store.issues.loading = true;
  store.issues.error = null;
  try {
    store.issues.data = await api('/api/wealth/issues', { token: store.auth.token });
  } catch (e) {
    store.issues.error = e.message;
    throw e;
  } finally {
    store.issues.loading = false;
  }
}

// ---------- 派生（纯展示：格式化/阈值着色，不重算财富） ----------

export const loggedIn = computed(() => !!store.auth.token);

export const scoreTone = computed(() => {
  const s = store.overview && store.overview.wealth_score;
  if (s == null) return 'neutral';
  return s >= 80 ? 'good' : s >= 60 ? 'warn' : 'bad';
});
