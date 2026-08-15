// 纯展示格式化工具 + 展示常量：只做格式化/着色，绝不产生任何财富结论。
// 被驾驶舱迁移后的视图（overview/allocation/retirement）与 sandbox 复用。

export function fmtMoney(n) {
  if (n == null || n === '') return '—';
  const v = Number(n);
  const sign = v < 0 ? '-' : '';
  const a = Math.abs(v);
  if (a >= 100000000) return sign + (a / 100000000).toFixed(2) + ' 亿';
  if (a >= 10000) return sign + (a / 10000).toFixed(1) + ' 万';
  return sign + a.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
}

export function fmtPct(r) { return r == null ? '—' : (Number(r) * 100).toFixed(0) + '%'; }

export function fmtRatio(r) { return r == null ? '—' : Number(r).toFixed(2); }

// 六大资产大类（展示顺序 / 标签 / 颜色，与后端 ASSET_CLASSES 对齐）
export const CLASS_ORDER = ['cash', 'fixed_income', 'equity', 'real_estate', 'alternative', 'other'];
export const CLASS_LABELS = { cash: '现金', fixed_income: '固收', equity: '权益', real_estate: '房产', alternative: '另类', other: '其他' };
export const CLASS_COLORS = { cash: '#34c759', fixed_income: '#5ac8fa', equity: '#ff9500', real_estate: '#af52de', alternative: '#ffcc00', other: '#8e8e93' };

// 进入 Σ=100% 点目标的可配置金融资产（与后端 FINANCIAL_TARGET_CLASSES 对齐）
export const FINANCIAL_CLASSES = ['cash', 'fixed_income', 'equity'];

export const SEV_TONE = { P0: 'sev-p0', P1: 'sev-p1', P2: 'sev-p2' };

// 模型能力边界（透传后端 KNOWN_LIMITATIONS，不隐藏）
export const LIMITATION_LABELS = {
  retirement_debt_service_not_included: '退休测算未把既有房贷的月供清偿安排纳入',
  goal_retirement_semantic_overlap: '养老目标与退休测算在口径上存在部分重叠',
  other_asset_liquidity_assumption: '「其他」类资产按不可即时变现处理（流动性假设）',
};

// 情景 → 中文标签（下一步按钮 / 沙盘跳转，纯展示映射，非财富计算）
export const SCENARIO_LABELS = {
  buy_house: '买房',
  prepay: '提前还贷',
  invest: '投资',
  income_change: '收入变化',
};

// 财富健康度等级 → 一句人话结论（体检报告横幅，先结论后数字）
export const LEVEL_CONCLUSION = {
  稳健: '你的家庭财务整体稳健，继续保持。',
  需关注: '你的家庭财务有几个需要关注的地方。',
  脆弱: '你的家庭财务比较脆弱，建议尽快调整。',
};

// 风险维度（与 Decision Layer detect.py 的 7 个 issue type 对齐）：风险地图分组用。
export const ISSUE_DIM_ORDER = ['cashflow', 'liquidity', 'debt', 'allocation', 'retirement', 'goals', 'decision'];
export const ISSUE_DIM_LABELS = {
  cashflow: '现金流', liquidity: '流动性', debt: '负债',
  allocation: '资产配置', retirement: '养老', goals: '目标', decision: '闲置资金',
};
