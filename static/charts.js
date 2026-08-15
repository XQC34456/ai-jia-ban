// 证据块图表组件工厂：把 Engine 已算好的确定性数字渲染成 ECharts 图。
// 铁律：只读 props.data（来自 overview 等 API 已返回字段），绝不做任何财富计算。
// 每个组件 = 一个明确的财务问题 + 一组确定性数据，可被 dashboard 与顾问回答复用。
import { fmtMoney, CLASS_ORDER, CLASS_LABELS, CLASS_COLORS } from './format.js';

const { ref, onMounted, onUnmounted, watch } = Vue;

const EMPTY_OPTION = {
  title: {
    text: '暂无数据 · 先完善家庭数据', left: 'center', top: 'middle',
    textStyle: { color: '#8e8e93', fontSize: 13, fontWeight: 'normal' },
  },
};

// 统一封装：容器 ref + ECharts 生命周期（init / setOption / resize / dispose）。
function defineChart(buildOption, height = '260px') {
  return {
    props: { data: { default: null } },
    setup(props) {
      const el = ref(null);
      let chart = null;
      function draw() {
        if (!el.value || !window.echarts) return;
        if (!chart) chart = window.echarts.init(el.value);
        chart.setOption(buildOption(props.data) || EMPTY_OPTION, true);
        chart.resize();
      }
      function onResize() { if (chart) chart.resize(); }
      onMounted(() => { draw(); window.addEventListener('resize', onResize); });
      watch(() => props.data, draw, { deep: true });
      onUnmounted(() => { window.removeEventListener('resize', onResize); if (chart) { chart.dispose(); chart = null; } });
      return { el };
    },
    template: `<div class="chart" ref="el" :style="{ height: '${height}', width: '100%' }"></div>`,
  };
}

// —— ① 7 维健康雷达图：回答「我家整体健不健康？哪维最弱？」 ——
const DIM_LABELS = {
  cashflow: '现金流', liquidity: '流动性', debt: '负债', protection: '保障',
  allocation: '配置', goals: '目标', retirement: '养老',
};
export const HealthRadar = defineChart((data) => {
  const dims = data || [];
  if (!dims.length) return null;
  return {
    tooltip: {},
    radar: {
      indicator: dims.map(d => ({ name: DIM_LABELS[d.name] || d.name, max: 100 })),
      radius: '62%',
      axisName: { color: '#5b616b', fontSize: 12 },
    },
    series: [{
      type: 'radar',
      data: [{
        value: dims.map(d => d.score),
        name: '健康评分',
        areaStyle: { opacity: 0.18 },
        lineStyle: { width: 2 },
      }],
    }],
  };
}, '300px');

// —— ② 现金流结构图：回答「钱去哪了？每月能存多少？」 ——
export const CashflowChart = defineChart((data) => {
  const c = data || {};
  if (c.income == null && c.expense == null) return null;
  const surplus = c.surplus ?? 0;
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmtMoney(v) },
    grid: { left: 8, right: 8, top: 24, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: ['收入', '支出', '结余'], axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceef1' } }, axisLabel: { formatter: (v) => fmtMoney(v) } },
    series: [{
      type: 'bar', barWidth: 40,
      data: [
        { value: c.income ?? 0, itemStyle: { color: '#34c759' } },
        { value: c.expense ?? 0, itemStyle: { color: '#ff3b30' } },
        { value: surplus, itemStyle: { color: surplus >= 0 ? '#007aff' : '#ff3b30' } },
      ],
    }],
  };
});

// —— ③ 资产配置环图：回答「钱放在哪？配置合理吗？」 ——
export const AllocationDonut = defineChart((data) => {
  const classes = data || {};
  const items = CLASS_ORDER
    .map(k => ({ name: CLASS_LABELS[k], value: (classes[k] && classes[k].value) || 0, itemStyle: { color: CLASS_COLORS[k] } }))
    .filter(x => x.value > 0);
  if (!items.length) return null;
  return {
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}：${fmtMoney(p.value)}（${p.percent}%）` },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10 },
    series: [{
      type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
      label: { show: false },
      data: items,
    }],
  };
});

// —— ④ 负债压力仪表盘：回答「债务危险吗？」 ——
export const DebtGauge = defineChart((data) => {
  const d = data || {};
  const dti = d.dti;
  if (dti == null) return null;
  return {
    series: [{
      type: 'gauge', min: 0, max: 100, startAngle: 210, endAngle: -30,
      axisLine: { lineStyle: { width: 14, color: [[0.3, '#34c759'], [0.5, '#ffcc00'], [1, '#ff3b30']] } },
      pointer: { width: 4, length: '60%' },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      detail: { formatter: (v) => v.toFixed(0) + '%', fontSize: 22, offsetCenter: [0, '20%'] },
      title: { offsetCenter: [0, '45%'], fontSize: 12, color: '#8e8e93' },
      data: [{ value: Math.round(dti * 100), name: '月供/收入' }],
    }],
  };
});

// —— ⑤ 保障缺口图：回答「保障够不够？出事扛不扛得住？」 ——
export const ProtectionGap = defineChart((data) => {
  const p = data || {};
  const ratio = p.coverage_ratio;
  if (ratio == null) return null;
  return {
    tooltip: { trigger: 'item' },
    grid: { left: 8, right: 24, top: 20, bottom: 4, containLabel: true },
    xAxis: { type: 'value', max: 6, axisLabel: { formatter: (v) => v + ' 倍' } },
    yAxis: { type: 'category', data: ['保额 / 年收入'] },
    series: [{
      type: 'bar', barWidth: 20, data: [Math.min(ratio, 6)],
      itemStyle: { color: ratio >= 5 ? '#34c759' : '#5ac8fa' },
      markLine: {
        symbol: 'none', lineStyle: { color: '#ff9500', type: 'dashed', width: 2 },
        data: [{ xAxis: 5, label: { formatter: '目标 5 倍', position: 'insideEndTop', color: '#ff9500' } }],
      },
    }],
  };
});

// —— ⑥ 目标资金进度图：回答「哪个目标落后？钱够不够？」 ——
export const GoalProgress = defineChart((data) => {
  const goals = data || [];
  if (!goals.length) return null;
  const names = goals.map(g => g.name);
  const values = goals.map(g => Math.min((g.coverage ?? 0) * 100, 100));
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v) => v.toFixed(0) + '%' },
    grid: { left: 8, right: 32, top: 8, bottom: 4, containLabel: true },
    xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: names, axisLabel: { width: 84, overflow: 'truncate' } },
    series: [{
      type: 'bar', barWidth: 16, data: values,
      itemStyle: { color: '#34c759', borderRadius: 8 },
      label: { show: true, position: 'right', formatter: (p) => p.value.toFixed(0) + '%' },
    }],
  };
});

// —— ⑦ 退休缺口对比图：回答「退休后钱够不够？资产能否覆盖需求？」 ——
// 只读 overview.retirement 已算好的三个确定性数字（可投资资产/净资产/需求现值），零计算。
export const RetirementGap = defineChart((data) => {
  const r = data || {};
  if (r.investable_at_retirement == null && r.net_worth_at_retirement == null && r.retirement_need_pv == null) return null;
  const investable = r.investable_at_retirement ?? 0;
  const netWorth = r.net_worth_at_retirement ?? 0;
  const need = r.retirement_need_pv ?? 0;
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v) => fmtMoney(v) },
    grid: { left: 8, right: 24, top: 24, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: ['退休可投资资产', '退休净资产', '退休需求现值'], axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceef1' } }, axisLabel: { formatter: (v) => fmtMoney(v) } },
    series: [{
      type: 'bar', barWidth: 40,
      data: [
        { value: investable, itemStyle: { color: '#34c759' } },
        { value: netWorth, itemStyle: { color: '#5ac8fa' } },
        { value: need, itemStyle: { color: '#ff9500' } },
      ],
    }],
  };
});

// —— ⑧ 现金流固定/弹性瀑布图：回答「钱怎么从收入流到结余的？固定 vs 弹性各花多少？」 ——
// 只读后端算好的确定性数字 {income, fixed, elastic, surplus}（固定/弹性总额后端已求和），零计算。
export const CashflowBreakdown = defineChart((data) => {
  const d = data || {};
  if (!d.income && !d.fixed && !d.elastic) return null;
  const income = d.income ?? 0;
  const fixed = d.fixed ?? 0;
  const elastic = d.elastic ?? 0;
  const surplus = d.surplus ?? 0;
  const cats = ['月收入', '固定支出', '弹性支出', '月结余'];
  // 瀑布：透明基座承载「累计起点」，可见柱高度 = |增量|，柱顶即累计值。
  const base = [0, income - fixed, income - fixed - elastic, 0];
  const heights = [income, fixed, elastic, surplus];
  const colors = ['#34c759', '#ff9500', '#5ac8fa', surplus >= 0 ? '#007aff' : '#ff3b30'];
  const signed = [income, -fixed, -elastic, surplus];
  return {
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = (params || []).find(x => x.seriesName === 'value');
        return p ? `${cats[p.dataIndex]}：${fmtMoney(signed[p.dataIndex])}` : '';
      },
    },
    grid: { left: 8, right: 8, top: 24, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: cats, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceef1' } }, axisLabel: { formatter: (v) => fmtMoney(v) } },
    series: [
      { name: 'base', type: 'bar', stack: 'total', silent: true, itemStyle: { color: 'transparent' }, data: base },
      { name: 'value', type: 'bar', stack: 'total', barWidth: 40,
        data: heights.map((h, i) => ({ value: h, itemStyle: { color: colors[i] } })) },
    ],
  };
});

// 利率展示归一化：后端透传原始值（可能是 3.5 百分数，也可能是 0.035 小数），
// 与 Engine _rate 口径一致（>1 视为百分数），只做展示格式化，非财富计算。
function ratePct(v) {
  if (v == null) return null;
  const r = Number(v);
  const pct = r > 1 ? r : r * 100;
  return pct.toFixed(2) + '%';
}

// —— ⑨ 负债明细图：回答「每笔债还剩多少本金？利率多少？还要还多久？」 ——
// 只读 debt.items（逐笔透传的已有字段），零计算。
export const DebtDetail = defineChart((data) => {
  const items = data || [];
  if (!items.length) return null;
  const names = items.map(l => l.name || l.type || '负债');
  const values = items.map(l => l.principal || 0);
  const labels = items.map(l => {
    const rate = ratePct(l.interest_rate) || '';
    const term = l.remaining_months != null ? l.remaining_months + '月' : '';
    return [rate, term].filter(Boolean).join(' · ') || '—';
  });
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = (params || [])[0];
        const l = items[p.dataIndex];
        const rate = ratePct(l.interest_rate) || '—';
        const term = l.remaining_months != null ? l.remaining_months + '月' : '—';
        const pay = l.monthly_payment != null ? fmtMoney(l.monthly_payment) : '—';
        return `${l.name || l.type || '负债'}<br/>剩余本金：${fmtMoney(l.principal || 0)}<br/>利率：${rate} · 剩余期限：${term}<br/>月供：${pay}`;
      },
    },
    grid: { left: 8, right: 96, top: 8, bottom: 4, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceef1' } }, axisLabel: { formatter: (v) => fmtMoney(v) } },
    yAxis: { type: 'category', data: names, axisLabel: { width: 84, overflow: 'truncate' } },
    series: [{
      type: 'bar', barWidth: 16, data: values,
      itemStyle: { color: '#ff9500', borderRadius: 8 },
      label: { show: true, position: 'right', formatter: (p) => labels[p.dataIndex] },
    }],
  };
});

// —— ⑩ 保障成员覆盖图：回答「谁有保障？每个人保额/保费/保单数各多少？」 ——
// 只读 protection.members（后端按成员归组好的确定性数字），零计算。
export const ProtectionMembers = defineChart((data) => {
  const members = data || [];
  if (!members.length) return null;
  const names = members.map(m => m.name || '未指定');
  const values = members.map(m => m.coverage || 0);
  const labels = members.map(m => {
    const parts = [];
    if (m.relation) parts.push(m.relation);
    parts.push((m.policy_count || 0) + ' 份');
    return parts.join(' · ');
  });
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = (params || [])[0];
        const m = members[p.dataIndex];
        return `${m.name || '未指定'}<br/>保额：${fmtMoney(m.coverage || 0)}<br/>年保费：${fmtMoney(m.premium || 0)}<br/>保单：${m.policy_count || 0} 份`;
      },
    },
    grid: { left: 8, right: 96, top: 8, bottom: 4, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceef1' } }, axisLabel: { formatter: (v) => fmtMoney(v) } },
    yAxis: { type: 'category', data: names, axisLabel: { width: 84, overflow: 'truncate' } },
    series: [{
      type: 'bar', barWidth: 16, data: values,
      itemStyle: { color: '#5ac8fa', borderRadius: 8 },
      label: { show: true, position: 'right', formatter: (p) => labels[p.dataIndex] },
    }],
  };
});
