"""对话抽取规则测试。"""
from app.extraction import RuleExtractor


def test_extract_income():
    ex = RuleExtractor()
    actions = ex.extract("我月薪2万，老婆1万5")
    incomes = [a for a in actions if a["kind"] == "income"]
    assert len(incomes) >= 2
    amounts = sorted(a["fields"]["amount"] for a in incomes)
    assert amounts == [15000, 20000]


def test_extract_liability():
    ex = RuleExtractor()
    actions = ex.extract("房贷月供8000")
    liab = [a for a in actions if a["kind"] == "liability"]
    assert liab and liab[0]["fields"]["monthly_payment"] == 8000
    assert liab[0]["fields"]["type"] == "房贷"


def test_extract_asset():
    ex = RuleExtractor()
    actions = ex.extract("存款50万")
    assets = [a for a in actions if a["kind"] == "asset"]
    assert assets and assets[0]["fields"]["value"] == 500000


def test_extract_person_age():
    ex = RuleExtractor()
    actions = ex.extract("孩子今年12岁")
    persons = [a for a in actions if a["kind"] == "person"]
    assert persons and persons[0]["fields"]["birth_year"] == 2014
    assert persons[0]["fields"]["relation"] == "子女"


def test_extract_goal():
    ex = RuleExtractor()
    actions = ex.extract("给孩子准备教育金，目标100万")
    goals = [a for a in actions if a["kind"] == "goal"]
    assert goals and goals[0]["fields"]["target_amount"] == 1000000
