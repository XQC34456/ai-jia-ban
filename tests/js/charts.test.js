// P2 图表·纯展示归一化单测：利率展示必须兼容「百分数(3.5)/小数(0.035)」两种后端透传值。
// 与 Engine _rate 口径一致（>1 视为百分数），只做展示格式化，非财富计算。
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const src = readFileSync(join(ROOT, 'static', 'charts.js'), 'utf8');

test('ratePct 按 >1 归一化利率（百分数/小数双兼容），非硬编码 *100', () => {
  assert.ok(src.includes('ratePct'), 'charts.js 应定义 ratePct 展示归一化');
  // 归一化核心：r > 1 ? r : r * 100，与 Engine _rate 同口径。
  assert.ok(src.includes('r > 1 ? r : r * 100'), 'ratePct 应包含 >1 归一化逻辑');
});

test('DebtDetail 标签与 tooltip 均走 ratePct，不直接 *100', () => {
  // 确保两处利率展示都不再硬编码 (interest_rate * 100)，避免百分数输入显示成 350%。
  assert.ok(!/interest_rate\s*\*\s*100/.test(src), 'DebtDetail 不应直接 interest_rate * 100');
  assert.ok(src.includes('ratePct(l.interest_rate)'), 'DebtDetail 应调用 ratePct');
});

test('三块 P2 图组件均已导出', () => {
  for (const c of ['CashflowBreakdown', 'DebtDetail', 'ProtectionMembers']) {
    assert.ok(src.includes(`export const ${c}`), `charts.js 缺 ${c} 组件`);
  }
});
