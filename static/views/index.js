// 视图注册表：hash 路径 → Vue 组件 + 侧边栏导航元数据。
// 迁移进度：Phase 0 全为占位；Phase 1~4 逐个替换为真实视图（见 docs/plan-c5-*）。
import { OverviewView } from './overview.js';
import { HealthView } from './health.js';
import { AllocationView } from './allocation.js';
import { RetirementView } from './retirement.js';
import { GoalsView } from './goals.js';
import { IssuesView } from './issues.js';
import { SandboxView } from './sandbox.js';
import { ChatView } from './chat.js';
import { DataView } from './data.js';

export const VIEWS = {
  overview: OverviewView,
  health: HealthView,
  allocation: AllocationView,
  retirement: RetirementView,
  goals: GoalsView,
  issues: IssuesView,
  sandbox: SandboxView,
  chat: ChatView,
  data: DataView,
};

export const NAV_ITEMS = [
  { route: 'overview', label: '家庭总览', icon: 'home' },
  { route: 'data', label: '家庭数据', icon: 'data' },
  { route: 'health', label: '财富健康', icon: 'health' },
  { route: 'allocation', label: '资产配置', icon: 'allocation' },
  { route: 'retirement', label: '退休规划', icon: 'retirement' },
  { route: 'goals', label: '家庭目标', icon: 'goals' },
  { route: 'issues', label: '风险问题', icon: 'issues' },
  { route: 'sandbox', label: '情景沙盘', icon: 'sandbox' },
  { route: 'chat', label: 'AI 顾问', icon: 'chat' },
];
