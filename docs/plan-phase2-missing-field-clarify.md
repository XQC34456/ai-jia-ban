# Phase 2 第四刀「缺数检测（字段级精准追问）」工作计划

> 状态：**待用户确认（2026-08-16）**。Phase 2 第 5 项核心工作，紧接第三刀（commit ad6e002）。
> 用户已确认：**方案 A 字段级精准追问**（AskUserQuestion）。
> 依据：主纲 Phase 2 完成标志「一句话持续完善档案」+ 原则 #3「建档是渐进式的」。

---

## 0. 这一刀的本质（一句话）

**建档路径抽空但像建档时，把笼统追问「有些金额没听清，请说得更具体」换成字段级精准追问「你刚才说有笔存款，具体存了多少钱？」——让半句话也能精准沉淀，而不是笼统打回。**

## 1. 现状取证（根因）

| 事实 | 结论 |
|------|------|
| `entry.py:58-59` 建档 gate：抽空但 `looks_like_filing` → `build_response(... summary=_FILING_CLARIFY_SUMMARY)` | 追问是**笼统文案**，不区分用户说的是存款/房贷/收入哪一类 |
| 实测「我有笔存款」（无金额）→ `extract_actions` 静默丢弃（RuleExtractor 无金额不提取）→ `looks_like_filing`=True → 笼统追问 | 用户被告知「说得更具体」，但不知道具体缺哪个数 |
| P1.3 `follow_up_questions`（followup.py）已做**回答路径**缺数检测，已接线 | 不重复造；本刀只补**建档路径**的精准追问 |
| RuleExtractor 覆盖 income/asset/liability/goal/person（无 expense）；LLM 抽取 schema 额外有 expense | 追问规则对齐 LLM 抽取能力（真实路径用 LLM） |
| `test_v27_extraction.py:113` 只断言 `status=="need_clarification"`，不断言 summary 文案 | 换文案**不破坏现有测试** |

## 2. 设计（最小改动：纯文案映射）

### 2.1 新增纯函数 `_filing_clarify(message) -> str`

有序规则表：命中第一个匹配类别 → 精准追问；无匹配 → 回退笼统 `_FILING_CLARIFY_SUMMARY`。

```python
import re

_FILING_CLARIFY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"存款|现金|活期|应急金|闲钱"), "你刚才提到存款/现金，具体有多少钱？"),
    (re.compile(r"房贷|车贷|消费贷|信用卡|月供"), "你刚才提到的负债，月供或剩余本金大概多少？"),
    (re.compile(r"支出|开销|花销|房租|学费|生活费"), "你每月支出大概多少？"),
    (re.compile(r"月薪|工资|月入|月收入|收入"), "你月收入大概多少？"),
    (re.compile(r"基金|股票|理财"), "你刚才提到的基金/股票/理财，投了多少钱？"),
    (re.compile(r"房产|房子"), "你的房产估值或房贷大概多少？"),
    (re.compile(r"教育|养老|退休|买房|创业|目标|攒|准备"), "你想存的目标金额大概多少？期限是？"),
]


def _filing_clarify(message: str) -> str:
    for pat, q in _FILING_CLARIFY_RULES:
        if pat.search(message):
            return q
    return _FILING_CLARIFY_SUMMARY
```

> 顺序说明：负债（含"房贷"）在房产前——「我有房贷」→ 负债追问，「我有房产」→ 房产追问；支出在收入前——「我每月开销」→ 支出追问（"每月"是歧义词，已从收入规则剔除，收入只匹配"月薪/工资/月入/月收入/收入"）。

### 2.2 接线

`entry.py:59` 一处改动：

```python
summary=_FILING_CLARIFY_SUMMARY   →   summary=_filing_clarify(message)
```

`_FILING_CLARIFY_SUMMARY` 保留作为回退兜底文案，不删除。

## 3. 代码落点

- **Modify `app/agent/entry.py`**：新增 `_FILING_CLARIFY_RULES` + `_filing_clarify`（约 20 行）+ 第 59 行接线（1 行）。
- **New `tests/test_filing_clarify.py`**：精准追问专项测试。
- 其余零改动：extraction / Advisor 主链 / schema / 前端 / db。

## 4. 测试（TDD，先红后绿）

| 用例 | 场景 | 断言 |
|------|------|------|
| D1 资产 | `_filing_clarify("我有笔存款")` | 含「多少钱」 |
| D2 负债 | `_filing_clarify("我有房贷")` | 含「月供」 |
| D3 收入 | `_filing_clarify("我月收入")` | 含「月收入」 |
| D4 支出 | `_filing_clarify("我每月开销")` | 含「支出」 |
| D5 基金 | `_filing_clarify("我有基金")` | 含「投了多少钱」 |
| D6 目标 | `_filing_clarify("我想给孩子准备教育金")` | 含「目标金额」 |
| D7 回退 | `_filing_clarify("我有保险")` | == `_FILING_CLARIFY_SUMMARY`（规则表不覆盖 → 笼统兜底） |
| D8 端到端 | `converse("我有笔存款")` | status==need_clarification 且 summary 含「多少钱」 |

**已有测试影响**：`test_v27_extraction.py:113` 只断言 status 不断言文案 → 保持绿；全量 pytest 确认零非预期失败。

## 5. 验证（做完必须自我验证）

1. `pytest tests/test_filing_clarify.py -v` → D1–D8 绿。
2. 全量 `pytest` → 全绿（587+）。
3. 确定性 12 题基线 → **零 diff**（本刀只动建档 gate 的 need_clarification 追问文案，不进 12 题回答路径；Q10 走 cancel reanswer 不触发此分支；重跑确认基准 json 无改动）。
4. 真机：`converse("我有笔存款")` 真实路径 → 精准追问文案出现，且确认卡/回答路径无漂移。
5. 独立 commit（只动 entry.py + 新测试 + 本计划文档）。

## 6. 不做什么（边界声明）

- **不做**：extraction 返回结构改动（区分"半成品+缺字段"）、对话式多轮澄清循环、G4 无澄清循环、保险提取、前端 UI 改动、Advisor 主链。
- **不碰**：Engine/Decision/铁律/冻结基线/schema。
- 不顺手修：Q2 G1 建档 gate 误判、extraction summary 措辞（「存款存款」）。

## 7. 风险与已知限制

| 限制 | 说明 |
|------|------|
| 只问一类 | 用户一句话多个缺失类别（"有存款和房贷"）→ 只命中第一个规则，问一类。符合原则 #5「最小澄清问题」 |
| 保险/净资产等 | `_FILING_HINT_RE` 识别但 extraction 不提取的类别 → 回退笼统兜底（可接受，不在范围） |
| 精准度靠关键词 | 「房子」追问「估值或房贷」，不再细分——细分属澄清循环（G4），不在本刀 |
