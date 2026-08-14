// scenario-interpret.js 的 Node 单测：锁死「可读不可算 + 顾问感不排名」。
//
// 铁律（与实现互为印证）：
//  1. interpret 只读 comparison（后端已算好的 baseline/option/delta）+ issues 标题，
//     绝不重新计算任何财富指标。
//  2. 差异有限 → 「变化有限」，绝不生成「方案更优」结论。
//  3. 有取舍（trade-off）→ 多维展示 + 「无绝对更优」提示，不按总分排名。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { interpret, POSITION } from '../../static/lib/scenario-interpret.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------- 构造 comparison 行（delta 与后端一致：option - baseline） ----------
function row(key, label, unit, baseline, option) {
  const delta = (baseline == null || option == null) ? null : Math.round((option - baseline) * 1e4) / 1e4;
  return { key, label, unit, baseline, option, delta };
}

const OPT = { id: 'A', name: '方案 A', params: { amount: 300000, to_class: 'equity' } };

function issue(id, title, severity) { return { issue_id: id, title, severity }; }
function overview(issues) { return { issues }; }

// ---------- 1. 定位：更有钱 ----------
test('position=richer 当财富维度显著改善且安全未恶化', () => {
  const cmp = [
    row('net_worth', '净资产', 'money', 5000000, 5000000),
    row('wealth_score', '财富评分', 'score', 81, 85),   // +4 分
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.1),
    row('nwc', '养老净资产覆盖 NWC', 'ratio', 2.0, 2.0),
    row('cashflow', '月度现金流结余', 'money', 30000, 30000),
    row('liquidity', '应急资金（月）', 'months', 15, 14.6),  // -0.4 月（低于阈值）
    row('dti', '负债率 DTI', 'pct', 0.16, 0.16),
    row('real_estate_pct', '房产占比', 'pct', 0.5, 0.5),
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.6),
  ];
  const out = interpret('invest', OPT, overview([]), overview([]), cmp);
  assert.equal(out.position.key, 'richer');
});

// ---------- 2. 定位：更安全 ----------
test('position=safer 当 DTI 下降、流动性上升且财富未恶化', () => {
  const cmp = [
    row('net_worth', '净资产', 'money', 5000000, 5000000),
    row('wealth_score', '财富评分', 'score', 81, 81),   // 财富持平
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.15),
    row('nwc', '养老净资产覆盖 NWC', 'ratio', 2.0, 2.05),
    row('cashflow', '月度现金流结余', 'money', 30000, 32000),
    row('liquidity', '应急资金（月）', 'months', 12, 14),   // +2 月
    row('dti', '负债率 DTI', 'pct', 0.42, 0.28),           // -14pp
    row('real_estate_pct', '房产占比', 'pct', 0.5, 0.5),
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.6),
  ];
  const out = interpret('prepay', OPT, overview([]), overview([]), cmp);
  assert.equal(out.position.key, 'safer');
});

// ---------- 2b. 定位：更富也更稳（财富与安全同向改善） ----------
test('position=balanced 当财富与安全同时改善', () => {
  const cmp = [
    row('net_worth', '净资产', 'money', 5000000, 5000000),
    row('wealth_score', '财富评分', 'score', 81, 84),   // +3 分
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.15),
    row('nwc', '养老净资产覆盖 NWC', 'ratio', 2.0, 2.0),
    row('cashflow', '月度现金流结余', 'money', 30000, 32000),
    row('liquidity', '应急资金（月）', 'months', 12, 14),   // +2 月
    row('dti', '负债率 DTI', 'pct', 0.42, 0.28),           // -14pp
    row('real_estate_pct', '房产占比', 'pct', 0.5, 0.5),
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.6),
  ];
  const out = interpret('prepay', OPT, overview([]), overview([]), cmp);
  assert.equal(out.position.key, 'balanced');
});

// ---------- 3. 顾问感：差异有限，绝不生成「更优」 ----------
test('差异有限 → 变化有限，且不出现「更优/最佳」结论', () => {
  const cmp = [
    row('net_worth', '净资产', 'money', 5000000, 5000000),
    row('wealth_score', '财富评分', 'score', 81, 81),
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.1),
    row('nwc', '养老净资产覆盖 NWC', 'ratio', 2.0, 2.0),
    row('cashflow', '月度现金流结余', 'money', 30000, 30000),
    row('liquidity', '应急资金（月）', 'months', 15, 15),
    row('dti', '负债率 DTI', 'pct', 0.16, 0.16),
    row('real_estate_pct', '房产占比', 'pct', 0.5, 0.5),
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.6),
  ];
  const out = interpret('invest', OPT, overview([]), overview([]), cmp);
  assert.equal(out.position.key, 'no_diff');
  assert.equal(out.changes.length, 0);
  // 顾问感：不能出现「更优」「最佳」「明显更好」这类强行排名字眼
  const text = [out.headline, out.summary].join(' ');
  assert.ok(!/更优|最佳|明显更好|最优/.test(text), `不应出现排名字眼，实际: ${text}`);
});

// ---------- 4. 顾问感：trade-off 多维展示 + 无绝对更优 ----------
test('trade-off（财富↑流动性↓）→ 有取舍 + 无绝对更优提示', () => {
  const cmp = [
    row('net_worth', '净资产', 'money', 5000000, 5000000),
    row('wealth_score', '财富评分', 'score', 81, 86),      // +5 分
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.1),
    row('nwc', '养老净资产覆盖 NWC', 'ratio', 2.0, 2.0),
    row('cashflow', '月度现金流结余', 'money', 30000, 30000),
    row('liquidity', '应急资金（月）', 'months', 8, 5),     // -3 月，跌破 6 月
    row('dti', '负债率 DTI', 'pct', 0.16, 0.16),
    row('real_estate_pct', '房产占比', 'pct', 0.5, 0.5),
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.6),
  ];
  const out = interpret('invest', OPT, overview([]), overview([]), cmp);
  assert.equal(out.position.key, 'tradeoff');
  assert.match(out.headline, /没有绝对更优|取舍/);
  // 多维展示：财富↑ 与 流动性↓ 两个方向都要在 changes 里
  const keys = out.changes.map(c => c.key);
  assert.ok(keys.includes('wealth_score'));
  assert.ok(keys.includes('liquidity'));
});

// ---------- 5. 风险变化：问题消除/新增（差集一致） ----------
test('issueDelta 严格等于 baseline 与 option 的差集', () => {
  const baseline = overview([issue('DEBT_HIGH_001', '负债压力过大', 'P0'), issue('LIQUIDITY_LOW_001', '应急资金偏低', 'P1')]);
  const option = overview([issue('DEBT_HIGH_001', '负债压力过大', 'P0'), issue('GOALS_GAP_001', '首付存在资金缺口', 'P2')]);
  const cmp = [];
  const out = interpret('prepay', OPT, baseline, option, cmp);
  assert.deepEqual(out.issueDelta.resolved, ['应急资金偏低']);
  assert.deepEqual(out.issueDelta.added, ['首付存在资金缺口']);
});

// ---------- 6. 风险提示：跨越安全线才提示 ----------
test('risk 仅在跨越安全线时提示（流动性<6 / DTI>50% / 现金流为负）', () => {
  const safe = [
    row('liquidity', '应急资金（月）', 'months', 10, 8),
    row('dti', '负债率 DTI', 'pct', 0.2, 0.2),
    row('cashflow', '月度现金流结余', 'money', 30000, 30000),
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.1),
  ];
  assert.equal(interpret('invest', OPT, overview([]), overview([]), safe).risk, null);

  const risky = [
    row('liquidity', '应急资金（月）', 'months', 10, 2.5),
    row('dti', '负债率 DTI', 'pct', 0.2, 0.55),
    row('cashflow', '月度现金流结余', 'money', 30000, -5000),
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 0.8),
  ];
  const r = interpret('invest', OPT, overview([]), overview([]), risky).risk;
  assert.match(r, /3 个月|50%|现金流为负|不够/);
});

// ---------- 6b. 关键变化：按相对变化率排序 + 截断 top 4 ----------
test('changes 按相对变化率降序，且只留变化最显著的 top 4', () => {
  const cmp = [
    row('liquidity', '应急资金（月）', 'months', 12, 14),       // |2|/12 ≈ 0.167
    row('dti', '负债率 DTI', 'pct', 0.42, 0.28),               // |0.14|/0.42 ≈ 0.333（最大）
    row('wealth_score', '财富评分', 'score', 81, 84),          // |3|/81 ≈ 0.037
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.75),    // |0.15|/0.6 = 0.25
    row('cashflow', '月度现金流结余', 'money', 30000, 32000),  // |2000|/30000 ≈ 0.067
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.15),      // |0.05|/2.1 ≈ 0.024
  ];
  const out = interpret('prepay', OPT, overview([]), overview([]), cmp);
  assert.equal(out.changes.length, 4);
  assert.deepEqual(out.changes.map(c => c.key), ['dti', 'goal_completion', 'liquidity', 'cashflow']);
});

// ---------- 7. 可读不可算：模块源码无财富算式 + 输出数字全部来自入参 ----------
test('可读不可算：源码不含财富算式，输出不凭空造数', () => {
  const src = readFileSync(join(__dirname, '..', '..', 'static', 'lib', 'scenario-interpret.js'), 'utf8');
  // 源码不得出现幂/指数/折现/净资产重算等财富算式
  assert.ok(!/\*\*|Math\.pow|Math\.exp|Math\.log|Math\.sqrt/.test(src), '源码含财富算式');

  const cmp = [
    row('net_worth', '净资产', 'money', 5000000, 5000000),
    row('wealth_score', '财富评分', 'score', 81, 85),
    row('rfr', '养老可投资覆盖 RFR', 'ratio', 2.1, 2.15),
    row('nwc', '养老净资产覆盖 NWC', 'ratio', 2.0, 2.05),
    row('cashflow', '月度现金流结余', 'money', 30000, 32000),
    row('liquidity', '应急资金（月）', 'months', 12, 14),
    row('dti', '负债率 DTI', 'pct', 0.42, 0.28),
    row('real_estate_pct', '房产占比', 'pct', 0.5, 0.5),
    row('goal_completion', '目标完成度', 'pct', 0.6, 0.6),
  ];
  const out = interpret('prepay', OPT, overview([]), overview([]), cmp);
  // changes 里的每个数字都必须等于入参 cmp 里的 baseline/option/delta 之一
  const inputVals = new Set(cmp.flatMap(r => [r.baseline, r.option, r.delta]));
  for (const c of out.changes) {
    assert.ok(inputVals.has(c.delta), `delta 非入参值: ${c.key}=${c.delta}`);
    assert.ok(inputVals.has(c.baseline) && inputVals.has(c.option));
  }
});

// ---------- 8. 四个场景的「发生了什么」人话摘要 ----------
test('summary 按场景输出人话（含参数）', () => {
  const cases = [
    ['buy_house', { params: { price: 3000000, down_payment_ratio: 0.3, loan_years: 30 } }, /购入房产/],
    ['prepay', { params: { prepay_amount: 500000, method: 'shorten' } }, /提前还贷/],
    ['invest', { params: { amount: 300000, to_class: 'equity' } }, /权益/],
    ['income_change', { params: { pct_change: 0.1 } }, /\+10%/],
  ];
  for (const [scenario, opt, re] of cases) {
    const out = interpret(scenario, { id: 'A', name: 'A', ...opt }, overview([]), overview([]), []);
    assert.match(out.summary, re, `${scenario} summary 不符`);
  }
});
