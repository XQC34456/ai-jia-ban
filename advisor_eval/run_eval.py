"""AI 顾问实战验收主入口：跑 6 观察点 → 铁律断言 + LLM 裁判 → 汇总 report.md。

用法：
    python advisor_eval/run_eval.py            # 真实 DeepSeek 评测
    python advisor_eval/run_eval.py --dry-run  # 结构自检（NullProvider，不调 LLM）

评测口径（用户拍板）：
1. converse() 唯一真实评测入口，真实 DeepSeek，不用 FakeLLM。
2. 1 个典型中国家庭 fixture，6 观察点共享同一 family_id（连续对话）。
3. 观察点4 家庭状态变化用 db.apply_action（保险用 SQL 直插），标注「评测专用外部
   状态变更」，不经 converse/API、不产生对话记忆。
4. 观察点4 记录 judgment/validity_conditions/状态变化/detect_invalidation/第二轮重判。
5. LLM Judge 独立裁判，每分附原文证据。
6. 铁律类程序判定，不交 LLM。
7. 顾问感 1-3 分制，分项+总分+理由+证据。
8. 报告输出 advisor_eval/report.md。
9. 目标不是高分，是找真实 DeepSeek 顾问链的第一批硬伤。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# 项目根进 sys.path，保证 `from app import db` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db
from app.agent.entry import converse
from app.agent.providers import get_provider
from app.agent.response import build_validity_conditions
from app.schemas.agent import AgentResponse
from app.services import build_overview

from .family import build_family
from .judge import judge_advisor_feel
from .rubric import build_transcript, resp_to_text, run_iron_rules
from .scripts import SCRIPTS

__all__ = ["main", "run_observation"]

REPORT_PATH = Path(__file__).resolve().parent / "report.md"


def load_dotenv() -> None:
    """加载项目根 .env（与 main._load_dotenv 同逻辑）。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


class TracingProvider:
    """包装真实 provider，记录 chat/complete_json 原始返回，观测 JSON 稳定性。

    不改任何产品逻辑——只透传 + 记录。记录粒度：
    - chat：每次返回的 tool_calls 名称序列 + content 前 200 字（None 记失败）
    - complete_json：返回 dict 的 keys（None 记 parse 失败）
    """

    def __init__(self, inner):
        self._inner = inner
        self.chat_log: list[dict | None] = []
        self.complete_log: list[dict | None] = []

    def reset(self) -> None:
        self.chat_log.clear()
        self.complete_log.clear()

    def chat(self, messages, tools=None):
        resp = self._inner.chat(messages, tools)
        self.chat_log.append(None if resp is None else {
            "content_head": (resp.get("content") or "")[:200],
            "tool_calls": [tc.get("name") for tc in (resp.get("tool_calls") or [])],
        })
        return resp

    def complete_json(self, system, user, schema, context=None):
        data = self._inner.complete_json(system, user, schema, context)
        self.complete_log.append(None if data is None else {"keys": sorted(data.keys())})
        return data


def _snapshot_conditions(family_id: int) -> dict:
    """只读快照：当前 overview 的有效条件值（无副作用、不碰判断状态）。"""
    return build_validity_conditions(build_overview(db.dump_family(family_id)))


def _diff_snapshots(before: dict, after: dict) -> list[dict]:
    """对比前后快照，返回变化清单 [{key, before, after}]（只读，不标记 stale）。

    评测脚本专用：记录每个外部变更「单独」触发了哪些维度变化，供报告诊断确定性
    失效检测。绝不调用 detect_invalidation（它有 invalidate_judgment 副作用）——
    否则会抢先把判断标 stale，导致 converse 里失效原因注入拿不到具体维度。
    """
    changed = []
    for k, before_val in before.items():
        after_val = after.get(k)
        if after_val is not None and after_val != before_val:
            changed.append({"key": k, "before": before_val, "after": after_val})
    return changed


def run_observation(script: dict, user: dict, llm, dry_run: bool = False) -> list[dict]:
    """跑单个观察点的一段多轮对话，返回每轮结果（含 resp + 铁律 + 失效检测）。

    dry_run（NullProvider）走确定性回退，finding 数字是引擎合法产出、非 LLM 编造，
    与真实 advisor 路径（assemble 会 strip LLM 数字）语义不同——故 dry_run 跳过铁律断言。
    """
    turns: list[dict] = []
    capture = bool(script.get("capture_invalidation"))
    tracer = llm if isinstance(llm, TracingProvider) else None
    for turn_def in script["turns"]:
        # 变更前的最新判断（观察点4 的「第一轮 judgment」）
        judgment_before = db.latest_judgment(user["family_id"]) if capture else None
        # 逐个执行外部状态变更，每次变更后确定性失效检测。
        # 元素支持 callable 或 {"fn", "label", "expect_stale"}（观察点4 的 4A/4B）。
        invalidation_steps: list[dict] = []
        for item in (turn_def.get("pre_change") or []):
            if callable(item):
                fn, label, expect = item, None, None
            else:
                fn, label, expect = item["fn"], item.get("label"), item.get("expect_stale")
            # 只读快照记录（无副作用）：变更前/后各取一次 validity_conditions，
            # diff 出「本变更单独触发」的维度变化。绝不调 detect_invalidation——
            # 它有 invalidate_judgment 副作用，会抢先把判断标 stale，导致 converse
            # 里失效原因注入拿不到具体维度。
            if capture:
                before = _snapshot_conditions(user["family_id"])
                active_before = (db.latest_judgment(user["family_id"]) or {}).get("status") == "active"
            fn(user["family_id"])
            if capture:
                after = _snapshot_conditions(user["family_id"])
                invalidation_steps.append({
                    "change": getattr(fn, "__name__", str(fn)),
                    "label": label,
                    "expect_stale": expect,
                    "active_before": active_before,
                    "changed": _diff_snapshots(before, after),
                })
        # converse（唯一评测入口），记录本轮 chat/complete_json 原始返回
        if tracer:
            tracer.reset()
        result = converse(turn_def["message"], user, llm=llm)
        turn: dict = {
            "message": turn_def["message"],
            "result": result,
            "judgment_before": judgment_before,
            "invalidation_steps": invalidation_steps,
        }
        if tracer:
            turn["chat_log"] = list(tracer.chat_log)
            turn["complete_log"] = list(tracer.complete_log)
        if isinstance(result, AgentResponse):
            turn["resp"] = result
            if not dry_run:
                turn["iron_rules"] = run_iron_rules(result)
        else:
            turn["non_agent"] = type(result).__name__  # 意外建档抽取
        turns.append(turn)
    return turns


def _dim_label(script: dict) -> str:
    dims = script.get("dimensions") or []
    return " ".join(dims)


def render_report(results: list[dict], family_id: int, dry_run: bool) -> str:
    """把结果渲染成 markdown 报告。"""
    lines: list[str] = []
    lines.append("# AI 顾问实战验收报告（真实 DeepSeek）")
    lines.append("")
    lines.append(f"- 家庭 fixture：family_id={family_id}（典型中国家庭，6 观察点共享）")
    lines.append(f"- 模式：{'dry-run（NullProvider，结构自检）' if dry_run else '真实 DeepSeek'}")
    lines.append("")
    lines.append("> 铁律类（数字无编造/source/status/无内部标识）由程序判定；")
    lines.append("> 顾问感（1-3 分）由独立 LLM 裁判判定，附原文证据。")
    lines.append("")

    # 总览
    total_iron_pass = 0
    total_iron_rule = 0
    judge_scores: list[float] = []
    for r in results:
        for turn in r["turns"]:
            if "iron_rules" in turn:
                for rule, violations in turn["iron_rules"].items():
                    total_iron_rule += 1
                    if not violations:
                        total_iron_pass += 1
        if r.get("judge") and isinstance(r["judge"].get("overall"), (int, float)):
            judge_scores.append(float(r["judge"]["overall"]))
    lines.append("## 总览")
    lines.append("")
    lines.append(f"- 铁律断言：{total_iron_pass}/{total_iron_rule} 通过")
    if judge_scores:
        lines.append(f"- 顾问感均分：{sum(judge_scores) / len(judge_scores):.2f}/3（{len(judge_scores)} 个观察点）")
    lines.append("")

    for r in results:
        script = r["script"]
        lines.append(f"## {script['title']}")
        lines.append("")
        lines.append(f"判分分项：`{_dim_label(script)}`")
        lines.append("")

        # 对话
        lines.append("### 对话原文（结构化）")
        lines.append("")
        for i, turn in enumerate(r["turns"], 1):
            lines.append(f"**第{i}轮 用户**：{turn['message']}")
            if "resp" in turn:
                lines.append(f"**第{i}轮 AI**：")
                lines.append("")
                lines.append("```")
                lines.append(resp_to_text(turn["resp"]))
                lines.append("```")
            elif "non_agent" in turn:
                lines.append(f"**第{i}轮**：⚠️ 意外触发建档抽取，返回 `{turn['non_agent']}`（剧本措辞命中 RuleExtractor）")
            # JSON 稳定性观测（真实模式才有 chat_log/complete_log）
            if "chat_log" in turn:
                lines.append("**JSON 稳定性观测**：")
                for ci, c in enumerate(turn["chat_log"], 1):
                    if c is None:
                        lines.append(f"  - chat#{ci}: FAIL(None)")
                    else:
                        tcs = c["tool_calls"] or ["<无 tool_calls，直接回答>"]
                        lines.append(f"  - chat#{ci}: tool_calls={tcs}")
                for ci, cp in enumerate(turn["complete_log"], 1):
                    if cp is None:
                        lines.append(f"  - complete_json#{ci}: FAIL(None)")
                    else:
                        tag = ("route" if "intent" in cp["keys"]
                               else "structure" if "summary" in cp["keys"] else "?")
                        lines.append(f"  - complete_json#{ci}[{tag}]: keys={cp['keys']}")
            # 观察点4 的失效检测记录
            if turn.get("judgment_before"):
                j = turn["judgment_before"]
                lines.append(f"**变更前判断**：主要矛盾 = {[p.get('title') for p in (j.get('priorities') or [])]}")
                lines.append(f"  validity_conditions = {j.get('validity_conditions')}")
            for step in turn.get("invalidation_steps") or []:
                changed = step["changed"]
                label = step.get("label") or step["change"]
                stale_txt = f"stale（{changed}）" if changed else "未失效"
                expect = step.get("expect_stale")
                if not step.get("active_before", True) and not changed:
                    verdict = "（前序变化已触发失效，本条无 active 判断可检测）"
                elif expect is True and changed:
                    verdict = " ✅ 确定性 invalidation 链路正常"
                elif expect is True and not changed:
                    verdict = " ⚠️ 预期应失效但未失效（判定：失效检测链路异常）"
                elif expect is False and not changed:
                    verdict = " ⚠️ 未失效（判定：validity_conditions 覆盖不足，该事实不在有效条件内）"
                else:
                    verdict = "（意外失效，需查）"
                lines.append(f"**外部变更 `{label}` → detect_invalidation**：{stale_txt}{verdict}")
            lines.append("")

        # 铁律断言
        lines.append("### 铁律断言（程序判定）")
        lines.append("")
        if dry_run:
            lines.append("（dry-run 跳过铁律断言：确定性回退路径 finding 数字为引擎合法产出，与真实 advisor 路径语义不同）")
            lines.append("")
        else:
            lines.append("| 轮次 | 规则 | 结果 |")
            lines.append("|------|------|------|")
            for i, turn in enumerate(r["turns"], 1):
                if "iron_rules" not in turn:
                    continue
                for rule, violations in turn["iron_rules"].items():
                    mark = "✅" if not violations else "❌ " + "；".join(violations)
                    lines.append(f"| {i} | {rule} | {mark} |")
            lines.append("")

        # 顾问感裁判
        judge = r.get("judge")
        if judge:
            lines.append("### 顾问感裁判（独立 LLM）")
            lines.append("")
            lines.append(f"**总分**：{judge.get('overall')} / 3")
            lines.append("")
            lines.append(f"**理由**：{judge.get('reason', '')}")
            lines.append("")
            dims = judge.get("dimensions") or {}
            if dims:
                lines.append("| 分项 | 分 | 理由 |")
                lines.append("|------|----|------|")
                for dname, dval in dims.items():
                    lines.append(f"| {dname} | {dval.get('score')} | {dval.get('reason', '')} |")
                lines.append("")
            ev = judge.get("evidence") or []
            if ev:
                lines.append("**原文证据**：")
                lines.append("")
                for e in ev:
                    lines.append(f"- [{e.get('speaker')}] {e.get('quote')}")
                lines.append("")
        else:
            lines.append("### 顾问感裁判")
            lines.append("")
            lines.append("（dry-run 跳过，或裁判调用失败）")
            lines.append("")

    # 硬伤清单
    lines.append("## 硬伤清单")
    lines.append("")
    found = False
    for r in results:
        for i, turn in enumerate(r["turns"], 1):
            if "iron_rules" in turn:
                for rule, violations in turn["iron_rules"].items():
                    for v in violations:
                        lines.append(f"- [铁律] {r['script']['title']} 第{i}轮 · {rule}：{v}")
                        found = True
            if "non_agent" in turn:
                lines.append(f"- [脚本] {r['script']['title']} 第{i}轮：意外触发建档抽取（`{turn['non_agent']}`），需改剧本措辞")
                found = True
        if r.get("judge"):
            ov = r["judge"].get("overall")
            if isinstance(ov, (int, float)) and ov < 2.0:
                lines.append(f"- [顾问感] {r['script']['title']}：总分 {ov}/3 偏低，见裁判理由")
                found = True
    if not found:
        lines.append("（未发现硬伤）")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    dry_run = "--dry-run" in argv
    load_dotenv()

    # 独立临时 DB，绝不污染 data.db
    tmp = tempfile.mkdtemp(prefix="advisor_eval_")
    db.DB_PATH = os.path.join(tmp, "eval.db")
    db.init_db()
    fid = build_family()
    user = {"family_id": fid, "tier": "vip"}

    llm = None if dry_run else TracingProvider(get_provider())
    # 独立 judge provider：不经 TracingProvider，与被测对话隔离，避免自评
    judge_llm = None if dry_run else get_provider()

    # 跑所有观察点（共享 family_id，连续对话）
    results: list[dict] = []
    all_turns: list[dict] = []
    for script in SCRIPTS:
        turns = run_observation(script, user, llm, dry_run=dry_run)
        results.append({"script": script, "turns": turns})
        # 观察点6 无独立剧本，用前五个观察点的整段对话做整体评估
        if script["id"] != "obs6_overall_advisor_feel":
            all_turns.extend(turns)
        if script["id"] == "obs6_overall_advisor_feel":
            results[-1]["turns"] = all_turns  # 复用整段对话

    # 顾问感裁判（dry-run 跳过）
    if not dry_run:
        for r in results:
            script = r["script"]
            turns = r["turns"]
            # 观察点6 用整段对话，其余用各自轮次
            transcript = build_transcript(turns)
            r["judge"] = judge_advisor_feel(script, transcript, llm=judge_llm)
            print(f"[judge] {script['id']} -> "
                  f"{r['judge'].get('overall') if r['judge'] else 'FAIL'}")

    # 渲染并写报告
    report = render_report(results, fid, dry_run)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\n报告已写入：{REPORT_PATH}")
    print(f"临时 DB：{tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
