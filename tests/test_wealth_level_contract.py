"""契约守门：锁死 wealth_level 三档枚举（脆弱 / 需关注 / 稳健），防文档/引擎漂移。

Wealth Engine（app/engine/score.py）是 wealth_level 的唯一真相源。若有人把引擎改成
4/5 档（如 api-contract-v1.md 曾误写的「谨慎/良好/卓越」），本测试先红，逼着同步更新
契约文档后再改引擎。
"""
from app.engine.score import wealth_score

WEALTH_LEVELS = {"脆弱", "需关注", "稳健"}


def _expected_level(score: int) -> str:
    """冻结的 3 档映射，与 app/engine/score.py 现状一致。"""
    if score >= 75:
        return "稳健"
    if score >= 50:
        return "需关注"
    return "脆弱"


# 三组数据分别落在脆弱/需关注/稳健三档，确保枚举未被压缩成单档。
_SAMPLES = [
    {},  # score=46 → 脆弱
    {
        "assets": [{"asset_class": "cash", "value": 300000}],
        "cashflows": [
            {"flow_type": "income", "amount": 50000, "period": "月"},
            {"flow_type": "expense", "amount": 30000, "period": "月"},
        ],
    },  # score=53 → 需关注
    {
        "assets": [
            {"asset_class": "cash", "value": 1200000},
            {"asset_class": "equity", "value": 800000},
            {"asset_class": "fixed_income", "value": 600000},
        ],
        "cashflows": [
            {"flow_type": "income", "amount": 100000, "period": "月"},
            {"flow_type": "expense", "amount": 30000, "period": "月"},
        ],
        "insurance": [{"coverage": 6000000, "annual_premium": 60000}],
        "persons": [{"relation": "本人", "birth_year": 1985}],
    },  # score=76 → 稳健
]


def test_wealth_level_enum_is_closed_three_tier():
    seen = set()
    for data in _SAMPLES:
        r = wealth_score(data)
        assert r["level"] in WEALTH_LEVELS, f"非法 wealth_level: {r['level']!r}"
        assert r["level"] == _expected_level(r["score"]), (
            f"等级与分数不一致: score={r['score']} level={r['level']!r}")
        seen.add(r["level"])
    assert seen == WEALTH_LEVELS, f"三档未全覆盖，实际命中 {seen}"
