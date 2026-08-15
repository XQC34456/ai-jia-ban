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
  回答：顾问表示目前无法直接判断是否适合投资，因为家庭的财务信息严重缺失。唯一确定的是无负债、无保险、无现金流记录、无理财目标。财富评分为'脆弱'，主要因为关键维度未记
  确定性工具(metrics)：['alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.0@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=0.0@overview.cashflow.expense', 'cashflow_income=0.0@overview.cashflow.income', 'cashflow_surplus=0.0@overview.cashflow.surplus', 'equity_pct=0.0@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'net_worth=0.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=46.0@overview.wealth_score']
  证据路径：['overview.wealth_score']
  行动建议：['回答顾问提出的四个问题：收入支出、资金用途、保险情况、风险承受能力。', '在系统内补全家庭档案。']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_issues,get_wealth_overview,get_cashflow,get_allocation] content='我先看一下这个家庭的整体情况，才能判断这 30 万现金适不适合投资、往哪个方向投。\n\n让我先调取家庭的基本面貌和财富全景。'
  chat#2：tool_calls=[无工具] content='看了你的家庭档案，我必须先停下来，因为现在**还不能回答"适不适合投资"**——缺少最关键的信息。\n\n先说我看到了什么。\n\n## 你现在的基本盘\n\n系统显示这个家庭是"**未建档家庭**"：没有成员、没有资产、没有负债、没有收入、没有支出、没有目标、没有保险。财富评分 46，水平是"脆弱"，但评分里除了"无负债"这一项是满分的，其余全是"未记录"状态。\n\n换句话说，**现在唯一确定的是：你没负债、'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 1b 30万现金适不适合投资（已建档）

> 已建档态应复用家庭数据给个性化判断，且数字可追溯

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
  回答：这笔钱不是「要不要投」的问题，而是「投到哪、顺便解决什么」的问题。你的现金过度闲置，但存在更急的教育金缺口，资产配置严重失衡，方向几乎已定——应优先补固收，而非
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'goal_completion', 'liquidity', 'liquidity_months', 'net_worth', 'nwc', 'other_pct', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow=400.81@comparison.A.cashflow.delta', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=-0.01@comparison.A.dti.delta', 'dti=0.0@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=-9.9@comparison.A.liquidity.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=0.01@comparison.A.nwc.delta', 'nwc=0.02@comparison.A.nwc.delta', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'rfr=0.01@comparison.A.rfr.delta', 'rfr=0.02@comparison.A.rfr.delta', 'wealth_score=-2.0@comparison.A.wealth_score.delta', 'wealth_score=3.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.debt.dti']
  行动建议：['决定是否建立教育金定存计划']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_issues,get_allocation,get_cashflow] content='我来帮你理清这个决策。让我先看看你家庭的整体状况。'
  chat#2：tool_calls=[run_scenario,run_scenario] content='我已经掌握了你的家庭状况。让我先确认一下你的理财决策环境——这题没有标准答案，关键是权衡。\n\n先看你家庭的关键数据：\n\n**你的现金状况**\n- 你手上有 50 万存款（加上 30 万股票基金），你问的 30 万应该就是其中一块现金\n- 应急资金覆盖 **16.7 个月**，远超 6 个月的安全线——这笔钱确实闲置了\n\n**但这笔钱有没有「别的用途」才是关键**\n- 你有一个 **100 万的孩子'
  chat#3：tool_calls=[run_scenario,compare_scenarios] content='提前还贷的参数用错了，我重新模拟一下正确参数。\n\n对了，让我也同时补充一下——你的核心 P1 问题其实是 **资产配置适配度偏低（51 分，现金占比过高、固收为零）**，而你的首要目标是 **补 90 万教育金缺口**。所以我需要看清楚：这笔 30 万到底是该投权益、投固收，还是干脆去补教育金。让我把「投固收」和「投权益」两个方向再对比一下，因为方向上差异很大。'
  chat#4：tool_calls=[无工具] content='数据已经很清晰了。我来给你一个完整的判断。\n\n---\n\n## 先说结论：这笔钱不是「要不要投」的问题，而是「投到哪、顺便解决什么」的问题\n\n你手上这 30 万，从家庭财务全局看，最该做的既不是简单丢进股票，也不是继续躺着。让我用你家真实的数字说话。\n\n### 你当下的真实处境（三个关键事实）\n\n**① 你的钱在"过度闲置"，但手里其实有更急的缺口**\n你目前的现金占总资产 **62%**，应急资金'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 2 30万投入股票怎么分

> 配置相关，期望引擎产出 allocation/风险指标

**验收判级**：

- ❌ 不被建档吞
- ❌ 返回类型
- ❌ 状态ok

**第1轮 用户**：我想把 30 万投入股票，应该怎么分？
第1轮：⚠️ ConfirmCard（建档确认卡，items=1）
  → 模拟取消：discarded「好的，已忽略，没有改动你的档案。」（原问题是否保留？）

## 3 提前还车贷还是拿钱投资

> 比较类：期望 tradeoffs + 行动建议

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我该提前还车贷还是拿钱投资？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：顾问指出系统数据中没有车贷记录，用户现有负债为房贷，因此需要先确认“车贷”的真实含义。顾问强调用户当前的核心矛盾并非提前还贷还是投资，而是现金过量闲置、固收配置
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.liquidity.emergency_months', 'overview.retirement.nwc', 'overview.wealth_score']
  行动建议：['确认“车贷”的具体含义和细节（金额、利率）。', '提供现金持有量。', '说明你个人的倾向。']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_wealth_overview,get_allocation,get_cashflow] content='我先看看你的家庭财务状况和问题清单，再来判断这个问题。'
  chat#2：tool_calls=[无工具] content='我需要先弄清楚情况——我看到了你的负债结构，你的负债里是房贷（200 万，利率 3.5%），我没有在数据里看到车贷。你提的是「车贷」，让我确认一下到底指的是哪笔负债，以及具体金额和利率，这样才能做对比。\n\n让我先了解更准确的负债明细。\n\n我先跟你确认几个关键信息，因为这直接决定答案：\n\n**我从来没有在系统里看到「车贷」。** 你现有的负债是：\n- 房贷 200 万，利率 3.5%，月供 1200'
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
  铁律：❌ 数字无编造
  chat#1：tool_calls=[get_wealth_overview,get_cashflow,run_scenario] content='我来帮你分析这个情况。收入下降 20% 对家庭财务的影响，需要结合当前现金流和应急能力来判断。\n\n让我先调取相关数据。'
  chat#2：tool_calls=[无工具] content='我来直接回答你的问题，并且把真实情况讲清楚。\n\n## 结论先说\n\n**如果收入下降 20%，按现在的支出水平，你靠现金"撑"的月份数并不会变（因为你手头有足额现金），但真正的危险不是"撑多久"，而是这么一降，你的家庭从"稳健"直接跌进"需关注"，而且养老资金会从健康变成不足。** 我们别只盯着"撑几个月"，这个问法会掩盖真正的大问题。\n\n---\n\n## 关键数字（系统模拟结果）\n\n收入从 40,0'
  complete_json#1：parse 失败(None)

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
  回答：教育金目标完成的核心不是增加储蓄，而是激活闲置现金并引导现金流进入固收类资产。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'goal_completion', 'liquidity', 'net_worth', 'nwc', 'other_pct', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow=-12000.0@comparison.A.cashflow.delta', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.0@comparison.A.dti.delta', 'dti=0.1286@comparison.A.dti.delta', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=-0.8@comparison.A.nwc.delta', 'nwc=0.01@comparison.A.nwc.delta', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'rfr=-0.8@comparison.A.rfr.delta', 'rfr=0.01@comparison.A.rfr.delta', 'wealth_score=-32.0@comparison.A.wealth_score.delta', 'wealth_score=0.0@comparison.A.wealth_score.delta']
  证据路径：['overview.cashflow.savings_rate']
  行动建议：['在系统中设定教育金目标的到期时间和每月定存金额。', '确认教育金目标的使用时间，以便更准确规划。', '提供更多信息以进行方案对比，如每月定投额或闲置现金一次性划转的两种方案。']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_issues,get_goals,get_allocation,get_cashflow] content='我需要先全面了解这个家庭的情况，特别是教育金目标的细节和整体财务状况。'
  chat#2：tool_calls=[run_scenario,run_scenario] content='我已经拿到完整数据。让我先梳理这个家庭的关键事实，再针对"教育金目标怎么完成"给出真正的答案。\n\n先做一个情景模拟来验证教育金完成路径——目前的月度结余、现金闲置、配置偏差，都指向同一个方向。'
  chat#3：tool_calls=[无工具] content='数据已经够了。让我把真正的答案讲清楚。\n\n---\n\n## 教育金缺口——真正的问题不是"怎么攒"，而是"钱放哪、有没有在动"\n\n先说结论：孩子教育金的目标是 100 万，目前只有 10 万，还差 90 万。这个缺口**不是靠"每月多存点钱"能解决的**，因为你这个家庭目前真正的病根不在储蓄意愿，而在于**一大笔钱躺在账上不动、眼睁睁看着通胀慢慢吃掉**。所以教育金怎么完成这个问题，答案很直接：\n\n'
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
  回答：退休资金本身是够的且有富余，但条件依赖持续储蓄，且存在配置失衡和房贷未计入测算的风险。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'nwc', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'nwc=1.24@overview.retirement.nwc', 'rfr=1.24@overview.retirement.rfr', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.cashflow.savings_rate', 'overview.liquidity.emergency_months', 'overview.retirement.nwc', 'overview.retirement.rfr']
  行动建议：['模拟将闲置现金投入固收后对养老和教育金的影响。', '确认距离退休的年数和房贷还款计划，以补全测算。']
  铁律：全部通过
  chat#1：tool_calls=[get_retirement,get_wealth_issues,get_wealth_overview] content='我先看一下你的养老测算和整体财务状况，综合判断。'
  chat#2：tool_calls=[无工具] content='我看了你的养老测算和整体财务状况，跟你说实话。\n\n**先给你结论：单看「钱够不够退休」，是够的，而且有富余。但这份「够」是有条件的，而且你的钱现在放错了地方。**\n\n我们分开看。\n\n---\n\n**一、退休本身：够，不用慌**\n\n- 系统测算你的养老象限是「养老健康」级，资金覆盖比（RFR）和净资产覆盖比（NWC）都在安全线之上。\n- 意思是：到你退休年龄，你的可投资资产足以覆盖你退休后的资金需求（'
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
  回答：你的现金流健康，并非入不敷出，但存在结构性隐忧：教育金缺口、资产配置失衡（现金过多、无固收）。你对'钱不够用'的感觉主要来自教育金等特定目标尚未落实，而非日常开
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.cashflow.savings_rate', 'overview.liquidity.emergency_months', 'overview.retirement.rfr']
  行动建议：['进行情景模拟，对比三个选项的得失']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues,get_cashflow] content='我先理解你现在的处境和真正在纠结的决策，然后帮你梳理。\n\n让我先看看你的家庭全貌和当前的核心问题。'
  chat#2：tool_calls=[无工具] content='我理解你的感受——"钱越来越不够用"往往是一句情绪，背后藏着一个具体的东西：可能是每个月的账紧，可能是某笔大的开销（教育金、房贷）压着，也可能只是一直觉得存不下钱。\n\n让我用你的真实数据先帮你把感受落到事实上，再判断到底该不该紧张。\n\n## 先看事实：你的"钱不够用"到底是不是真的\n\n**说实话，从数据看，你并不处于"不够用"的危机状态，但确实有一个结构性隐忧。**\n\n先说清楚你的真实底子（这些是'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

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
第1轮：intent=EXPLAIN_RESULT status=ok
  回答：当前家庭信息几乎空白，无法直接推荐具体基金。建议先建立应急金和保险保障，再根据资金用途和风险承受力确定投资方向。需要用户补充收入、支出、资金使用时间等信息后才能
  确定性工具(metrics)：['alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.0@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=0.0@overview.cashflow.expense', 'cashflow_income=0.0@overview.cashflow.income', 'cashflow_surplus=0.0@overview.cashflow.surplus', 'equity_pct=0.0@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'net_worth=0.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=46.0@overview.wealth_score']
  证据路径：['overview.wealth_score']
  行动建议：['提供月收入和月支出', '确认家庭成员情况及保险需求']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues,get_cashflow,get_allocation] content='我先理解一下你的问题。你问「买什么基金」——这背后其实是在问「我有 30 万现金，该怎么投资」。但要回答这个，我得先看清楚这个家庭的真实底色，否则任何基金建议都是空中楼阁。\n\n让我先调取数据和工具。'
  chat#2：tool_calls=[无工具] content='我先说结论：**现在我不能告诉你买什么基金，因为家庭信息几乎是空白。** 这不是敷衍，而是这个决策链上关键的底座全部缺失。\n\n让我把话说透。\n\n---\n\n## 你这个「买什么基金」的问题，其实卡在一堵墙上\n\n你想问的是「30 万放哪能增值」。但你看数据反映出的现状：\n\n- **财富评分 46，等级「脆弱」**——不是因为你穷，而是因为关键维度几乎全没记录：没有收入、没有支出、没有应急金、没有保险、'
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
  回答：核心矛盾不是还贷或留现金，而是当前资产结构不适合再叠加买房重压。需先补充几个关键信息才能给出方向。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.debt.dti', 'overview.liquidity.emergency_months', 'overview.net_worth']
  行动建议：['补充买房目的、首付预算、可承受月供增量等信息', '评估资产重新配置方案，降低现金占比', '咨询保险产品，弥补保障缺失']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_wealth_overview,get_cashflow,get_allocation,get_family_profile] content='让我先全面理解你的家庭状况，再来看这个买房决策。'
  chat#2：tool_calls=[无工具] content='我先梳理一下你的全貌，再来回答「买房该先还贷还是留现金」。\n\n先厘清一个关键点——你的问题里藏着两件不同的事，我需要先确认一下：\n\n**你说的「先还贷」指的是还房贷对吗？** 系统数据显示，你目前唯一的负债是房贷（本金 200 万，月供 1.2 万，利率按揭约 3.5%）。\n\n而在「买房」这件事上，我注意到一个很大的疑点：**你的现金只有 50 万，净资产是 -120 万，总负债已经有 200 万'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 10 取消建档后继续回答原问题

> 轮1 用「投入股票」措辞（非「投资」情景词）→ 现状弹确认卡（G1 吞问题）；弹卡后自动模拟取消（cancel 记录）；轮2 取消+追问 → 原问题必须不丢、继续回答

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ❌ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我想把 30 万投入股票，应该怎么分？
第1轮：intent=EXPLAIN_RESULT status=need_clarification
  回答：我识别到你在介绍家庭财务情况，但有些金额我还没听清。请说得更具体些，例如：月收入多少、房贷月供多少、存款大概多少。
  铁律：全部通过
  chat#1：tool_calls=[无工具] content='我来分析一下你的需求。你提到想投入30万到股票，这是一个投资规划的问题，但其中并没有涉及需要建档的具体信息（家庭成员、收入、支出、资产、负债或目标等）。\n\n让我先确认一下：你提到要投入30万到股票，这笔钱目前是否已经持有（作为资产）？还是有其他相关背景信息（比如收入的来源、家庭情况、风险承受能力等）可以补充？\n\n就目前提供的信息来看：\n- 没有明确的家庭成员介绍\n- 没有提到收入、支出、负债等信息'

**第2轮 用户**：我不想建档了，你先回答我的问题
第2轮：intent=CHECK_ISSUES status=need_clarification
  回答：需要补充以下信息：家庭收支、负债、现金流数据、应急金储备情况、资产和户口信息
  行动建议：['告知月支出金额', '评估对亏损的容忍程度']
  铁律：全部通过
  chat#1：tool_calls=[无工具] content='我理解你的心情——你不想被一堆表格和步骤绕在里面，只想知道一个直接的答案。\n\n但我得对你说实话:我现在手里关于你这个「家庭」的信息几乎是空白的——看不到你的收支、负债、现金流,连资产和户口都没录进去。\n\n这意味着如果你现在问我「该不该投资」「买什么基金」,我给出的任何答案,都是**在不知道你情况的前提下拍的**,不是帮你做的决策。那对你是不负责任的。\n\n举个最直白的例子:**你连应急金有没有、月支'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

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
  回答：现金流账面健康，月结余为正，储蓄率属稳健区间，应急资金远高于安全线；但资产结构失衡，现金占比过高而固收为零，且存在教育金缺口，属于'钱放错了地方'而非收支问题。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.cashflow.surplus', 'overview.liquidity.emergency_months']
  行动建议：['与客户确认闲置现金中需短期使用、不能锁定的具体金额', '进行情景模拟，比较不同配置方案对教育金缺口的改善效果']
  铁律：全部通过
  chat#1：tool_calls=[get_cashflow,get_wealth_issues,get_wealth_overview] content='我先调取你的现金流和财富全景，再看看有没有相关的风险点。'
  chat#2：tool_calls=[无工具] content='我先把你的现金流全貌看清楚，再结合你上次问的那些问题一起说。\n\n---\n\n## 你的现金流：账面健康，但不是"没压力"\n\n先给你吃颗定心丸——**你的现金流本身没有问题，它不是"钱不够用"那类问题。**\n\n从数据看：\n- **月收入** 40,000，**月支出** 30,000，**每月结余** 10,000\n- **储蓄率 25%** ——这个水平是健康的，属于稳健区间\n- **利息保障和月供'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

**第2轮 用户**：我收入多少你不是知道吗，为什么还要问
第2轮：intent=EXPLAIN_RESULT status=ok
  回答：您说得对，您的收入我清楚。您真正的问题是资产结构失衡和教育金缺口，而非收入不足。您问收入是在确认我是否真正理解您的情况。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.cashflow.surplus', 'overview.liquidity.emergency_months', 'overview.retirement.nwc']
  行动建议：['请您告知教育金计划使用的时间（几年后），以便制定具体填补方案。', '核实资产配置数据，确保准确评估。']
  铁律：全部通过
  chat#1：tool_calls=[get_cashflow,get_wealth_overview] content='你说得对，我先确认一下——你的收入我确实有数。\n\n让我把数据和你的问题对齐一下，先别急着问你要数字。'
  chat#2：tool_calls=[无工具] content='你说得对，收入我确实清楚——月入 4 万，这是真实的工资收入。我前面之所以谨慎，不是"不知道"，而是想先把你的完整情况摊开，避免我基于一个数字就下结论。\n\n让我把系统里的数和你对齐一下，说明我为什么看重它。\n\n**你现在的事实（系统里的真实数据）：**\n- 月收入 4 万，来源是工资，单一来源（没有其他被动收入）\n- 月支出 3 万，其中固定支出（教育）约 3 千，弹性支出（日常）约 1.5 万—'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 12 从目标页问顾问，首轮直接回答目标问题

> context 已传入；当前系统是否消费它、首轮是否针对教育金目标

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ❌ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：这个教育金目标怎么完成？
第1轮：intent=CHECK_GOALS status=need_clarification
  回答：需要补充以下信息：目标使用日期、房贷月供是否已含在月支出中
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'goal_1_coverage', 'goal_1_gap']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap']
  行动建议：['确认教育金的目标使用日期（孩子几年级动用）', '确认房贷月供是否已含在月支出中，以核实真实结余']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_goals,get_family_profile] content='我先调取你的家庭全貌、目标进度和问题清单，看清这个教育金缺口的实际情况。'
  chat#2：tool_calls=[无工具] content='我先看清这个家庭的全貌，再给你一个真正走得通的说法。\n\n先明确一下你手里的牌：\n\n- **孩子2016年出生，今年约10岁**，教育金目标 100 万，但目前只存了 10 万，缺口 90 万。也就是说，从孩子现在到上大学/用这笔钱，其实留给你积累的时间窗口并不算宽裕。\n- 你**有 50 万现金趴在账户里闲置**，应急资金覆盖 16.7 个月，远超 6 个月安全线；股票基金 30 万。但配置里**'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']
