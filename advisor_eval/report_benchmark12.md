# V1.0 12 题 Advisor Benchmark

- 模式：真实 DeepSeek
- 题量：13 个测量单元（12 题 + 1b 状态对比 + 11 双轮）
- 验收判级只标注硬伤（建档吞/未回答/铁律），细节见每轮测量

## 1 30万现金适不适合投资（未建档）

> G1 反向验收：带金额提问必须到回答路径，不得弹建档确认卡

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我有 30 万现金，现在适不适合投资？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：已生成家庭财务分析，详见下方画像与下一步行动。
  确定性工具(metrics)：['alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.0@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=0.0@overview.cashflow.expense', 'cashflow_income=0.0@overview.cashflow.income', 'cashflow_surplus=0.0@overview.cashflow.surplus', 'equity_pct=0.0@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'net_worth=0.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=46.0@overview.wealth_score']
  证据路径：['overview.wealth_score']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues,get_cashflow,get_allocation] content='我先了解一下您的家庭财务全貌，才能判断这 30 万适不适合投资。'
  chat#2：tool_calls=[无工具] content='我看了一下您家庭的档案，这里有一个很关键的情况必须先跟您说清楚。\n\n## 现在的状况：我掌握的「您」还是一片空白\n\n对您家庭的实际财务，我目前能看到的数据非常有限：\n\n- **家庭档案尚未建档**——没有成员、没有资产负债记录、没有现金流记录\n- **您的 30 万现金**在系统里也没有体现（当前记录的净资产是 0）\n- 财富评分 46（脆弱档），但**主要是因为没有数据**（"尚未记录收入""尚'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 1b 30万现金适不适合投资（已建档）

> 已建档态应复用家庭数据给个性化判断，且数字可追溯

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ❌ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我有 30 万现金，现在适不适合投资？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：当前最需要关注：资产配置适配度偏低（配置适配度 51 分）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'goal_completion', 'liquidity', 'liquidity_months', 'net_worth', 'nwc', 'other_pct', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.0@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=-10.0@comparison.A.liquidity.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=0.01@comparison.A.nwc.delta', 'nwc=0.12@comparison.A.nwc.delta', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'rfr=0.01@comparison.A.rfr.delta', 'rfr=0.12@comparison.A.rfr.delta', 'wealth_score=-3.0@comparison.A.wealth_score.delta', 'wealth_score=3.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.liquidity.emergency_months', 'overview.net_worth', 'overview.wealth_score']
  行动建议：['确认现有股票的投资性质。']
  铁律：❌ 数字无编造
  chat#1：tool_calls=[get_wealth_overview,get_wealth_issues,get_allocation,get_goals] content='我来帮你分析这个问题。首先让我了解一下你的家庭财务状况全貌，以及当前的重点问题。'
  chat#2：tool_calls=[run_scenario,run_scenario] content='我先理清了你的家庭状况，让我把关键信息和你真正面对的问题看清楚。\n\n你问的是"30 万现金适不适合投资"，但这个问题的背后，其实是三个交织在一起、需要一起做的决策：这 30 万该投、投多少、投到哪。让我用你的数据说明我看到了什么，然后帮你跑一个情景验证。\n\n先讲我掌握的事实：\n\n**你的现金其实已经超标了。** 你目前现金类资产占比 62%，而资产配置目标里现金只该占约 16%，固收类占你 0%—'
  chat#3：tool_calls=[无工具] content='两个情景跑完了，数据很清楚地告诉我答案。我把结论给你。\n\n---\n\n## 直接回答：不是"适不适合投"，而是"该投、但要投对地方"\n\n30万现金**应该投出去**——你的问题不是"要不要投资"，而是"不投就亏了"。但关键在**别投进股票**，而是**投进固收**。我用你的真实数据验证给你看。\n\n---\n\n### 为什么说"该投"——你的证据链\n\n- 你现在现金占整个金融资产的 **62%**，而你'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 2 30万投入股票怎么分

> 配置相关，期望引擎产出 allocation/风险指标

**验收判级**：

- ❌ 不被建档吞
- ❌ 返回类型
- ❌ 状态ok

**第1轮 用户**：我想把 30 万投入股票，应该怎么分？
第1轮：⚠️ ConfirmCard（建档确认卡，items=1）→ 用户取消
  → 模拟取消：discarded「好的，已忽略，没有改动你的档案。」（原问题是否保留？）

## 3 提前还车贷还是拿钱投资

> 比较类：期望 tradeoffs + 行动建议

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ❌ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我该提前还车贷还是拿钱投资？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：当前最需要关注：资产配置适配度偏低（配置适配度 51 分）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow', 'cashflow_surplus', 'dti', 'goal_completion', 'liquidity', 'liquidity_months', 'net_worth', 'nwc', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow=400.81@comparison.A.cashflow.delta', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=-0.01@comparison.A.dti.delta', 'dti=0.0@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=-9.9@comparison.A.liquidity.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=0.01@comparison.A.nwc.delta', 'nwc=0.02@comparison.A.nwc.delta', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'rfr=0.01@comparison.A.rfr.delta', 'rfr=0.02@comparison.A.rfr.delta', 'wealth_score=-2.0@comparison.A.wealth_score.delta', 'wealth_score=3.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.liquidity.emergency_months', 'overview.retirement.nwc']
  行动建议：['确认车贷的具体金额和利率，以便重新评估。', '评估并购买合适的保险产品。']
  铁律：❌ 数字无编造
  chat#1：tool_calls=[get_wealth_issues,get_wealth_overview,get_family_profile] content=''
  chat#2：tool_calls=[run_scenario,run_scenario] content='我先确认一下你的债务结构，再做情景对比。让我看看你提到的"车贷"是否在手头的负债里。\n\n从家庭画像看到，你目前账面上的负债只有一项：**房贷**（本金200万，月供12000，年利率3.5%，还剩240期）。我没有看到车贷的记录。\n\n在往下分析之前，我需要澄清一个关键问题：**你说的"车贷"是还没在账面上的贷款吗？还是其实你想问的是"房贷"？**\n\n不过不管是车贷还是房贷，我先把思路理清楚——因为'
  chat#3：tool_calls=[run_scenario] content='投资情景已经出结果了，我用正确的参数重新跑一下提前还贷：'
  chat#4：tool_calls=[无工具] content='两个情景都出结果了，数据非常清晰。让我先做个说明，然后给你完整分析。\n\n---\n\n好，我可以给你一个明确的判断了。不过要先把话说清楚：**你账面上目前只有一笔负债——房贷（200万，年利率3.5%）**，我没有看到车贷记录。我下面把"提前还贷"指的是还这笔房贷来对比。如果你说的车贷是另一笔还没登记进来的贷款，请告诉我金额和利率，我再重新算。\n\n---\n\n## 结论：拿这30万去投资，而不是提前还贷'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 4 收入下降20%能撑多久

> 变化/情景类：期望现金流/应急月数数字

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ❌ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：如果收入下降 20%，我能撑多久？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：当前最需要关注：资产配置适配度偏低（配置适配度 51 分）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'goal_completion', 'liquidity', 'liquidity_months', 'net_worth', 'nwc', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow=-8000.0@comparison.A.cashflow.delta', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.075@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=-0.54@comparison.A.nwc.delta', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'rfr=-0.54@comparison.A.rfr.delta', 'wealth_score=-17.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.cashflow.savings_rate', 'overview.debt.dti', 'overview.liquidity.emergency_months', 'overview.retirement.rfr']
  行动建议：['确认收入下降的持续时间', '若要比较不同应对方案，可分别模拟情景', '考虑是否需要压缩开支或调整投资以保护长期目标']
  铁律：❌ 数字无编造
  chat#1：tool_calls=[get_cashflow,get_wealth_overview,get_wealth_issues,run_scenario] content='我来帮你分析收入下降20%的影响。先看一下你当前的现金流和应急状况，同时跑一个情景模拟来看看到底能撑多久。\n\n让我先调取数据。'
  chat#2：tool_calls=[无工具] content='我已拿到完整数据，包括情景模拟结果。我先把话说清楚。\n\n---\n\n## 收入下降20%，你能撑多久？——结论先说\n\n**短期（应急层面）：你不缺钱。** 你的流动性底子很厚，但**问题不在"撑多久"，而在"撑过去之后，长期目标还保不保得住"**。\n\n我分开讲。\n\n### 一、应急层面：能撑很久\n\n- 你目前有可动用现金，应急资金覆盖约 **16.7 个月**，这已经远远超过 6 个月的安全线。\n-'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 5 孩子教育金目标怎么完成

> 目标类：期望目标缺口数字 + 行动

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：这个孩子教育金目标怎么完成？
第1轮：intent=CHECK_GOALS status=ok
  回答：教育金目标存在较大缺口，需要结合现有闲置现金和月度结余，通过一次性建底仓加定期定存的方式逐步填补，同时需注意资产配置集中风险。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'other_pct', 'real_estate_pct']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct']
  证据路径：['overview.cashflow.surplus']
  行动建议：['确认教育金的目标使用时间（孩子年龄）', '明确可用于长期教育金的现金金额', '进行情景模拟，测算底仓和月度定存的具体方案']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_goals,get_cashflow,get_allocation] content=''
  chat#2：tool_calls=[无工具] content='我已经拿到关键数据了。让我梳理一下你的教育金目标和现状，来回答这个问题。\n\n---\n\n你的问题本质是：**这个教育金目标（100万）靠什么方式填上那90万的缺口**。这不是一个「要不要存」的问题，而是一个「钱从哪来、怎么增值」的组合决策。\n\n我先说清楚现状：\n\n**教育金缺口有多大？**\n- 目标是 100 万，目前只备了 10 万，缺口是 **90 万**，覆盖率只有 10%。\n- 这个目标还没'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 6 退休够不够

> 退休类：期望 retirement metrics + 判断

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：按现在的情况，我退休够不够？
第1轮：intent=CHECK_RETIREMENT status=ok
  回答：从测算数字看，退休是够的，但需注意房贷未计入退休开销、教育金缺口与退休目标重叠、资产配置适配度偏低等前提。核心矛盾是资产配置适配度偏低，现金占比过高，未充分复利
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'nwc', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'nwc=1.24@overview.retirement.nwc', 'rfr=1.24@overview.retirement.rfr', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct']
  行动建议：['梳理出闲置现金的具体金额。', '模拟将多余现金按目标配比投入固收/权益后的退休覆盖变化。', '明确房贷还款计划，是否在退休前结清。', '评估教育金缺口，制定补充计划。']
  铁律：全部通过
  chat#1：tool_calls=[get_retirement,get_wealth_overview,get_wealth_issues] content='我来看一下你的养老测算情况。'
  chat#2：tool_calls=[无工具] content='我把你的养老数据完整看了一遍，直接给你结论。\n\n## 结论：从测算数字看，你退休是够的——但要带几个前提看\n\n**硬指标上你处于"养老健康"区域**。测算显示，你 60 岁退休时可投资的资产（按现状滚动积累）将高于你退休后全部生活需求资金的现值，资金覆盖比和净资产覆盖比都在 1.24 的水位，即需求得到覆盖、还有富余。从这个角度，你的退休账本目前是立得住的。\n\n但我不能只报一个"够"字，因为系统标'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 7 钱越来越不够用了怎么办

> 模糊情感+财务：不应答非所问

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我最近感觉钱越来越不够用了，怎么办？
第1轮：intent=VIEW_OVERVIEW status=ok
  回答：钱不够用的感觉可能源于资产配置不当和保障缺失，而非现金流本身紧张。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_overview,get_wealth_issues,get_cashflow,get_allocation] content='我先停下来理解你这句话背后的决策。\n\n你说"钱越来越不够用了"，这背后可能是几个不同的信号：是现金流真的紧张了？还是因为看到孩子教育金缺口、负债而感到焦虑？我需要先看清这个家庭的真实状况，才能判断你现在面对的是"事实上的紧张"还是"感觉上的紧张"——这两者的解法完全不同。\n\n让我先调取全貌数据。'
  chat#2：tool_calls=[无工具] content='我需要先跟你把"钱不够用"这个感觉拆开——因为数据告诉我，你现在的处境可能跟你的感受不完全一样。让我把真实情况给你看清楚。\n\n## 先回应你的感受\n\n你感觉"钱越来越不够用了"，这个感觉我完全理解。当你同时背着一笔负债、看着孩子的教育金缺口、每个月结余只剩下一点的时候，那种"钱在往外流、存不下来"的焦虑是真实的。但我想先帮你区分一件事：**你现在的问题是"现金流真的紧张"，还是"资产配置让你觉得钱'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['summary']

## 8 应该买什么基金

> 纯知识：无档案也应给有效通用回答，且不编造家庭数字

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我应该买什么基金？
第1轮：intent=VIEW_OVERVIEW status=ok
  回答：顾问明确表示，在家庭财务档案信息严重缺失的情况下，无法负责任地推荐具体基金。顾问指出当前最需要解决的是财务基础问题而非基金选择。
  确定性工具(metrics)：['cashflow_surplus', 'net_worth', 'wealth_score']
  关键数字：['cashflow_surplus=0.0@overview.cashflow.surplus', 'net_worth=0.0@overview.net_worth', 'wealth_score=46.0@overview.wealth_score']
  证据路径：['overview.wealth_score']
  行动建议：['待信息补充后，可通过情景模拟对比一次性投入与分批定投等策略的利弊。']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_issues,get_wealth_overview] content='我先理解一下你的处境。你问"应该买什么基金"，但这是一个刚刚起步、还没有完整家庭数据的场景。你的家庭档案显示信息几乎是空的——没有成员、没有资产、没有负债、没有问题清单。\n\n在给任何投资建议前，我需要先弄清楚这个家庭的真实底子。让我先调取一下核心数据。'
  chat#2：tool_calls=[无工具] content='我现在能清楚地看到你的处境了。让我诚实地说出真相：\n\n**你说有 30 万现金，但你的家庭档案是空的——没有任何收入、支出、资产、负债、目标、保险的记载。** 我刚才调到的财富评分 46 分，标注为"脆弱"，但那个分数其实是因为"尚未记录"而拉低的，不是真实的财务风险。\n\n现在，我要直接回答你的问题，但先要纠正一个顺序。\n\n---\n\n## 你在问的问题，本身跳了两步\n\n你问"买什么基金"——这背后'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 9 买房先还贷还是留现金

> 决策比较：期望引擎计算 + 权衡

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我想买房，应该先还贷还是留现金？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：你的决策方向取决于你是否真的要买新房，两种情形路径完全不同，需要先确认关键信息。无论哪种情形，你账上现金过多、股票过于集中、教育金缺口矛盾比负债更突出，提前还贷
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.debt.dti', 'overview.liquidity.emergency_months', 'overview.wealth_score']
  行动建议：['提供新房总价、首付比例及计划动用的现金金额', '补充新房月供的资金安排', '核实并更新教育金目标金额及当前积累情况']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_wealth_overview,get_cashflow,get_allocation] content='我先理解一下你的问题。你叫「买房」，但实际上你问的是「该不该提前还现有贷款」——这背后其实是一个决策：**在「提前还贷」和「保留现金」之间，哪个对你买房更有利**。\n\n要回答这个问题，我得先看看你现在的负债结构、现金流和资产配置情况。'
  chat#2：tool_calls=[无工具] content='我需要先澄清一个关键事实，再帮你做决策。\n\n我先看你账上的情况：你手上有一笔房贷 200 万、月供 1.2 万，同时现金 50 万、股票 30 万。你现在纠结的是「提前还这笔房贷」还是「把现金留着」——而你的标题写的是「买房」。\n\n这里有个信息差我必须先问清楚，否则没法给你靠谱的判断。让我先模拟一下几种可能，但我们缺一个关键参数。\n\n在动手之前，我先跟你确认两件事——**因为你此刻的答案会彻底改变'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 10 取消建档后继续回答原问题

> Step 4（G3 闭环）：轮1 建档话术（月收入+存款+带金额配置问题）→ 弹确认卡；自动模拟取消 = 拒绝本次建档 ≠ 拒绝回答——cancel_and_reanswer 把原问题（original_query）重新投入正常 Advisor 路径（filing_declined 跳过建档 gate，防死循环），回答原配置问题（CHECK_ALLOCATION，status=ok，真实配置指标），不再返回「好的，已忽略」。family=filed 让 CHECK_ALLOCATION 有真实配置指标可测

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ❌ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我月收入 3 万，存款 50 万，这 30 万怎么配置？
第1轮：⚠️ ConfirmCard（建档确认卡，items=2）→ 用户取消
  → 取消建档 = 拒绝本次建档 ≠ 拒绝回答：原问题重新回答 ↓
第1轮：intent=CHECK_ALLOCATION status=need_clarification
  回答：需要补充以下信息：配置的主要目的
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'equity_pct', 'fixed_income_pct', 'other_pct', 'real_estate_pct']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct']
  行动建议：['明确配置目的（教育金、收益改善、养老）', '用场景模拟工具对比不同配置方向的得失']
  铁律：全部通过
  chat#1：tool_calls=[record_family_info] content='I need to first clarify what "这 30 万" refers to, as you mentioned a monthly income of 30,000 and savings of 500,000. Let me extract the clear information from your statement.\n\nBased on what you\'ve sha'

## 11 已有收入是否被重复追问

> 收入已在档案，轮2 不应重复要求用户提供收入

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：帮我看看我的现金流情况
第1轮：intent=VIEW_OVERVIEW status=ok
  回答：账面现金流健康但结构性有隐患。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.cashflow.surplus', 'overview.liquidity.emergency_months']
  行动建议：['确认教育金目标用钱时间点']
  铁律：全部通过
  chat#1：tool_calls=[get_cashflow,get_wealth_issues,get_wealth_overview] content=''
  chat#2：tool_calls=[无工具] content='我帮你把现金流捋清楚了。先给结论，再拆解。\n\n## 你的现金流：账面健康，但结构性有隐患\n\n### 先说好的\n\n**你每个月的收支是这样的：**\n- 月收入 4 万，月支出 3 万，每月结余 1 万\n- 储蓄率 25%，这个水平在稳健家庭里属于合格线以上\n- 在现金流这一个维度上，你的得分是满分 100 分\n\n**应急能力很强。** 手头可动用的现金大约 50 万，按当前每月 3 万的支出算，够撑'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

**第2轮 用户**：我收入多少你不是知道吗，为什么还要问
第2轮：intent=EXPLAIN_RESULT status=ok
  回答：顾问承认不该重复询问已提供的信息，并基于已有数据重新整理了财务状况。现金流健康，每月可稳定储蓄，储蓄率合理。但资产配置存在三方面问题：现金闲置过多、股票占比偏高
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.liquidity.emergency_months', 'overview.net_worth']
  行动建议：['制定教育金的定期储蓄计划']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_cashflow,get_wealth_issues] content='你说得对，是我多此一举了。你月收入的数据我这里确实有——让我先把你的家庭全景调出来，重新基于已掌握的信息回应你，而不是让你重复。\n\n让我读取你的最新家庭数据。'
  chat#2：tool_calls=[无工具] content='你批评得对，我不该重复问你已经告诉我的事。你月收入 4 万（你自己 2.5 万 + 配偶 1.5 万），每月结余 1 万，这些数据我都有，是我没先查数据就问，这是我的失误。\n\n我重新把数据调出来了，把你的真实情况摆在这里——\n\n**你现在的现金流情况：**\n- 月收入 4 万，月支出 3 万，每月结余 1 万，储蓄率 25%\n- 支出里，日常开销 1.5 万是弹性支出，教育 3 千是固定支出\n\n*'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 12 从目标页问顾问，首轮直接回答目标问题

> Step 3 修正：payload 改为真实前端契约（goal_id 标识，goal_type 语义），移除原泄漏的 target_amount/current_saved/gap 聚合数字（T6 白名单剥离，T4 红线：数字只能由 Engine 注入）。goal_id=1 指向 build_family 的教育金目标，用于验收『顾问围绕 payload.goal_id 指向的目标回答』

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：这个教育金目标怎么完成？
第1轮：intent=CHECK_GOALS status=ok
  回答：目标为教育金，缺口需通过调整资产配置和利用闲置现金来补充，而非仅依赖每月结余硬存。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.cashflow.surplus', 'overview.liquidity.emergency_months', 'overview.wealth_score']
  行动建议：['用户需明确教育金用钱的大致时间，以便进行具体测算。']
  铁律：全部通过
  chat#1：tool_calls=[get_goals,get_wealth_issues,get_allocation,get_cashflow,get_wealth_overview] content='我来帮你仔细看看教育金目标的情况。先调取相关的家庭数据和目标信息。'
  chat#2：tool_calls=[无工具] content='我先理清你的情况，然后帮你把教育金这个目标掰开来看。\n\n---\n\n## 先看清现状\n\n你的教育金目标：目标是 **100 万**，目前已备 **10 万**，缺口 **90 万**。这是你主要要补的一个数。\n\n关键点在于——**这个目标没有设定时间线**（`target_date` 为空，`monthly_needed` 也是空的）。也就是说，还没定这个钱是"孩子 5 年后要用"还是"10 年后要'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']
