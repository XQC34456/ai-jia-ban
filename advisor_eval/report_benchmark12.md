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
  行动建议：['核实并补充收入、支出数据', '评估现有保险覆盖，补充必要的保障型产品']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues,get_cashflow,get_allocation] content='我先来了解一下你的家庭财务状况，这样才能给出针对性的建议。'
  chat#2：tool_calls=[无工具] content='我看了一下系统里的家庭数据，这里有件很重要的事需要先跟你讲清楚。\n\n## 现在的局面是：我几乎没有你的任何数据\n\n你说的"有 30 万现金"，但系统里在资金端、收入端、支出端、家庭结构端**全部是空白**——没有你的收入、没有支出、没有家庭其他资产，甚至连你是单身还是已婚有孩子都不知道。\n\n我不能在这样一个信息真空里，就直接回答你"30 万该不该投资、投到哪"。那是不负责任的。\n\n不过在追问之前，'
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
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.0@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=0.01@comparison.A.nwc.delta', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'rfr=0.01@comparison.A.rfr.delta', 'wealth_score=3.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.liquidity.emergency_months', 'overview.wealth_score']
  行动建议：['询问此前股票资金的来源背景']
  铁律：❌ 数字无编造
  chat#1：tool_calls=[get_wealth_overview,get_wealth_issues,get_goals,get_allocation] content='我来帮你分析这个投资决策。先让我了解一下你家庭的完整状况。\n\n让我先看看你的财富全景和问题清单，理解你现在的处境。'
  chat#2：tool_calls=[run_scenario] content='我已经掌握了你的家庭全貌。让我来帮你梳理这个投资决策。\n\n先看几个关键事实：\n- 你手里 30 万现金，加上已有流动资产总共 50 万在现金里\n- 你的资产配置里现金占比非常高，固收却是 0%\n- 你的孩子教育金还有很大缺口\n- 你没有任何保险\n\n在给方向之前，让我用情景模拟验证一下"把现金投入配置"会怎样。你的主要矛盾是**资产配置适配度偏低（P1）**，这直接关系你"这 30 万该不该动、往哪'
  chat#3：tool_calls=[无工具] content='我已经得到了清晰的模拟结果。现在我可以给你一个扎实的判断。\n\n---\n\n**结论先行：你手里这 30 万现金，不应该是"要不要投"的问题，而是"投哪一类"。答案很明确——不是再投股票，而是补上你几乎为零的固收（稳健资产）。**\n\n为什么这么判断，我给你拆开讲。\n\n**一、你的真问题不是"钱多了该不该投资"，而是"钱全躺在现金里、结构失衡"**\n\n看你的配置现状就知道问题有多集中：\n- 你的流动资产'
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
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我该提前还车贷还是拿钱投资？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：顾问指出用户提及车贷，但系统中只有一笔房贷，需先澄清负债性质，才能判断提前还款还是投资更优。基于现有数据，家庭现金超配且资产配置偏离目标，可先进行方向性分析，但
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.surplus', 'overview.wealth_score']
  行动建议：['补充车贷具体情况', '核实资金用途和风险承受力']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_family_profile,get_cashflow,get_allocation] content='我需要先理解这个家庭的全貌和优先问题，然后才能给出有依据的建议。让我先调用工具获取数据。'
  chat#2：tool_calls=[无工具] content='我需要先明确一个关键事实：用户问的是「车贷」，但我看到这个家庭只有一笔负债——是房贷 200 万、利率 3.5%、月供 1.2 万。我需要确认用户说的「车贷」是否就是这笔负债，还是另外有一笔我没看到的信息。\n\n让我先看看是否有车贷的更多信息，同时理解用户手上到底有多少可用于决策的现金。\n\n从数据看，这个家庭的情况很清晰了。我先梳理一下我看到的事实，然后再调用情景模拟工具来验证不同的资金安排方向。\n'
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
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.debt.dti', 'overview.liquidity.emergency_months', 'overview.retirement.rfr']
  行动建议：['明确收入下降的性质（短期还是长期）', '核实是否还有其他收入来源']
  铁律：❌ 数字无编造
  chat#1：tool_calls=[get_cashflow,get_wealth_overview,get_wealth_issues] content='我来帮你分析这个关键问题。先获取家庭现状数据来模拟收入下降的影响。\n\n让我先调取现金流和整体状况的数据。'
  chat#2：tool_calls=[run_scenario] content='我来模拟收入下降 20% 对家庭应急能力的影响。'
  chat#3：tool_calls=[无工具] content='数据已经拿到了，我来分析这个情景。\n\n先理清一个关键点：**"能撑多久"其实有两层含义**，我分开说。\n\n---\n\n## 你问的"撑多久"，答案取决于你指的是哪件事\n\n### 第一层：靠手头现金能撑几个月？\n\n从数据看，你的家庭持有 **50 万现金** 作为流动资产，同时每月的支出是 **3 万**。也就是说，即便收入完全中断、一分钱不进账，你现在的现金池也能覆盖约 **16.7 个月的支出**'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 5 孩子教育金目标怎么完成

> 目标类：期望目标缺口数字 + 行动

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ❌ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：这个孩子教育金目标怎么完成？
第1轮：intent=CHECK_GOALS status=need_clarification
  回答：需要补充以下信息：孩子年龄和目标用款年份、除房贷外的其他负债信息
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'goal_completion', 'liquidity', 'net_worth', 'nwc', 'other_pct', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.0@comparison.A.dti.delta', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=-6.7@comparison.A.liquidity.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=0.01@comparison.A.nwc.delta', 'nwc=0.08@comparison.A.nwc.delta', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'rfr=0.01@comparison.A.rfr.delta', 'rfr=0.08@comparison.A.rfr.delta', 'wealth_score=-2.0@comparison.A.wealth_score.delta', 'wealth_score=0.0@comparison.A.wealth_score.delta']
  行动建议：['补充孩子当前年龄及预计用款年份。', '确认是否存在其他负债（如车贷）及其金额和期限。']
  铁律：全部通过
  chat#1：tool_calls=[get_goals,get_wealth_issues,get_cashflow,get_allocation] content='我来帮你分析教育金目标的达成路径。先让我调取完整的目标数据和家庭现状。'
  chat#2：tool_calls=[run_scenario,run_scenario] content='让我跑一个情景模拟，看看把闲置现金配置到固收/权益后对教育金目标的帮助。'
  chat#3：tool_calls=[无工具] content='让我梳理一下数据，给用户一个清晰的回答。\n\n从数据来看，有几个关键点需要先对齐概念。你问「这个教育金目标怎么完成」，但其实这个问题的答案，跟你家庭当前最大的一个结构性矛盾是绑在一起的。\n\n---\n\n## 先说结论：教育金的缺口，不是靠"多存一点"能填的\n\n你在问「怎么完成」，但你真正的决策是：**怎么用好手里那 50 万趴着不动的现金 + 每月 1 万结余，去把 90 万缺口填上，同时不把家庭其他'
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
  回答：按当前趋势，退休是够的，但'够'得有点松，且建立在房贷正常清掉、教育金不挤占的前提上。真正的短板在于资产配置适配度偏低，现金占比过高、固收为零，若现金继续闲置，
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'nwc', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'nwc=1.24@overview.retirement.nwc', 'rfr=1.24@overview.retirement.rfr', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.liquidity.emergency_months', 'overview.retirement.nwc', 'overview.retirement.rfr', 'overview.wealth_score']
  行动建议：['核实当前现金和固收的具体占比，制定再配置方案。', '确认退休年龄和教育金使用计划，以便精确评估对退休覆盖的影响。', "若需要，可测算'重新配置后退休覆盖比'与'维持现金'的对比。"]
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_retirement,get_wealth_issues,get_wealth_overview] content='我先了解一下这个家庭的全貌和养老测算数据，同时看看主要问题清单。'
  chat#2：tool_calls=[无工具] content='数据齐了，我来回应你「退休够不够」这个问题。\n\n## 结论先说：按当前趋势，退休是够的，但"够"得有点松\n\n先说一个好消息，再讲两个必须放在心上的前提。\n\n**测算数据本身是健康的。** 按你现在家庭的情况推演到退休时，可用于退休的资产对退休资金需求是**有覆盖的**,测算给出的覆盖比（RFR 和 NWC）都在健康区间，落在"养老健康"象限。也就是说，**如果只看"退休这个目标本身"，你并不缺钱*'
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
第1轮：intent=CHECK_ISSUES status=ok
  回答：你的‘钱不够用’不是收入问题，而是钱摆错了位置、目标没有抓手。当前每月有结余、储蓄健康，但资金闲置过多、配置失衡，且教育金有缺口、无任何保险，这些才是真正的压力
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.liquidity.emergency_months', 'overview.retirement.rfr']
  行动建议：['梳理‘钱不够用’的具体所指，是每月紧张、攒不下钱，还是担心孩子教育金。', '确认教育金的使用时间与目标金额，判断是否适合配置波动稍高的资产。', '核实当前家庭是否已有任何保险，如有单位保障需评估覆盖范围与缺口。']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues,get_cashflow] content=''
  chat#2：tool_calls=[无工具] content='我理解你的感受——"钱越来越不够用"，这种感觉往往不是账面上缺了多少钱，而是每月盯着支出、担心这里那里要花钱的那种紧绷感。让我先陪你一起看看，这个家现在的钱到底是怎么流动的。\n\n先跟你确认一下我对你家现状的理解，然后咱们一起拆解。\n\n---\n\n## 先说结论：你的"不够用"，未必是收入不行，而是三件事挤在一起\n\n### 一、你其实不穷，但你的钱"睡"得太多了\n\n你目前的情况是这样的：\n\n- **月'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 8 应该买什么基金

> 纯知识：无档案也应给有效通用回答，且不编造家庭数字

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ❌ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我应该买什么基金？
第1轮：intent=CHECK_ALLOCATION status=need_clarification
  回答：需要补充以下信息：家庭人口数、月收入与支出、是否有房贷等负债、资金用途（购房、养老等）、风险承受能力
  确定性工具(metrics)：['alternative_pct', 'cash_pct', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.0@overview.asset_allocation.classes.cash.pct', 'cashflow_surplus=0.0@overview.cashflow.surplus', 'equity_pct=0.0@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'net_worth=0.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=46.0@overview.wealth_score']
  行动建议：['咨询顾问协助建档', '顾问据此给出方向性判断']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues] content='我先了解一下这个家庭的完整状况，才能判断该不该聊基金、以及聊什么类型的基金。\n\n让我读取财务全景和问题清单。'
  chat#2：tool_calls=[无工具] content='我先停下来，跟您说句实话——**现在还没到聊"买哪只基金"的时候**。\n\n我读取到的家庭档案是这样的：这个家庭目前**还没有建档**，系统里显示的是零成员、零资产、零收支、零目标——你刚才提到的"30 万现金"，在系统记录里其实也还没有体现。也就是说，我现在手上**没有任何真实数据**能支撑我去判断"买什么基金"。\n\n而且更重要的是，哪怕假设这 30 万都是你自己的钱，答案也**不是闭着眼睛选一只'
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
  回答：需要先确认几个关键信息，才能就‘买房、还贷还是留现金’给出真正有价值的建议。目前的核心矛盾是再买房会同时踩中资产配置适配度偏低和教育金缺口两个已有风险点。房贷利
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.liquidity.emergency_months', 'overview.retirement.nwc']
  行动建议：['告知新房总价与首付金额', '确认‘还贷’的具体对象（现有房贷或其他借款）及利率', '提供孩子预计使用教育金的年龄']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_overview,get_wealth_issues,get_allocation,get_cashflow,get_family_profile] content='我来帮你理清这个决策。先让我看看你家现在完整的财务状况。'
  chat#2：tool_calls=[无工具] content='我注意到一个关键点需要先跟你确认——你之前问过"还车贷"，但我看到的系统里你名下只有**一笔 200 万的房贷**，没有车贷记录。这直接影响整个判断，所以我先把账目说清楚，再帮你理这个"买房还贷 vs 留现金"的决策。\n\n先说结论性的框架，然后我需要你补充几个信息才能给你真正有价值的建议。\n\n---\n\n## 先看你现在卡在什么位置\n\n从你家的数据看，你现在的核心矛盾**不是"还贷还是投资"**，而'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 10 取消建档后继续回答原问题

> Step 4（G3 闭环）：轮1 建档话术（月收入+存款+带金额配置问题）→ 弹确认卡；自动模拟取消 = 拒绝本次建档 ≠ 拒绝回答——cancel_and_reanswer 把原问题（original_query）重新投入正常 Advisor 路径（filing_declined 跳过建档 gate，防死循环），回答原配置问题（CHECK_ALLOCATION，status=ok，真实配置指标），不再返回「好的，已忽略」。family=filed 让 CHECK_ALLOCATION 有真实配置指标可测

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ❌ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我月收入 3 万，存款 50 万，这 30 万怎么配置？
第1轮：⚠️ ConfirmCard（建档确认卡，items=2）→ 用户取消
  → 取消建档 = 拒绝本次建档 ≠ 拒绝回答：原问题重新回答 ↓
第1轮：intent=CHECK_ALLOCATION status=ok
  回答：当前最需要关注：资产配置适配度偏低（配置适配度 51 分）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'other_pct', 'real_estate_pct']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct']
  证据路径：['overview.asset_allocation.classes.real_estate.pct']
  行动建议：['明确这笔钱的用途和时间规划', '确认风险承受能力和教育金使用时间']
  铁律：❌ 数字无编造
  chat#1：tool_calls=[record_family_info] content='我理解您的问题是希望配置一笔资金，但我需要明确一下：您提到存款50万，说"这30万怎么配置"，我需要确认这30万是否是从存款50万中划出的部分来进行规划。\n\n让我先为您建立基础的家庭财务档案信息。您提到月收入3万、存款50万，我来先记录这些信息。'

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
  回答：你的现金流本身是健康的，每月有结余，储蓄率和负债率都在安全区间。但真正的压力不在每月钱够不够，而在于钱躺在那里没有发挥该有的作用，存在配置失衡、教育金缺口和现金
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.debt.dti', 'overview.liquidity.emergency_months']
  行动建议：["明确'不够用'的具体含义。", '做闲置现金转固收的情景模拟。', '做教育金每月定存金额的情景模拟。']
  铁律：全部通过
  chat#1：tool_calls=[get_cashflow,get_wealth_issues,get_wealth_overview] content=''
  chat#2：tool_calls=[无工具] content='你的现金流我已经调出来看了一遍。先给你一个整体判断，再拆开讲。\n\n---\n\n## 一句话结论\n\n**你的现金流本身是健康的——这不是你需要担心的地方。**真正的压力不在"每月钱够不够"，而在"钱躺在那里没有发挥该有的作用"。\n\n---\n\n## 现金流全景\n\n**每月进账**：工资 4 万（唯一收入来源）\n\n**每月支出**：3 万，其中——\n- **固定支出**：教育 3 千（这部分不能省）\n- '
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

**第2轮 用户**：我收入多少你不是知道吗，为什么还要问
第2轮：intent=EXPLAIN_RESULT status=ok
  回答：顾问确认收入数据已知，提问是为了明确用户具体困惑指向哪一笔账。现金流本身健康，问题在于资金配置和风险保障缺口。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.liquidity.emergency_months', 'overview.retirement.nwc', 'overview.wealth_score']
  行动建议：["向用户澄清'不够用'具体指哪一笔账", '核实教育金目标与当前储备数据是否准确', '评估应急金合理规模，并规划超额资金用途', '分析家庭保障缺口，探讨保险配置方案']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_overview,get_cashflow,get_wealth_issues] content='你说得对，之前确实聊过，我先跟你确认一下我看到的现状，看看有没有漏了什么新变化。\n\n让我调一下你的最新数据，用事实来对齐，不凭记忆说话。'
  chat#2：tool_calls=[无工具] content='你说得对，你的收入我这边确实有记录——月收入 4 万、每月结余 1 万、储蓄率 25% 这些都在数据里，我不用问你。\n\n我之所以会问，是因为**收入只是起点**，真正决定"钱够不够用"的不是进账多少，而是钱怎么摆。我缺的不是你的收入数字，而是你心里那个具体的困惑——你说"钱越来越不够用"，那你算的到底是哪一笔账？\n\n我先给你对一下我看到的事实，你看看是不是同一件事：\n\n**你的现金流本身是健康的*'
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
  回答：教育金目标存在真实缺口，但现金流健康。解决思路是先调动过剩现金补仓固收，再设定每月定存计划。缺乏目标日期和每月定存金额，无法给出具体计算，需要用户补充信息。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'goal_1_coverage', 'goal_1_gap']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap']
  证据路径：['overview.cashflow.savings_rate']
  行动建议：['补充孩子预计用钱的时间点，设定目标日期', '设定每月定存金额', '开始每月定存，使教育金覆盖率逐步上升']
  铁律：全部通过
  chat#1：tool_calls=[get_goals,get_cashflow,get_wealth_issues] content='我先了解一下家庭的目标和当前资金状况，才能给你真正可落地的方案。'
  chat#2：tool_calls=[无工具] content='先给你说清楚当前这笔教育金的真实处境，再看怎么补。\n\n**现在的状况**\n\n你为孩子教育金设的目标是 100 万，目前已经备了 10 万，缺口是 90 万（coverage 只有 10%）。这是 P2 的问题——不是最急的 P1，但它是真实存在的硬缺口，不像现金闲置那种"钱多到不知道放哪"，这个是实实在在差一大截。\n\n关键点在于：**你的现金流本身是健康的**——每月收入 4 万、支出 3 万、结'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']
