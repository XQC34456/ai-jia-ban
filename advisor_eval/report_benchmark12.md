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
  行动建议：['确认是否有应急储备，以及能覆盖几个月生活开支。', '明确这笔资金预计多久不用。', '提供月收入和月支出的估算值。', '说明是否负债以及负债情况。']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues,get_cashflow,get_allocation] content='我先理解一下你的处境。你说有 30 万现金想投资，但我想先看看你家庭目前的真实状况——毕竟「适不适合投资」取决于你现在的现金流、负债、应急储备和整体财富结构。\n\n让我先拉取你的家庭档案和财务状况。'
  chat#2：tool_calls=[无工具] content='我看到一个关键问题，得先跟你坦诚说清楚。\n\n老实说，**你现在这个「30 万适不适合投资」的问题，我暂时没法直接给你一个负责任的答案**——不是我不愿意帮，而是因为我在系统里看到的你家档案，几乎是一片空白：\n\n- 家庭成员：0 人\n- 收入记录：**没有**（0）\n- 支出记录：**没有**（0）\n- 资产、负债：**都没有**记录\n- 保险：**一份没配**\n- 目标：**没设**\n\n这意味着我'
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
  回答：这笔资金适合投资，但方向比是否投资更关键。现金严重超配、固收为零、权益接近目标上限，因此应将资金投入固收以平衡结构，而非继续增加权益。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'goal_completion', 'liquidity', 'liquidity_months', 'net_worth', 'nwc', 'other_pct', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow=0.0@comparison.A.cashflow.delta', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.0@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=0.01@comparison.A.nwc.delta', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'rfr=0.01@comparison.A.rfr.delta', 'wealth_score=3.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.surplus', 'overview.liquidity.emergency_months']
  行动建议：['将大部分资金投入固收类产品（如债券基金或固收理财）。', '暂缓增加股票投资，保持权益比例在合理区间。', '单独设立教育金账户，每月从结余中定存以逐步弥补缺口。', '评估并购买家庭保险，优先覆盖房贷和家庭成员风险。']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_allocation,get_goals,get_cashflow] content='我先了解一下这个家庭的完整情况和当前的主要矛盾，再来判断这30万该怎么用。\n\n让我先调取相关数据。'
  chat#2：tool_calls=[get_wealth_overview,get_family_profile] content='让我梳理一下这个家庭的情况。\n\n**数据掌握情况：**\n- 你现在有30万现金，但家庭整体现金有50万（占资产的62%）\n- 净资产为负（-120万），但有负债200万（可能是房贷之类）\n- 当前主要矛盾（P1优先级最高）：**资产配置适配度偏低**——现金占62%，远超20%目标上限；固收占0%，远低于30%目标下限\n- 第二个P2：**孩子教育金缺口90万**（目标100万，已备仅10万）\n-'
  chat#3：tool_calls=[run_scenario,compare_scenarios] content='现在情况很清晰了。让我用情景模拟来验证一下：你这30万现金，如果投入固收和权益，对整体配置会带来什么影响。\n\n因为这是决策类问题（投资），我需要用 run_scenario 来验证。你提到"适不适合投资"——那么核心是：你的30万属于闲钱（应急已覆盖16.7个月），但投资的**方向**才是关键，因为当前权益已经占38%超了上限，固收是0%。\n\n让我模拟一下把这30万主要投到固收的效果。'
  chat#4：tool_calls=[无工具] content='数据已经非常清楚了。情景模拟的结果直接给了我很强的证据，让我把结论组织好。\n\n先说结论：**这30万现在适合投资，但关键不在"投不投"，而在"投什么"——你的问题真正要做的决策，是把这笔钱放进哪个篮子里。** 让我把证据链讲清楚。\n\n---\n\n## 核心判断：该投，但要投固收，而不是继续加股票\n\n**为什么这笔钱确实该动起来（而不是继续躺着）**\n\n你有50万现金，占总资产的62%。而你的**应急'
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
- ❌ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我该提前还车贷还是拿钱投资？
第1轮：intent=SCENARIO_COMPARE status=need_clarification
  回答：需要补充以下信息：投资金额（元）
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_wealth_overview,get_cashflow,get_allocation] content='我先理解一下你的问题。你面临的决策是：手头有一笔资金（结合上次对话，约30万现金），是提前还车贷还是拿去投资。我需要先看清这个家庭的整体财务状况和主要矛盾。\n\n让我先调取相关数据。'
  chat#2：tool_calls=[compare_scenarios] content='我需要先澄清一个关键事实。你问的是"提前还车贷还是投资"，但我查到的负债里只有一笔房贷（200万），并没有车贷。这需要和用户确认。\n\n不过，先看看能判断的部分。让我梳理一下证据链，同时做一个对比：提前还贷 vs 拿去投资。我先跑一个情景模拟来辅助判断。\n\n让我确认——虽然工具里显示的是房贷，但你问的是"车贷"。我理解为手头有约30万现金，有考虑提前还某笔车贷（可能车贷不在系统负债里？），或者你要还'
  chat#3：tool_calls=[compare_scenarios] content='工具对提前还贷需要 method 参数。让我重新跑。同时我也要确认——系统里只有房贷。你的"车贷"我需要向你再确认一下。\n\n我先用正确的参数跑。'
  chat#4：tool_calls=[compare_scenarios] content='投资场景需要 amount 参数。让我分开跑两个场景对比。'
  chat#5：tool_calls=[run_scenario,run_scenario] content='我明白了，投资场景不支持 prepay_loan。提前还贷和投资是两个不同的场景类型。让我分别调用 run_scenario 来做。\n\n让我用正确的场景名分别跑提前还贷和投资。'
  chat#6：tool_calls=[run_scenario] content='投资固收的场景跑通了。现在我需要跑提前还贷的场景来对比。让我用正确的 method 参数格（shorten / reduce_payment）。\n\n同时我也意识到一个重要情况需要向你确认——我系统里的负债只有一笔房贷（200万，利率3.5%），并没有看到车贷。你问的"车贷"可能是系统外的另一笔负债，或者你其实指的是房贷。让我先把场景都跑一遍再和你谈。\n\n让我重跑提前还贷场景。'
  complete_json#1：keys=['amount', 'to_class']

## 4 收入下降20%能撑多久

> 变化/情景类：期望现金流/应急月数数字

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：如果收入下降 20%，我能撑多久？
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：当前最需要关注：资产配置适配度偏低（当前资产结构偏离目标配置）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'goal_completion', 'liquidity', 'liquidity_months', 'net_worth', 'nwc', 'real_estate_pct', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow=-8000.0@comparison.A.cashflow.delta', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.075@comparison.A.dti.delta', 'dti=0.3@overview.debt.dti', 'goal_completion=0.0@comparison.A.goal_completion.delta', 'liquidity=0.0@comparison.A.liquidity.delta', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'net_worth=0.0@comparison.A.net_worth.delta', 'nwc=-0.54@comparison.A.nwc.delta', 'real_estate_pct=0.0@comparison.A.real_estate_pct.delta', 'rfr=-0.54@comparison.A.rfr.delta', 'wealth_score=-17.0@comparison.A.wealth_score.delta', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.debt.dti']
  行动建议：['模拟用部分现金提前还贷，观察负债率和月供变化。', '评估将部分闲钱投入固收或权益，同时确保应急保障不受影响。', '如果收入下降比例不同，用实际数字重新模拟。']
  铁律：全部通过
  chat#1：tool_calls=[get_cashflow,get_wealth_overview,run_scenario] content='我先看一下家庭的现金流和应急资金状况，再来回答这个问题。'
  chat#2：tool_calls=[无工具] content='我看到了收入下降 20% 后的模拟结果。让我先给你一个直观的结论。\n\n---\n\n## 收入下降 20%，你能撑多久？\n\n**先从两个层面回答你：**\n\n### 一、"撑多久"——靠存量资金，你很不脆弱\n\n你的应急资金覆盖 **16.7 个月**（数据显示的是按月支出衡量的储备），即便收入下降 20%，这个数字不变——因为你没有动用这笔现金，它依然在。所以从**纯"断粮应急"的角度**，你手里近 5'
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
  回答：你的教育金目标完成的关键不在于单纯每月储蓄，而在于把闲置现金和每月结余有效配置到生息资产。当前缺口较大，但有一笔可动用的超配现金作为启动资金。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'equity_pct', 'fixed_income_pct', 'goal_1_coverage', 'goal_1_gap', 'other_pct', 'real_estate_pct']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.cashflow.savings_rate']
  行动建议：['补充孩子预计使用教育金的具体年份', '核实每月收入和支出的最新情况', '根据确认的目标年限重新规划每月投资额和资产配置']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_goals,get_cashflow,get_allocation] content='我来帮你梳理孩子教育金的问题。先看看这个家庭目前的整体情况和目标详情。\n\n让我先调取相关数据。'
  chat#2：tool_calls=[无工具] content='让我梳理一下现在掌握的情况，然后展开分析。\n\n**当前的完整图景：**\n- 教育金目标 **100 万**，已存 10 万，**缺口 90 万**，覆盖率仅 10%\n- 每月结余 **1 万**（收入 4 万，支出 3 万）\n- 手上有 **50 万现金**（占 62%），其中应急金远超安全线（16.7 个月 vs 安全 6~12 个月）\n- 固收配置为 **0%**（低于目标下限 30%）\n- '
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
  回答：按现有数据，退休资金是够的，但需警惕房贷本金计入投资及现金超配、无保险等隐患，可能动摇这一结论。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'nwc', 'rfr', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'nwc=1.24@overview.retirement.nwc', 'rfr=1.24@overview.retirement.rfr', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.wealth_score']
  行动建议：['核实家庭收入下降时养老覆盖比的变化', '评估将闲置现金投入固收后的退休资产变动情况']
  铁律：全部通过
  chat#1：tool_calls=[get_retirement,get_wealth_overview,get_wealth_issues] content='我来帮你看看退休的情况。先调取你们家的养老测算和相关数据。'
  chat#2：tool_calls=[无工具] content='我先回答你的核心问题，再看一个关键点。\n\n**结论先说：按现在的数据，你退休是够的——但有一笔"账面外的钱"不能算错。**\n\n### 为什么说"够"\n\n- 按测算，你到 60 岁退休时可投资资产能覆盖退休后的资金需求，**覆盖比（RFR）和净资产覆盖比（NWC）都是 1.24**，也就是退休需求打 8 折覆盖了，这个数字超过"刚好够"的安全线（1.0），所以系统把你的养老判定为「**健康**」象限'
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
  回答：这位家庭的账面数据其实并不缺钱，现金流和流动性都健康，真正的问题是资产配置失衡和教育金缺口，以及完全没有保险保障，导致你感觉钱不够用。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.savings_rate', 'overview.liquidity.emergency_months', 'overview.retirement.nwc', 'overview.wealth_score']
  行动建议：['确认你更想先解决资产配置调整还是教育金计划，或说明是否有其他具体担忧。', '提供具体方案对比，分析不同类型配置对家庭财富的影响。']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_issues,get_cashflow,get_wealth_overview] content=''
  chat#2：tool_calls=[无工具] content='我先不急着给建议。你说"钱越来越不够用"，我理解这句话背后可能是你在担心什么——是日常开销撑不住？还是怕哪天收入出问题？还是心里觉得攒不下钱？\n\n让我先把你家的真实账目摊开给你看，很多"感觉不够用"其实和"实际不够用"不是一回事。\n\n---\n\n**先把你的账看清了。**\n\n你的家庭月收入 **4 万**，月支出 **3 万**，每月结余 **1 万**，储蓄率 **25%**——这个数字并不差，很'
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
第1轮：intent=SCENARIO_COMPARE status=ok
  回答：已生成家庭财务分析，详见下方画像与下一步行动。
  确定性工具(metrics)：['cashflow_surplus', 'net_worth', 'wealth_score']
  关键数字：['cashflow_surplus=0.0@overview.cashflow.surplus', 'net_worth=0.0@overview.net_worth', 'wealth_score=46.0@overview.wealth_score']
  证据路径：['overview.wealth_score']
  行动建议：['提供真实月收入金额', '提供月支出金额', '告知是否有房贷、车贷等其他负债', '告知是否购买过任何保险产品']
  铁律：全部通过
  chat#1：tool_calls=[get_family_profile,get_wealth_overview,get_wealth_issues] content='让我先理解一下情况。用户问「应该买什么基金」，这是个投资决策问题。但有个关键前提——我需要先了解这个家庭的真实财务状况，才能判断「买基金」这件事本身对不对、够不够。\n\n从记忆看，用户之前说过有 30 万现金，问过「现在适不适合投资」。但我注意到系统显示的家庭数据是空的（成员 0、资产 0），可能信息还没同步完整。我需要先调用工具看看真实的家庭画像和问题清单。\n\n让我先拉取基础数据。'
  chat#2：tool_calls=[无工具] content='数据清楚地说明了问题：这不是一个「该买什么基金」的问题。系统显示的是一个**尚未建档的家庭**——成员、资产、收入、支出、目标、保单全部为 0。虽然你口头说过有 30 万现金，但系统里完全没有你的真实财务数据。\n\n而且我有责任先指出一个更根本的冲突：**你说有 30 万现金，但系统里净资产是 0。** 这意味着当前判断的依据缺失。在拿到真实数据之前，我不能假装能给你算出「买什么基金」。\n\n让我把话'
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
  回答：顾问认为提问的核心不是简单在还贷与留现金之间做二选一，而是需结合买房细节综合判断。基于现有数据，顾问指出现金超配、流动性健康、房产占比为零、配置适配度偏低，并强
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.asset_allocation.classes.real_estate.pct', 'overview.debt.dti', 'overview.liquidity.emergency_months', 'overview.wealth_score']
  行动建议：['用户需补充购房总价、首付、还贷对象及现金用途等参数']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_issues,get_cashflow,get_allocation,get_wealth_overview] content='我先理解一下你的真正问题：你在纠结「买房之前，手里的现金流/结余应该先去提前还贷，还是留作现金备用」。这是一个涉及家庭资产负债结构的选择。我需要先看看当前的风险优先级和资产全貌。\n\n让我先调取相关数据。'
  chat#2：tool_calls=[无工具] content='我先看清楚几个关键事实，再回答你这个问题——因为你问的其实不只是「还贷 vs 留现金」，而是**在买房这个大动作之前，手头的钱该怎么摆布**。\n\n我先把数据摊开看，再给你做情景模拟验证判断，而不是空口给结论。\n\n先把当前的决策困难讲清楚，我要对比「提前还贷」和「继续持有现金」两条路。先给一句实话：**这个问题的答案，取决于你要买的房子到底多大、怎么付款**——所以有几件事我需要先向你确认，也先把已'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

## 10 取消建档后继续回答原问题

> Step 4（G3 闭环）：轮1 建档话术（月收入+存款+带金额配置问题）→ 弹确认卡；自动模拟取消 = 拒绝本次建档 ≠ 拒绝回答——cancel_and_reanswer 把原问题（original_query）重新投入正常 Advisor 路径（filing_declined 跳过建档 gate，防死循环），回答原配置问题（CHECK_ALLOCATION，status=ok，真实配置指标），不再返回「好的，已忽略」。family=filed 让 CHECK_ALLOCATION 有真实配置指标可测

**验收判级**：

- ✅ 不被建档吞
- ✅ 返回类型
- ✅ 状态ok
- ✅ 铁律·数字无编造
- ✅ 铁律·source 正确
- ✅ 铁律·status 正确
- ✅ 铁律·无内部标识

**第1轮 用户**：我月收入 3 万，存款 50 万，这 30 万怎么配置？
第1轮：⚠️ ConfirmCard（建档确认卡，items=2）→ 用户取消
  → 取消建档 = 拒绝本次建档 ≠ 拒绝回答：原问题重新回答 ↓
第1轮：intent=CHECK_ALLOCATION status=ok
  回答：当前最需要关注：资产配置适配度偏低（当前资产结构偏离目标配置）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'alternative_pct', 'cash_pct', 'cashflow_surplus', 'dti', 'equity_pct', 'fixed_income_pct', 'liquidity_months', 'net_worth', 'other_pct', 'real_estate_pct', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'alternative_pct=0.0@overview.asset_allocation.classes.alternative.pct', 'cash_pct=0.625@overview.asset_allocation.classes.cash.pct', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'equity_pct=0.375@overview.asset_allocation.classes.equity.pct', 'fixed_income_pct=0.0@overview.asset_allocation.classes.fixed_income.pct', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'other_pct=0.0@overview.asset_allocation.classes.other.pct', 'real_estate_pct=0.0@overview.asset_allocation.classes.real_estate.pct', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.retirement.nwc']
  行动建议：['明确这笔钱是补教育金缺口还是优化收益']
  铁律：全部通过
  chat#1：tool_calls=[record_family_info] content='我来帮您分析。您提到了月收入3万、存款50万，以及"这30万怎么配置"。首先我需要理解这个"30万"的配置诉求——这可能是一个理财配置目标，但从信息来看还不明确。\n\n让我先提取已有的明确信息来建档。'

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
  回答：你的现金流账面数据很健康，每月收支有结余，储蓄率不低，且支出结构以可控的弹性支出为主，现金流维度表现稳健偏宽裕。但现金流健康不等于钱够用，真正的问题在于资产配置
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  证据路径：['overview.cashflow.surplus', 'overview.liquidity.emergency_months', 'overview.wealth_score']
  行动建议：['告知孩子教育金的大致使用年份', '确认每月结余目前是否用于投资', '在信息明确后，进行配置模拟分析']
  铁律：全部通过
  chat#1：tool_calls=[get_cashflow,get_wealth_overview,get_wealth_issues] content='我先调取你的现金流数据和相关背景，看看整体的收支状况。'
  chat#2：tool_calls=[无工具] content='我帮你把这家人的现金流看清楚了。先说结论，再说它到底意味着什么。\n\n## 你的现金流现状\n\n你家的现金流账面数据很健康，用两句话就能概括：\n\n- **每月收入 4 万，支出 3 万，结余 1 万**，储蓄率 25%。这个结余水平不算低。\n- 支出结构里，**固定支出只有 3000（教育），弹性支出 1.5 万（日常）**，说明绝大部分开销是可控的，不是压死人的刚性负担。\n\n所以单看「现金流」，你家'
  complete_json#1：keys=['intent']
  complete_json#2：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']

**第2轮 用户**：我收入多少你不是知道吗，为什么还要问
第2轮：intent=EXPLAIN_RESULT status=ok
  回答：当前最需要关注：资产配置适配度偏低（当前资产结构偏离目标配置）
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_surplus', 'dti', 'liquidity_months', 'net_worth', 'wealth_score']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'dti=0.3@overview.debt.dti', 'liquidity_months=16.7@overview.liquidity.emergency_months', 'net_worth=-1200000.0@overview.net_worth', 'wealth_score=78.0@overview.wealth_score']
  行动建议：['确认房贷月供是否已从收入中扣除，以判断结余是还贷前还是还贷后的余额', '明确本次咨询的方向（具体资金安排或整体财务审视）']
  铁律：全部通过
  chat#1：tool_calls=[get_wealth_overview,get_wealth_issues] content='你说得对，是我多此一举了——你的收入确实在我们这有记录，不该再反问你。\n\n我先用现有数据帮你把情况梳理清楚，这样以后就不用绕弯子了。\n\n让我先确认一下当前的整体状况和问题优先级。'
  chat#2：tool_calls=[无工具] content='好的，你的情况我都调出来了，不用再问你了。\n\n先说清楚你的基本面，让你心里有数：\n\n**账面上你其实不缺钱**\n- 月收入 4 万，支出 3 万，每月结余 1 万，储蓄率 25%\n- 应急资金覆盖 16.7 个月，远超 6 个月的安全线，流动性非常充裕\n- 房贷月供占收入 30%，在合理范围内\n\n所以你要先放下「钱不够用」这个感觉——数据上不是钱不够，是你**感觉**钱不够，这种感觉来自下面几个真'
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
  回答：该教育金目标为整笔金额，当前存在较大缺口，完成的关键在于确定使用期限与启动正确的积累方式，并将闲置现金调度起来，而非单纯依靠每月硬攒。
  确定性工具(metrics)：['ALLOCATION_LOW_FITNESS_001_allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months', 'GOALS_GAP_001_gap', 'cashflow_expense', 'cashflow_income', 'cashflow_savings_rate', 'cashflow_surplus', 'goal_1_coverage', 'goal_1_gap']
  关键数字：['ALLOCATION_LOW_FITNESS_001_allocation_fitness=51.0@issues.ALLOCATION_LOW_FITNESS_001.metric.allocation_fitness', 'ALLOCATION_LOW_FITNESS_001_real_estate_pct=0.0@issues.ALLOCATION_LOW_FITNESS_001.metric.real_estate_pct', 'DECISION_IDLE_CASH_001_emergency_months=16.7@issues.DECISION_IDLE_CASH_001.metric.emergency_months', 'GOALS_GAP_001_gap=900000.0@issues.GOALS_GAP_001.metric.gap', 'cashflow_expense=30000.0@overview.cashflow.expense', 'cashflow_income=40000.0@overview.cashflow.income', 'cashflow_savings_rate=0.25@overview.cashflow.savings_rate', 'cashflow_surplus=10000.0@overview.cashflow.surplus', 'goal_1_coverage=0.1@goals.1.coverage', 'goal_1_gap=900000.0@goals.1.gap']
  证据路径：['overview.cashflow.savings_rate', 'overview.cashflow.surplus']
  行动建议：['提供教育金预计使用的时间点', '在获得期限信息后，进行情景模拟测算']
  铁律：全部通过
  chat#1：tool_calls=[get_goals,get_wealth_issues,get_family_profile,get_cashflow] content='我先理解你的问题：你关注的是「孩子教育金」这个目标，缺口很大（900,000），想知道怎么完成。这是一个目标实现路径的问题，我需要先看清家里的整体状况和这个目标的具体要求。\n\n让我先调取家庭全貌、目标详情和问题清单。'
  chat#2：tool_calls=[无工具] content='我来梳理一下这个目标和你家的整体情况。\n\n## 先看清楚：这个教育金目标到底缺多少\n\n你的教育金目标 100 万，目前只备了 10 万，缺口 90 万。而这是一个「整笔金额」目标（lump_sum），不是每年支出的那种，意味着到期时要一次性拿出一笔钱。数据里目前没有设定**达成期限**（target_date 是空的），也没有设定**每月应存金额**（monthly_needed 也是空的）——这'
  complete_json#1：keys=['evidence', 'finding', 'missing', 'next_actions', 'recommendations', 'refuse', 'summary', 'tradeoffs', 'uncertainty']
