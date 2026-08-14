// 4.1 人性化·纯展示映射单测：确保 format.js 的映射键完整、无遗漏。
import test from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const src = readFileSync(join(ROOT, 'static', 'format.js'), 'utf8');

test('SCENARIO_LABELS 覆盖沙盘 4 个情景键', () => {
  for (const k of ['buy_house', 'prepay', 'invest', 'income_change']) {
    assert.ok(src.includes(`${k}: '`), `format.js 缺 SCENARIO_LABELS.${k}`);
  }
});

test('LEVEL_CONCLUSION 覆盖 3 个财富健康度等级', () => {
  for (const k of ['稳健', '需关注', '脆弱']) {
    assert.ok(src.includes(`${k}: '`), `format.js 缺 LEVEL_CONCLUSION.${k}`);
  }
});
