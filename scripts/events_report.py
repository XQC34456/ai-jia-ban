"""内测观察期：产品事件本地报表（只读，不做任何写操作、不参与财富计算）。

用法：python scripts/events_report.py
数据源：data.db（可用环境变量 AIJIABAN_DB 覆盖），直接读 product_event 表。

输出三块：
  1. 各事件计数 + intent_asked 的最终路由 intent 分布
  2. 漏斗：进入 → 提问 → 获得判断 → 触发VIP → 升级 → 采纳 → 完成 → 回访
  3. 每个家庭「最后停在哪」（按时间最后一条事件）
"""
import io
import json
import os
import sqlite3
import sys

# Windows 控制台默认非 UTF-8 → 强制 UTF-8 输出，避免中文乱码。
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB_PATH = os.environ.get("AIJIABAN_DB", os.path.join(os.path.dirname(__file__), "..", "data.db"))

# 提问 = 发起了七意图之一（建档 filing 不算「提问」，单独列）
_FILING_INTENT = "filing"


def _load_events():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在：{DB_PATH}")
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM product_event ORDER BY id ASC").fetchall()
    conn.close()
    events = [dict(r) for r in rows]
    for e in events:
        e["meta"] = json.loads(e["meta"]) if e["meta"] else {}
    return events


def main():
    events = _load_events()
    if events is None:
        return
    if not events:
        print("暂无产品事件。")
        return

    families = sorted({e["family_id"] for e in events})
    families = [f for f in families if f is not None]

    # —— 1. 事件计数 ——
    from collections import Counter
    type_count = Counter(e["event_type"] for e in events)
    intent_count = Counter(
        e["intent"] for e in events
        if e["event_type"] == "intent_asked" and e["intent"]
    )

    print("=" * 64)
    print("① 各事件计数")
    print("-" * 64)
    for t in sorted(type_count):
        print(f"  {t:<18} {type_count[t]}")

    print()
    print("② intent_asked 的最终路由 intent 分布（建档 filing 单独列）")
    print("-" * 64)
    for i in sorted(intent_count):
        print(f"  {i:<18} {intent_count[i]}")

    # —— 2. 漏斗（按去重家庭计数）——
    def fam_hit(pred):
        return sum(1 for f in families if any(pred(e) for e in events if e["family_id"] == f))

    def ask_ok(e):
        return (e["event_type"] == "intent_asked"
                and e["intent"] != _FILING_INTENT
                and (e.get("meta") or {}).get("status") == "ok")

    def asked(e):
        return e["event_type"] == "intent_asked" and e["intent"] != _FILING_INTENT

    stage = [
        ("进入(entry)",          lambda e: e["event_type"] == "entry"),
        ("提问(intent≠filing)",   asked),
        ("获得判断(status=ok)",   ask_ok),
        ("触发VIP边界",           lambda e: e["event_type"] == "vip_boundary_hit"),
        ("升级",                  lambda e: e["event_type"] == "upgrade"),
        ("采纳",                  lambda e: e["event_type"] == "adopt"),
        ("完成计划",              lambda e: e["event_type"] == "action_complete"),
    ]
    print()
    print("③ 漏斗（去重家庭数，家庭总数 %d）" % len(families))
    print("-" * 64)
    for label, pred in stage:
        print(f"  {label:<22} {fam_hit(pred)}")
    # 回访 = 至少 2 次 entry
    ret = sum(1 for f in families
              if sum(1 for e in events if e["family_id"] == f and e["event_type"] == "entry") >= 2)
    print(f"  {'回访(entry≥2次)':<20} {ret}")

    # —— 3. 每家最后停在哪 ——
    print()
    print("④ 每个家庭「最后停在哪」")
    print("-" * 64)
    for f in families:
        fev = [e for e in events if e["family_id"] == f]
        last = fev[-1]
        intent = last.get("intent") or "-"
        extra = ""
        if last["event_type"] == "intent_asked":
            extra = f" / status={ (last.get('meta') or {}).get('status', '-') }"
        print(f"  family#{f:<4} {last['created_at']:<20} {last['event_type']:<16} intent={intent}{extra}")


if __name__ == "__main__":
    main()
