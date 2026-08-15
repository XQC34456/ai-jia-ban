"""内测观察期埋点测试：轻量产品事件层。

覆盖：
- db.record_event / list_events 往返（meta JSON 序列化）
- require_vip → vip_boundary_hit（带 scope）；upgrade → upgrade
- action-plan：adopt（去重命中不重复埋）/ action_complete（仅 done）
- converse：intent_asked 记「最终路由后」intent（建档路径记 filing）+ stale_detected
- build_review_status：stale_detected（驾驶舱横幅路径）
- /api/event 端点白名单（entry/reassess 可，后端内部事件不可）
"""
from app import db
from app.agent.entry import converse
from app.agent.memory import build_review_status
from app.agent.provider import NullProvider


def _token(auth_headers: dict) -> str:
    return auth_headers["Authorization"].split(" ", 1)[1]


def _fid(auth_headers: dict) -> int:
    return db.get_user_by_token(_token(auth_headers))["family_id"]


# ---------- DB 层 ----------

def test_record_event_roundtrip(client, auth_headers):
    fid = _fid(auth_headers)
    db.record_event(fid, "entry")
    db.record_event(fid, "intent_asked", intent="CHECK_ISSUES", meta={"status": "ok"})
    evs = db.list_events(fid)
    assert [e["event_type"] for e in evs] == ["entry", "intent_asked"]
    assert evs[1]["intent"] == "CHECK_ISSUES"
    assert evs[1]["meta"] == {"status": "ok"}          # meta JSON 往返
    assert evs[0]["meta"] is None


def test_list_events_scoped_to_family(client, auth_headers):
    # 第二个用户的事件不串到第一个用户
    fid1 = _fid(auth_headers)
    client.post("/api/register", json={"username": "other", "password": "secret123"})
    db.record_event(fid1, "entry")
    # 新用户（other）尚无事件
    other = db.get_user_by_username("other")
    assert db.list_events(other["family_id"]) == []
    assert [e["event_type"] for e in db.list_events(fid1)] == ["entry"]


# ---------- VIP / upgrade ----------

def test_require_vip_records_boundary_hit(client, auth_headers):
    r = client.get("/api/report", headers=auth_headers)
    assert r.status_code == 403
    hits = [e for e in db.list_events(_fid(auth_headers))
            if e["event_type"] == "vip_boundary_hit"]
    assert len(hits) == 1
    assert hits[0]["meta"] == {"scope": "report"}


def test_upgrade_records_event(client, auth_headers):
    assert client.post("/api/upgrade", headers=auth_headers).status_code == 200
    assert any(e["event_type"] == "upgrade" for e in db.list_events(_fid(auth_headers)))


# ---------- action-plan ----------

def test_adopt_records_event_once(client, auth_headers):
    p1 = client.post("/api/wealth/action-plan", headers=auth_headers,
                     json={"issue_id": "X", "action": "A"}).json()["id"]
    assert p1 is not None
    p2 = client.post("/api/wealth/action-plan", headers=auth_headers,
                     json={"issue_id": "X", "action": "A"}).json()["id"]
    assert p2 is None                                   # 去重命中
    adopts = [e for e in db.list_events(_fid(auth_headers)) if e["event_type"] == "adopt"]
    assert len(adopts) == 1                             # 去重命中不重复埋
    assert adopts[0]["meta"]["action"] == "A"


def test_action_complete_records_only_on_done(client, auth_headers):
    pid = client.post("/api/wealth/action-plan", headers=auth_headers,
                      json={"issue_id": "X", "action": "A"}).json()["id"]
    client.put(f"/api/wealth/action-plan/{pid}", headers=auth_headers, json={"status": "todo"})
    client.put(f"/api/wealth/action-plan/{pid}", headers=auth_headers, json={"status": "done"})
    done = [e for e in db.list_events(_fid(auth_headers)) if e["event_type"] == "action_complete"]
    assert len(done) == 1                               # todo 不埋，仅 done 埋一次
    assert done[0]["meta"]["plan_id"] == pid


# ---------- converse：intent_asked（最终路由后 intent，非 LLM 首猜） ----------

def _user(auth_headers: dict) -> dict:
    return db.get_user_by_token(_token(auth_headers))


def test_converse_records_intent_asked_final_intent(client, auth_headers):
    converse("我最大的财务问题是什么", _user(auth_headers), llm=NullProvider())
    asks = [e for e in db.list_events(_fid(auth_headers)) if e["event_type"] == "intent_asked"]
    assert asks, "七意图路径必埋 intent_asked"
    assert asks[-1]["intent"] == "CHECK_ISSUES"         # 最终路由后 intent
    assert asks[-1]["meta"]["status"] == "ok"


def test_converse_filing_records_intent_filing(client, auth_headers):
    from app.schemas.agent import ConfirmCard
    r = converse("我月薪3万", _user(auth_headers), llm=NullProvider())
    assert isinstance(r, ConfirmCard)
    asks = [e for e in db.list_events(_fid(auth_headers)) if e["event_type"] == "intent_asked"]
    assert asks and asks[-1]["intent"] == "filing"


def test_converse_records_stale_detected(client, auth_headers, monkeypatch):
    from app.agent import entry
    monkeypatch.setattr(entry, "detect_invalidation",
                        lambda fid: [{"key": "cashflow_surplus", "before": 1, "after": 2}])
    converse("我最大的财务问题是什么", _user(auth_headers), llm=NullProvider())
    stale = [e for e in db.list_events(_fid(auth_headers)) if e["event_type"] == "stale_detected"]
    assert len(stale) == 1
    assert stale[0]["meta"]["count"] == 1


def test_no_stale_when_no_invalidation(client, auth_headers):
    converse("我最大的财务问题是什么", _user(auth_headers), llm=NullProvider())
    assert not any(e["event_type"] == "stale_detected" for e in db.list_events(_fid(auth_headers)))


# ---------- build_review_status：stale_detected ----------

def test_review_status_records_stale(client, auth_headers, monkeypatch):
    fid = _fid(auth_headers)
    db.save_judgment(fid, [], None, None, {"cashflow_surplus": 1})
    from app.agent import memory
    monkeypatch.setattr(memory, "detect_invalidation",
                        lambda f: [{"key": "cashflow_surplus", "before": 1, "after": 2}])
    build_review_status(fid)
    stale = [e for e in db.list_events(fid) if e["event_type"] == "stale_detected"]
    assert len(stale) == 1


# ---------- /api/event 端点白名单 ----------

def test_event_endpoint_accepts_entry_and_reassess(client, auth_headers):
    assert client.post("/api/event", headers=auth_headers,
                       json={"event_type": "entry"}).status_code == 200
    assert client.post("/api/event", headers=auth_headers,
                       json={"event_type": "reassess"}).status_code == 200
    types = [e["event_type"] for e in db.list_events(_fid(auth_headers))]
    assert types == ["entry", "reassess"]


def test_event_endpoint_rejects_internal_types(client, auth_headers):
    r = client.post("/api/event", headers=auth_headers, json={"event_type": "adopt"})
    assert r.status_code == 400


def test_event_endpoint_requires_auth(client):
    assert client.post("/api/event", json={"event_type": "entry"}).status_code == 401
