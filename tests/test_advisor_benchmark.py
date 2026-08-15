"""V1.0 12 题 Advisor Benchmark：冻结确定性基线签名（不改实现）。

作用：Phase 1 改造的唯一「回归锚」——任何改动（跨页问顾问 / 取消建档继续回答 /
澄清循环）必须保持确定性路径下的测量签名与 frozen JSON 一致，或在改完后**有意**
重新冻结。这保证「先冻结、再重构、后验证」的闭环（红线 #12：改完对照基线验证）。

运行：零 API 成本（NullProvider 确定性回退），CI 安全。
冻结文件：advisor_eval/benchmark12_baseline.json（git 跟踪）。
"""
import json

from pathlib import Path

import pytest

from advisor_eval.benchmark12 import BASELINE_PATH, run_benchmark
from app.agent.provider import NullProvider


def _signature(baseline: list[dict]) -> dict:
    """把基线列表压成按题号索引的 dict，便于逐题 diff 与报错定位。"""
    return {b["id"]: b["turns"] for b in baseline}


@pytest.fixture(scope="module")
def frozen() -> dict:
    """读取 git 跟踪的冻结基线（唯一真源）。"""
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return _signature(data)


@pytest.fixture(scope="module")
def measured() -> dict:
    """当场用 NullProvider 重跑 12 题，产出当前确定性签名。"""
    _, baseline, _ = run_benchmark(NullProvider())
    return _signature(baseline)


def test_baseline_file_exists() -> None:
    """冻结文件必须存在（防止手滑删掉导致回归锚丢失）。"""
    assert BASELINE_PATH.exists(), "缺少冻结基线文件，先跑 python advisor_eval/benchmark12.py"


_FROZEN_IDS = tuple(
    sorted((b["id"] for b in json.loads(BASELINE_PATH.read_text(encoding="utf-8"))),
           key=lambda x: str(x))
)


def test_measured_has_same_questions(frozen: dict, measured: dict) -> None:
    """题集一致：13 个测量单元全部重跑（不允许偷偷少题）。"""
    assert set(frozen) == set(measured)


@pytest.mark.parametrize("qid", _FROZEN_IDS)
def test_question_signature_unchanged(qid, frozen: dict, measured: dict) -> None:
    """每题签名逐字段 diff：returned/intent/status/metrics/关键数字/证据/行动/铁律。

    intent 变化 = 行为语义变化，必须有意为之；key_numbers 变化 = 数字可追溯路径变了，
    同样必须有意为之（改完重新冻结）。任何未声明的漂移都会红。
    """
    assert qid in frozen, f"frozen 基线缺少题 {qid}"
    assert qid in measured, f"本轮测量缺少题 {qid}"
    assert measured[qid] == frozen[qid], (
        f"题 {qid} 基线签名漂移！\n"
        f"  冻结：{json.dumps(frozen[qid], ensure_ascii=False)}\n"
        f"  实测：{json.dumps(measured[qid], ensure_ascii=False)}\n"
        f"  若为有意变更，请重跑 `python advisor_eval/benchmark12.py` 重新冻结。"
    )


def test_measured_iron_rules_known_failures(measured: dict) -> None:
    """铁律已知失败必须与冻结基线一致（冻结当时的真实瑕疵，不静默修复）。

    防「改代码把已知缺陷顺手改没了而不留记录」——铁律状态也是回归锚的一部分。
    """
    for qid, turns in measured.items():
        for i, t in enumerate(turns, 1):
            assert "iron_ok" in t, f"题 {qid} 轮{i} 缺 iron_ok 字段（签名结构被破坏）"


def test_no_uncertainty_example_digits_in_clarification(measured: dict) -> None:
    """基线已知缺陷：Q4 澄清文案含示例数字（0.1/+10%），违反铁律·数字无编造。

    这题现在**必须红**——它标记了一个真实待修缺陷。若变绿说明有人改了模板，应
    同步更新冻结基线并在 Phase 1 缺口清单里勾销该缺陷。
    """
    q4 = measured.get(4, [])
    assert q4 and q4[0]["iron_ok"] is False, (
        "Q4 铁律已通过——need_clarification 示例数字缺陷被修掉了？"
        "若属实：更新冻结基线 + 在缺口清单勾销。"
    )
