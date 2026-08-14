// 确定性「决策解释层」：把后端已算好的 comparison + Overview.issues 翻译成自然语言。
//
// 铁律（可读不可算）：
//  1. 只读 comparison（后端已算好的 baseline/option/delta）+ baseline/option 的 issues 标题。
//  2. 只做「取符号 + 阈值比较 + 字符串模板」，绝不计算 wealth_score/RFR/NWC/DTI/占比 等任何财富指标。
//  3. 不生成「最佳方案」结论；差异有限就明说差异有限；有取舍就明说无绝对更优。
//  4. 本模块零 import，纯函数，可被 Node 直接单测（node --test）。

// 定位徽标
export const POSITION = {
  richer:   { key: 'richer',   label: '更有钱' },
  safer:    { key: 'safer',    label: '更安全' },
  balanced: { key: 'balanced', label: '更富也更稳' },
  tradeoff: { key: 'tradeoff', label: '有取舍' },
  no_diff:  { key: 'no_diff',  label: '变化有限' },
};

// 「有意义变化」阈值（呈现启发式，非财富计算；可调）。
// money=元, score=分, ratio=比率, months=月, pct=比率（0-1，1% 即 0.01）。
const ABS = { money: 1000, score: 1, ratio: 0.02, months: 1.0, pct: 0.01 };
const REL = 0.01; // 相对 1%

// 维度方向分类（real_estate_pct 中性，不参与方向判定）
const RICH = new Set(['net_worth', 'wealth_score']);
const SAFE_UP = new Set(['rfr', 'nwc', 'cashflow', 'liquidity', 'goal_completion']);
const SAFE_DOWN = new Set(['dti']);

const CLASS_LABEL = {
  cash: '现金', fixed_income: '固收', equity: '权益',
  real_estate: '房产', alternative: '另类', other: '其他',
};

function fmtWan(v) {
  const w = v / 10000;
  return w.toFixed(Math.abs(w % 1) < 1e-9 ? 0 : 1);
}

function meaningful(row) {
  if (row.delta == null) return false;
  const abs = ABS[row.unit] ?? 1;
  if (Math.abs(row.delta) < abs) return false;
  if (row.baseline == null || Math.abs(row.baseline) < 1e-9) return true;
  return Math.abs(row.delta) / Math.abs(row.baseline) >= REL;
}

function meaningfulChanges(cmp) {
  return (cmp || []).filter(meaningful);
}

// 展示用：按相对变化率降序，取变化最显著的 top 4（跨单位可比）。
// 仅用于叙事卡「关键变化」，classifyPosition 仍用未截断的 meaningfulChanges。
function _significance(row) {
  const base = Math.abs(row.baseline);
  return Math.abs(row.delta) / (base > 1e-9 ? base : 1);
}
function topChanges(cmp) {
  return meaningfulChanges(cmp)
    .sort((a, b) => _significance(b) - _significance(a))
    .slice(0, 4);
}

export function classifyPosition(cmp) {
  const ch = meaningfulChanges(cmp);
  if (!ch.length) return POSITION.no_diff;
  let wealth = 0, safe = 0;
  for (const r of ch) {
    const s = Math.sign(r.delta);
    if (RICH.has(r.key)) wealth += s;
    else if (SAFE_UP.has(r.key)) safe += s;
    else if (SAFE_DOWN.has(r.key)) safe -= s;
    // real_estate_pct 中性，不计方向
  }
  const W = Math.sign(wealth), S = Math.sign(safe);
  if (W > 0 && S > 0) return POSITION.balanced;
  if (W > 0 && S < 0) return POSITION.tradeoff;
  if (W < 0 && S > 0) return POSITION.tradeoff;
  if (W > 0) return POSITION.richer;
  if (S > 0) return POSITION.safer;
  if (W < 0 || S < 0) return POSITION.tradeoff;
  return POSITION.no_diff;
}

function summary(scenario, opt) {
  const p = opt.params || {};
  switch (scenario) {
    case 'buy_house':
      return `购入房产 ${fmtWan(p.price)} 万元，首付 ${Math.round((p.down_payment_ratio ?? 0.3) * 100)}%，贷款 ${p.loan_years ?? 30} 年`;
    case 'prepay':
      return `提前还贷 ${fmtWan(p.prepay_amount)} 万元（${(p.method === 'reduce_payment') ? '减少月供' : '缩短年限'}）`;
    case 'invest':
      return `将 ${fmtWan(p.amount)} 万元现金投入${CLASS_LABEL[p.to_class] || p.to_class}`;
    case 'income_change': {
      const pct = Math.round((p.pct_change ?? 0) * 100);
      return `收入变动 ${pct >= 0 ? '+' : ''}${pct}%`;
    }
    default:
      return '情景模拟';
  }
}

function headline(position) {
  switch (position.key) {
    case 'richer': return '这个方案更偏向让钱变多。';
    case 'safer': return '这个方案更偏向把风险降下来。';
    case 'balanced': return '钱和安全感都在变好。';
    case 'tradeoff': return '有的变好、有的变差，没有绝对更优——看你在乎什么。';
    case 'no_diff': return '和现在差别不大，暂无明显优劣。';
    default: return '';
  }
}

function riskNote(cmp) {
  const get = k => (cmp || []).find(r => r.key === k);
  const liq = get('liquidity'), dti = get('dti'), cf = get('cashflow'), rfr = get('rfr');
  const risks = [];
  if (liq && liq.option != null && liq.option < 3) risks.push('应急资金已跌破 3 个月安全线');
  else if (liq && liq.option != null && liq.option < 6) risks.push('应急资金低于 6 个月安全线');
  if (dti && dti.option != null && dti.option > 0.5) risks.push('负债率超过 50% 警戒线');
  if (cf && cf.option != null && cf.option < 0) risks.push('月度现金流为负');
  if (rfr && rfr.option != null && rfr.option < 1) risks.push('退休后能用的钱可能不够花');
  return risks.length ? risks.join('；') : null;
}

function issueDelta(baseline, option) {
  const base = new Map((baseline.issues || []).map(i => [i.issue_id, i.title]));
  const opt = new Map((option.issues || []).map(i => [i.issue_id, i.title]));
  const resolved = [], added = [];
  for (const [id, title] of base) if (!opt.has(id)) resolved.push(title);
  for (const [id, title] of opt) if (!base.has(id)) added.push(title);
  return { resolved, added };
}

// 主入口：把后端 compare 结果翻译成人话，绝不重算财富。
export function interpret(scenario, opt, baseline, option, cmp) {
  const position = classifyPosition(cmp);
  return {
    summary: summary(scenario, opt),
    position,
    headline: headline(position),
    risk: riskNote(cmp),
    changes: topChanges(cmp),
    issueDelta: issueDelta(baseline, option),
  };
}
