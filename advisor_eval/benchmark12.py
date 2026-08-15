"""V1.0 12 题 Advisor Benchmark：冻结当前顾问行为为可重复基线。

用法：
    python advisor_eval/benchmark12.py            # 确定性（NullProvider）基线 → 冻结 JSON
    python advisor_eval/benchmark12.py --real     # 真实 DeepSeek 基线 → 报告
    python advisor_eval/benchmark12.py --report <path>   # 自定义报告路径

评测口径（对齐 run_eval.py）：
1. converse() 唯一真实评测入口（message, user, llm, context）。
2. 每题记录 8 维：intent / 是否直接回答 / 是否澄清 / 确定性工具(metrics) /
   关键数字(value+source) / 证据路径(source) / 行动建议(next_actions) / 铁律。
3. 两态家庭：empty（未建档，测通用回答）+ filed（build_family 典型中国家庭，测个性化）。
4. 铁律程序判定（复用 rubric.run_iron_rules），不交 LLM。
5. 确定性模式把测量结果冻结进 benchmark12_baseline.json（git 跟踪），
   供 Phase 1 改造后 diff 对比——这是「先冻结、再重构、后验证」的基线。

验收判级（V1.0 §九/§十一）只做测量标注，不设硬断言：此题基线是「现在是什么」，
不是「应该是什么」。真缺口的暴露正是本步骤的目的。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db
from app.agent.entry import converse
from app.agent.profile import apply_confirmation
from app.agent.provider import NullProvider
from app.agent.providers import get_provider
from app.schemas.agent import AgentResponse, ConfirmCard

from advisor_eval.family import build_family
from advisor_eval.rubric import run_iron_rules
from advisor_eval.run_eval import TracingProvider

REPORT_PATH = Path(__file__).resolve().parent / "report_benchmark12.md"
BASELINE_PATH = Path(__file__).resolve().parent / "benchmark12_baseline.json"

__all__ = ["BENCHMARK", "run_question", "measure", "grade", "render_report", "main"]

# 12 题（V1.0 §十一）+ 1b/11b 状态对比，共 14 个测量单元。
# expect：仅标注验收方向（供评分），不参与测量本身；返回真实行为永远记录。
BENCHMARK: list[dict] = [
    # -- 通用投资判断（G1 主战场：带金额提问不应被建档吞）--
    {"id": 1, "title": "30万现金适不适合投资（未建档）",
     "messages": ["我有 30 万现金，现在适不适合投资？"],
     "family": "empty",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"], "gap": "G1 建档优先"},
     "notes": "G1 反向验收：带金额提问必须到回答路径，不得弹建档确认卡"},
    {"id": "1b", "title": "30万现金适不适合投资（已建档）",
     "messages": ["我有 30 万现金，现在适不适合投资？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"], "gap": "G1 建档优先"},
     "notes": "已建档态应复用家庭数据给个性化判断，且数字可追溯"},
    {"id": 2, "title": "30万投入股票怎么分",
     "messages": ["我想把 30 万投入股票，应该怎么分？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "配置相关，期望引擎产出 allocation/风险指标"},
    # -- 决策比较 --
    {"id": 3, "title": "提前还车贷还是拿钱投资",
     "messages": ["我该提前还车贷还是拿钱投资？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "比较类：期望 tradeoffs + 行动建议"},
    {"id": 4, "title": "收入下降20%能撑多久",
     "messages": ["如果收入下降 20%，我能撑多久？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "变化/情景类：期望现金流/应急月数数字"},
    # -- 目标 / 退休 / 现金流（需已建档）--
    {"id": 5, "title": "孩子教育金目标怎么完成",
     "messages": ["这个孩子教育金目标怎么完成？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "目标类：期望目标缺口数字 + 行动"},
    {"id": 6, "title": "退休够不够",
     "messages": ["按现在的情况，我退休够不够？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "退休类：期望 retirement metrics + 判断"},
    {"id": 7, "title": "钱越来越不够用了怎么办",
     "messages": ["我最近感觉钱越来越不够用了，怎么办？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "模糊情感+财务：不应答非所问"},
    # -- 通用知识（未建档）--
    {"id": 8, "title": "应该买什么基金",
     "messages": ["我应该买什么基金？"],
     "family": "empty",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "纯知识：无档案也应给有效通用回答，且不编造家庭数字"},
    # -- 买房决策比较 --
    {"id": 9, "title": "买房先还贷还是留现金",
     "messages": ["我想买房，应该先还贷还是留现金？"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"]},
     "notes": "决策比较：期望引擎计算 + 权衡"},
    # -- 取消建档继续回答（G3 主战场，两轮）--
    {"id": 10, "title": "取消建档后继续回答原问题",
     "messages": ["我想把 30 万投入股票，应该怎么分？",
                  "我不想建档了，你先回答我的问题"],
     "family": "empty",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"], "gap": "G3 取消建档丢问题"},
     "notes": "轮1 用「投入股票」措辞（非「投资」情景词）→ 现状弹确认卡（G1 吞问题）；"
              "弹卡后自动模拟取消（cancel 记录）；轮2 取消+追问 → 原问题必须不丢、继续回答"},
    # -- 不重复问已有信息（#4，两轮）--
    {"id": 11, "title": "已有收入是否被重复追问",
     "messages": ["帮我看看我的现金流情况", "我收入多少你不是知道吗，为什么还要问"],
     "family": "filed",
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"], "gap": "#4 数据复用"},
     "notes": "收入已在档案，轮2 不应重复要求用户提供收入"},
    # -- 跨页面上下文入口（#8 主战场，带 context）--
    {"id": 12, "title": "从目标页问顾问，首轮直接回答目标问题",
     "messages": ["这个教育金目标怎么完成？"],
     "family": "filed",
     "context": {"source": "goals", "intent_hint": "CHECK_GOALS",
                 "payload": {"goal_type": "教育", "target_amount": 1000000,
                             "current_saved": 100000, "gap": 900000},
                 "first_turn_action": "直接回答这个目标怎么完成"},
     "expect": {"returned": "AgentResponse", "status": "ok",
                "accepts": ["AgentResponse"], "gap": "#8 上下文未消费"},
     "notes": "context 已传入；当前系统是否消费它、首轮是否针对教育金目标"},
]


def empty_family() -> int:
    """未建档家庭：全新空档案，测「无档案仍给有效通用回答」。"""
    return db.create_family("未建档家庭")


def _user(fid: int, tier: str = "vip") -> dict:
    return {"family_id": fid, "tier": tier, "id": 1}


def measure(result: ConfirmCard | AgentResponse) -> dict:
    """把一轮 converse 结果压成 8 维测量签名（确定性，可 JSON 化）。"""
    if isinstance(result, ConfirmCard):
        return {"returned": "ConfirmCard",
                "pending_items": len(result.items or []),
                "message_head": (result.message or "")[:60]}
    if isinstance(result, AgentResponse):
        return {
            "returned": "AgentResponse",
            "intent": result.intent,
            "status": result.status,
            "summary_head": (result.summary or "")[:80],
            "finding_head": (result.finding or "")[:80],
            "metric_keys": sorted({m.key for m in (result.metrics or [])}),
            "key_numbers": sorted(
                {f"{m.key}={m.value}@{m.source}" for m in (result.metrics or [])
                 if m.value is not None and m.source}),
            "evidence_paths": sorted(
                {e.metric.source for e in (result.evidence or []) if e.metric.source}),
            "next_actions": (result.next_actions or [])[:4],
            "priorities": [p.title for p in (result.priorities or [])],
            "iron": {k: (not v) for k, v in run_iron_rules(result).items()},
        }
    return {"returned": type(result).__name__}


def run_question(q: dict, fid: int, llm) -> dict:
    """跑一个测量单元（单轮或多轮），返回 {turns: [...], head_turn: ...}。

    llm: NullProvider（确定性）或 TracingProvider(真实 provider)。真实模式额外
    记录每轮 chat/complete_json 的 JSON 稳定性观测。
    """
    user = _user(fid)
    turns = []
    tracer = llm if isinstance(llm, TracingProvider) else None
    for msg in q["messages"]:
        if tracer:
            tracer.reset()
        result = converse(msg, user, llm=llm, context=q.get("context"))
        t = {"message": msg, **measure(result)}
        if tracer:
            t["chat_log"] = list(tracer.chat_log)
            t["complete_log"] = list(tracer.complete_log)
        turns.append(t)
        # G3 测量：本轮弹了建档确认卡 → 自动模拟「取消」并记录取消结果。
        # 当前行为：取消只返回 discarded，原问题不保留、不重新回答（正是 G3 缺陷）。
        if isinstance(result, ConfirmCard):
            canc = apply_confirmation(user["family_id"], result.pending_id,
                                      confirmed=False)
            t["cancel"] = {"type": canc.type, "message": canc.message}
    return {"id": q["id"], "title": q["title"], "family": q["family"],
            "turns": turns}


def grade(q: dict, run: dict) -> dict:
    """对测量结果做验收判级（V1.0 §九 方向的确定性标注）。

    只判「明显违背主线」的硬伤：返回类型 / 建档吞问题 / 是否回答 / 铁律。
    细节维度（数字对不对、答得是否个性化）留真实模式报告人工看。
    """
    exp = q.get("expect") or {}
    first = run["turns"][0]
    checks: dict[str, bool] = {}
    # G1：带金额提问不得被建档吞（返回类型必须在 accepts 内）
    checks["不被建档吞"] = first["returned"] in (exp.get("accepts") or ["AgentResponse"])
    # 返回类型与状态
    if "returned" in exp:
        checks["返回类型"] = first["returned"] == exp["returned"]
    if "status" in exp:
        checks["状态ok"] = first.get("status") == exp["status"]
    # 铁律（数字无编造 / source 正确 / status 合法 / 无内部标识）
    for rule, ok in (first.get("iron") or {}).items():
        checks[f"铁律·{rule}"] = ok
    return checks


def render_report(units: list[dict], real: bool) -> str:
    lines: list[str] = []
    lines.append("# V1.0 12 题 Advisor Benchmark")
    lines.append("")
    lines.append(f"- 模式：{'真实 DeepSeek' if real else '确定性（NullProvider，可重复基线）'}")
    lines.append("- 题量：%d 个测量单元（12 题 + 1b 状态对比 + 11 双轮）" % len(units))
    lines.append("- 验收判级只标注硬伤（建档吞/未回答/铁律），细节见每轮测量")
    lines.append("")
    for u in units:
        q = next(x for x in BENCHMARK if x["id"] == u["id"])
        lines.append(f"## {u['id']} {q['title']}")
        lines.append("")
        if q.get("notes"):
            lines.append(f"> {q['notes']}")
            lines.append("")
        lines.append(f"**验收判级**：")
        lines.append("")
        g = grade(q, u)
        for name, ok in g.items():
            lines.append(f"- {'✅' if ok else '❌'} {name}")
        lines.append("")
        for i, t in enumerate(u["turns"], 1):
            lines.append(f"**第{i}轮 用户**：{t['message']}")
            if t["returned"] == "ConfirmCard":
                lines.append(f"第{i}轮：⚠️ ConfirmCard（建档确认卡，items={t['pending_items']}）")
                if t.get("cancel"):
                    c = t["cancel"]
                    lines.append(f"  → 模拟取消：{c['type']}「{c['message']}」（原问题是否保留？）")
            elif t["returned"] == "AgentResponse":
                lines.append(f"第{i}轮：intent={t['intent']} status={t['status']}")
                if t["summary_head"]:
                    lines.append(f"  回答：{t['summary_head']}")
                if t["metric_keys"]:
                    lines.append(f"  确定性工具(metrics)：{t['metric_keys']}")
                if t["key_numbers"]:
                    lines.append(f"  关键数字：{t['key_numbers']}")
                if t["evidence_paths"]:
                    lines.append(f"  证据路径：{t['evidence_paths']}")
                if t["next_actions"]:
                    lines.append(f"  行动建议：{t['next_actions']}")
                if t["iron"]:
                    fails = [k for k, v in t["iron"].items() if not v]
                    lines.append(f"  铁律：{'全部通过' if not fails else '❌ ' + '；'.join(fails)}")
                if t.get("chat_log"):
                    for i, cl in enumerate(t["chat_log"], 1):
                        if cl is None:
                            lines.append(f"  chat#{i}：失败(None)")
                        else:
                            tc = ",".join(cl["tool_calls"]) or "无工具"
                            lines.append(f"  chat#{i}：tool_calls=[{tc}] content={cl['content_head']!r}")
                if t.get("complete_log"):
                    for i, cj in enumerate(t["complete_log"], 1):
                        if cj is None:
                            lines.append(f"  complete_json#{i}：parse 失败(None)")
                        else:
                            lines.append(f"  complete_json#{i}：keys={cj['keys']}")
            else:
                lines.append(f"第{i}轮：⚠️ 返回 `{t['returned']}`")
            lines.append("")
    return "\n".join(lines)


def _load_dotenv() -> None:
    """独立脚本运行时也要拿到 LLM_API_KEY（否则 get_provider() 静默回退 NullProvider）。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def run_benchmark(llm) -> tuple[list[dict], list[dict], str]:
    """跑完整 12 题基准，返回 (units, baseline 签名, 报告文本)。

    llm: NullProvider（确定性）→ baseline 签名可重复，供 diff/测试冻结；
         TracingProvider(真实) → baseline 不冻结，只用于出报告。
    每次调用用独立临时 DB，绝不污染 data.db。
    """
    tmp = tempfile.mkdtemp(prefix="benchmark12_")
    db.DB_PATH = os.path.join(tmp, "bench.db")
    db.init_db()

    empty_fid = empty_family()
    filed_fid = build_family()

    units = []
    for q in BENCHMARK:
        fid = empty_fid if q["family"] == "empty" else filed_fid
        units.append(run_question(q, fid, llm))

    report = render_report(units, isinstance(llm, TracingProvider))

    # 基线签名（可 diff）：去掉 message 原文长度噪声，只留可断言字段。
    baseline = []
    for u in units:
        b = {"id": u["id"], "family": u["family"],
             "turns": [{"returned": t["returned"],
                        "intent": t.get("intent"),
                        "status": t.get("status"),
                        "metric_keys": t.get("metric_keys", []),
                        "key_numbers": t.get("key_numbers", []),
                        "evidence_paths": t.get("evidence_paths", []),
                        "has_next_actions": bool(t.get("next_actions")),
                        "priorities": t.get("priorities", []),
                        "iron_ok": all(t.get("iron", {}).values()),
                        "cancel_type": (t.get("cancel") or {}).get("type")}
                       for t in u["turns"]]}
        baseline.append(b)
    return units, baseline, report


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    real = "--real" in argv
    report_arg = None
    if "--report" in argv:
        report_arg = argv[argv.index("--report") + 1]
    _load_dotenv()

    # 真实模式用 TracingProvider 包裹（顺带观测每轮 chat/complete_json 稳定性）；
    # 确定性模式用 NullProvider（冻结可重复基线，零 API 成本）。
    llm = TracingProvider(get_provider()) if real else NullProvider()
    units, baseline, report = run_benchmark(llm)

    out = Path(report_arg) if report_arg else REPORT_PATH
    out.write_text(report, encoding="utf-8")

    if not real:
        BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        print(f"确定性基线已冻结：{BASELINE_PATH}")

    print(f"报告已写入：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
