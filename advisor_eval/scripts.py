"""6 个观察点的多轮对话剧本（共享同一 family_id，连续对话）。

措辞刻意避开 RuleExtractor 的建档正则（月薪 X 万 / 房贷月供 X / 存款 X 万 /
房子值 X 万 / 孩子 X 岁 / 目标 X 万），否则 converse 会先走建档抽取返回
ConfirmCard，到不了 advisor 链路。每个观察点只测「顾问感」，不测建档。
"""
from __future__ import annotations

from .family import add_income, add_insurance

__all__ = ["SCRIPTS", "DIMENSIONS"]

# 顾问感分项（统一 4 维，各观察点声明适用哪些）
DIMENSIONS = {
    "understanding": "理解问题：是否听懂用户真正的意图/处境，而非停留在字面",
    "advisory": "顾问行为：是否给出顾问式建议与行动，而非问答式给结论",
    "continuity": "上下文连续性：是否记住并利用本轮之前的信息（含纠正、新事实、旧结论）",
    "reasoning": "解释与权衡：是否有证据+权衡支撑结论，而非空口给方向",
}

# 每个观察点 = 一段连续对话。turn 的 pre_change 在「发本轮消息之前」执行
# （评测专用外部家庭状态变更，不经 converse/API，不产生对话记忆）。
SCRIPTS: list[dict] = [
    {
        "id": "obs1_remember",
        "title": "观察点1：真的记得我刚说的话",
        "turns": [
            {"message": "我爸妈年纪大了，我想给他们多留点养老的钱", "pre_change": None},
            {"message": "那这笔钱你建议我怎么安排更稳妥？", "pre_change": None},
        ],
        "expect_status": None,
        "dimensions": ["continuity", "understanding"],
        "judge_question": (
            "第二轮用户说「这笔钱」时，AI 是否接住了第一轮「给爸妈留养老钱」这个上下文"
            "（而不是当成一句孤立的、无指向的资产配置提问）？"
        ),
    },
    {
        "id": "obs2_proactive_gap",
        "title": "观察点2：主动发现信息缺口",
        "turns": [
            {"message": "我想再买一套房子做投资，你觉得该不该？", "pre_change": None},
        ],
        "expect_status": None,
        "dimensions": ["advisory", "understanding"],
        "judge_question": (
            "在用户没给预算、首付、现有资金、风险承受任何信息的情况下，AI 是否主动追问"
            "缺失的关键信息（而非直接给「该买/不该买」的结论）？"
        ),
    },
    {
        "id": "obs3_reevaluate",
        "title": "观察点3：纠正后重新判断",
        "turns": [
            {"message": "我想拿五十万去炒股，搏一把", "pre_change": None},
            {"message": "不好意思我说反了，不是炒股，我是想提前还房贷", "pre_change": None},
        ],
        "expect_status": None,
        "dimensions": ["continuity", "advisory"],
        "judge_question": (
            "第二轮用户纠正「不是炒股，是提前还房贷」后，AI 是否推翻第一轮的炒股分析、"
            "按提前还贷重新判断（而非含糊带过或坚持旧方向）？"
        ),
    },
    {
        "id": "obs4_invalidation",
        "title": "观察点4：数据变化后旧结论失效",
        "turns": [
            {"message": "我现在最大的财务风险是什么？", "pre_change": None},
            # 外部状态变更：4A 加收入（改现金流），4B 补保险（改保障维度）。
            # 每项带 label + expect_stale，报告据此区分「覆盖不足」vs「链路正常」。
            {"message": "那我现在的情况有没有什么变化？",
             "pre_change": [
                 {"fn": add_income, "expect_stale": True,
                  "label": "4A 加收入（改 cashflow_surplus / dti / rfr）"},
                 {"fn": add_insurance, "expect_stale": True,
                  "label": "4B 补保险（改 insurance_count / total_coverage，P1 保障维度）"},
             ]},
        ],
        "expect_status": None,
        "dimensions": ["continuity", "reasoning"],
        "judge_question": (
            "家庭数据在用户不知情的情况下发生了变化（补保险、收入增加），第二轮 AI 是否"
            "意识到「之前基于旧数据的判断已经不再成立」并重新评估（而非照搬旧结论）？"
        ),
        "capture_invalidation": True,  # 记录 judgment/validity_conditions/stale
    },
    {
        "id": "obs5_synthesis",
        "title": "观察点5：把工具结果转成建议而非播报",
        "turns": [
            {"message": "我的养老准备到底够不够？", "pre_change": None},
        ],
        "expect_status": None,
        "dimensions": ["advisory", "reasoning"],
        "judge_question": (
            "AI 是把养老测算结果转化成了「结合你情况的行动建议」，还是只是把指标数字"
            "报一遍（数据播报）？"
        ),
    },
    {
        "id": "obs6_overall_advisor_feel",
        "title": "观察点6：连续对话后仍像顾问而非问答机器人",
        "turns": [],  # 无独立剧本，用观察点1-5整段对话做整体评估
        "expect_status": None,
        "dimensions": ["understanding", "advisory", "continuity", "reasoning"],
        "judge_question": (
            "把观察点1-5连成一段对话看，这个 AI 整体上像不像一个「记得上下文、主动追问、"
            "能纠正、把数据变成建议」的真人财富顾问，还是更像一个「每问必答但不记事的"
            "高级问答机器人」？"
        ),
    },
]
