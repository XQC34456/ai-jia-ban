# Phase 2 第三刀「来源追踪（filing_provenance 事件日志）」工作计划

> 状态：**待用户确认（2026-08-16）**。Phase 2 第三刀，紧接第二刀（commit 53adce9）之后。
> 用户已确认：第三刀 = **来源追踪**，粒度 = **B 事件日志**（零 schema）。
> 硬边界：只回答「这条事实从哪里来、为什么变成现在这样」，**不演化成 provenance/audit 系统**。

---

## 0. 这一刀的本质（一句话）

**`apply_confirmation` 写库后，逐条把 reconciliation 结果（new/exists/conflict）记成 `product_event` 事件——档案事实的来源从此可查：用户新声明、既有档案复用、还是覆盖更新产生（含命中哪一行）。零 schema、不碰档案表、不注入 LLM。**

## 1. 现状取证（根因）

| 事实 | 结论 |
|------|------|
| `record_event`（db.py:733）支持任意 meta JSON，`product_event` 表已建索引 | 事件日志**零 schema 变更**，机制现成 |
| 5 张档案表无 source 列；第一刀只瞬态算 status 后丢弃 | 「为什么这个数字现在是这样」目前无法回答——**真实缺口** |
| **`get_family_profile`（tool_schemas.py:116）把 `db.dump_family()`（SELECT *）全量注入 LLM** | 方案 A（行级 source 列）会改档案表 → SELECT * 带出新列 → **LLM 输入漂移** → 用户否决，选 B |
| `db.py` 无读 product_event 的公开函数（events_report.py 脚本裸 SQL） | 需新增 `get_product_events` 只读入口供测试/报表复用 |
| events_report.py 已有读侧模式（sqlite Row + json.loads(meta)） | 新脚本 provenance_report.py 复用该模式 |

## 2. 设计（方案 B：事件日志，零 schema）

### 2.1 事件定义

- **event_type**：`filing_provenance`（新增第 9 类，product_event 表复用，无 schema 变更）
- **触发点**：`apply_confirmation(family_id, pending_id, confirmed=True)` 确认分支，对每条 reconciled 动作记一条
- **meta JSON**：

| status | 含义 | meta 字段 |
|--------|------|-----------|
| `new` | 用户新声明，已插入 | `{status, kind, summary}` |
| `exists` | 既有档案复用，未写 | `{status, kind, summary}` |
| `conflict_overwrite` | 单匹配覆盖更新 | `{status, kind, summary, matched_id, prev_value}` |
| `conflict_ambiguous` | 多匹配歧义，未自动改 | `{status, kind, summary}` |

> `matched_id` = 被覆盖的档案行 id；`prev_value` = `_archive_value(kind, row)` 人类可读旧值（复用第二刀已有函数）。

### 2.2 读侧

- **New `db.get_product_events(family_id: int, event_type: str | None = None) -> list[dict]`**：只读返回该家庭事件（按 id 升序），meta 自动 json.loads。供测试断言 + 报表脚本复用。
- **New `scripts/provenance_report.py`**：仿 events_report.py，输出每家庭按事实 summary 聚合的来源链（new/exists/conflict），回答「为什么这个数字现在是这样」。

### 2.3 零泄漏保证（关键）

事件**只写 product_event 表**，档案表一行不动 → `get_family_profile` 的 `dump_family()` 返回结构逐字节不变 → **LLM 输入零漂移 → 12 题确定性基线零 diff + 真实路径零漂移**。

## 3. 代码落点

- **Modify `app/agent/profile.py`**：`apply_confirmation` 确认分支，每条动作写库后调 `db.record_event`（约 8 行，按 status 分 4 种 meta）。
- **Modify `app/db.py`**：新增 `get_product_events` 只读函数（约 8 行）。
- **New `scripts/provenance_report.py`**：只读来源报表（约 60 行，仿 events_report.py）。
- **New `tests/test_filing_provenance.py`**：来源追踪专项测试。

## 4. 测试（TDD，先红后绿）

| 用例 | 场景 | 断言 |
|------|------|------|
| P1 new 记事件 | fresh family + income 30000 → confirm | 1 条 filing_provenance，status=new，meta.summary 含 30000 |
| P2 exists 记事件 | 档案已有 收入3万 → 重复提交 | 1 条 exists，status=exists |
| P3 conflict_overwrite 记事件 | 档案 2.5 万 → 提交 3 万 → confirm | status=conflict_overwrite，meta.matched_id=命中行 id，meta.prev_value 含 "25,000" |
| P4 conflict_ambiguous 记事件 | 档案 2 笔工资 → 提交 3 万 → confirm | status=conflict_ambiguous，matched_id 不在 meta（歧义不定位） |
| P5 未确认不记事件 | create_confirm 后 cancel | 0 条 filing_provenance（确认前绝不记） |
| P6 get_product_events 过滤 | 记 2 类事件，按 event_type 过滤 | 只返回目标类型，meta 已解析为 dict |

**已有测试影响**：`apply_confirmation` 增写事件不改变返回结构（AppliedResponse 不变）；12 题确定性基线（Q10 reanswer 走 cancel → 不触发确认分支；Q10 confirm 分支会多写事件但不影响签名，签名不含事件）。全量 pytest 确认零非预期失败。

## 5. 验证（做完必须自我验证）

1. `pytest tests/test_filing_provenance.py -v` → P1–P6 绿。
2. 全量 `pytest` → 全绿（581+）。
3. 确定性 12 题基线 → **零 diff**（事件不影响任何签名字段；重跑确认基准 json 无改动）。
4. 真机真实路径：确认一条 conflict → `scripts/provenance_report.py`（或手机查 product_event）看到 filing_provenance 事件，且真实回答路径行为与第二刀收口一致（无漂移）。
5. 独立 commit（只动 profile.py + db.py + 新测试 + 新脚本 + 本计划文档）。

## 6. 不做什么（边界声明，防膨胀）

- **不做**：新增表 / 档案行级 source 列 / 完整 provenance schema / 审计历史 / 非 goal 实体版本化 / memory_fact 泛化。
- **不做**：对话式来源澄清 UI（用户问「这数字哪来的」→ 未来由 advisor 读事件回答，本刀只建数据）。
- **不碰**：Engine/Decision/铁律/前端/Advisor 主链/冻结基线；`get_family_profile` 与 `dump_family` 结构零改动。
- 不顺手修：Q2 G1 建档 gate 误判、extraction summary 措辞（「存款存款」）——均独立问题。

## 7. 风险与已知限制

| 限制 | 说明 |
|------|------|
| 历史无来源 | 只有本刀之后确认的动作有事件；存量档案行无来源（事件日志方案固有，可接受） |
| new 无 matched_id | 插入不返回 id（apply_action 返回 None）→ new 事件不带行定位，靠 summary 追踪。要行级定位属方案 A（已否决） |
| events_report.py 计数含新事件 | 新事件类型自动出现在 ①各事件计数（非破坏，只是多一类） |
