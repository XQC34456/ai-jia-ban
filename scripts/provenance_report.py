# -*- coding: utf-8 -*-
"""来源追踪观察工具（Phase 2 第三刀）：只读，不做任何写操作、不参与财富计算。

用法：python scripts/provenance_report.py [family_id]
数据源：data.db（可用环境变量 AIJIABAN_DB 覆盖），直接读 product_event 表。

输出：每个家庭 filing_provenance 事件的来源链——每条档案事实是
  new（用户新声明）/ exists（既有复用）/ conflict_overwrite（覆盖更新，
  带 matched_id=被改行 + prev_value=改前值）/ conflict_ambiguous（多匹配歧义）。

刻意最小化：只做观察工具，不做 dashboard / 历史时间线 / UI。
"""
import io
import json
import os
import sqlite3
import sys

# Windows 控制台默认非 UTF-8 → 强制 UTF-8 输出，避免中文乱码。
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB_PATH = os.environ.get("AIJIABAN_DB", os.path.join(os.path.dirname(__file__), "..", "data.db"))

_STATUS_LABEL = {
    "new": "新声明",
    "exists": "既有复用",
    "conflict_overwrite": "覆盖更新",
    "conflict_ambiguous": "多匹配歧义(未改)",
}


def _load(family_id: int | None):
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在：{DB_PATH}")
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM product_event WHERE event_type = 'filing_provenance'"
    params: tuple = ()
    if family_id is not None:
        sql += " AND family_id = ?"
        params = (family_id,)
    sql += " ORDER BY family_id, id"
    events = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    for e in events:
        e["meta"] = json.loads(e["meta"]) if e["meta"] else {}
    return events


def main():
    fid = None
    if len(sys.argv) > 1:
        try:
            fid = int(sys.argv[1])
        except ValueError:
            print(f"用法：python scripts/provenance_report.py [family_id]")
            return
    events = _load(fid)
    if events is None:
        return
    if not events:
        print("暂无来源追踪事件（filing_provenance）。")
        return

    families = sorted({e["family_id"] for e in events if e["family_id"] is not None})
    print("=" * 64)
    print("来源追踪：档案事实从哪来")
    print("-" * 64)
    for f in families:
        print(f"\n■ 家庭 {f}")
        for e in events:
            if e["family_id"] != f:
                continue
            m = e["meta"]
            status = m.get("status")
            label = _STATUS_LABEL.get(status, status or "?")
            line = f"  {label:<12} {m.get('summary', '')}"
            if m.get("matched_id") is not None:
                line += f"  → 改档案行 id={m['matched_id']}"
            if m.get("prev_value"):
                line += f"（原 {m['prev_value']}）"
            print(line)
    print("=" * 64)


if __name__ == "__main__":
    main()
