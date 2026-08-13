// 依赖-free 的 hash 路由：只维护「当前路由」响应式状态 + navigate。
// 视图注册表在 views/index.js 的 VIEWS 里（shell.js 据此解析当前视图组件）。
const { ref } = Vue;

function parseHash() {
  const h = location.hash.replace(/^#\/?/, '');
  return h || 'overview';
}

export const currentRoute = ref(parseHash());

export function navigate(path) {
  if (currentRoute.value === path) return;
  location.hash = '#/' + path;
}

window.addEventListener('hashchange', () => {
  currentRoute.value = parseHash();
});
