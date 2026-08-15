"""FastAPI 服务：AI家办 MVP 后端。

启动：python -m app.main  或  uvicorn app.main:app --reload
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, decision, report
from .api import agent, event, goal, onboarding, scenario, wealth
from .agent.entry import cancel_and_reanswer
from .agent.profile import apply_confirmation
from .agent.providers import get_provider


def _load_dotenv() -> None:
    """加载项目根目录的 .env（如果存在），用于配置 LLM_API_KEY 等。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

app = FastAPI(title="AI家办 · 家庭财富智管家", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wealth.router)
app.include_router(event.router)
app.include_router(onboarding.router)
app.include_router(scenario.router)
app.include_router(goal.router)
app.include_router(agent.router)


class AuthIn(BaseModel):
    username: str
    password: str


class ConfirmIn(BaseModel):
    pending_id: str
    confirmed: bool


class DecisionIn(BaseModel):
    scenario: str
    params: dict


_ENTITY_TABLES = set(db.ENTITY_COLS)


def _ensure_table(table: str) -> None:
    if table not in _ENTITY_TABLES:
        raise HTTPException(400, f"未知实体类型: {table}")


# ---------- 鉴权 ----------
from .api.deps import get_current_user, require_vip as _require_vip  # noqa: E402


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/api/health")
def api_health():
    return {"ok": True, "llm": bool(os.environ.get("LLM_API_KEY"))}


# ---------- 账号 ----------

def _issue_token(user: dict) -> dict:
    token = secrets.token_hex(32)
    db.set_token(user["id"], token)
    return {"token": token, "username": user["username"], "tier": user["tier"]}


@app.post("/api/register")
def register(body: AuthIn):
    username = body.username.strip()
    if not username or not body.password:
        raise HTTPException(400, "用户名和密码不能为空")
    if len(body.password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    if db.get_user_by_username(username):
        raise HTTPException(409, "用户名已被占用")
    user = db.create_user(username, body.password)
    return _issue_token(user)


@app.post("/api/login")
def login(body: AuthIn):
    user = db.verify_user(body.username.strip(), body.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误")
    return _issue_token(user)


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return {"username": user["username"], "tier": user["tier"]}


@app.post("/api/upgrade")
def upgrade(user: dict = Depends(get_current_user)):
    """模拟开通 VIP（无支付）。TODO: 接入真实支付后替换此路由。"""
    db.set_tier(user["id"], "vip")
    db.record_event(user["family_id"], "upgrade")
    return {"tier": "vip"}


@app.delete("/api/account")
def delete_account(user: dict = Depends(get_current_user)):
    """删除当前账号及其家庭全部数据（个保法删除权，内测三件套之一）。"""
    db.delete_user(user["id"])
    return {"ok": True, "deleted": True}


# ---------- 家庭档案（数据随登录用户隔离） ----------

@app.get("/api/family")
def get_family(user: dict = Depends(get_current_user)):
    data = db.dump_family(user["family_id"])
    from . import calc_engine as ce
    return {
        "data": data,
        "snapshot": ce.snapshot(data),
        "problems": decision.build_problems(data),
    }


@app.post("/api/confirm")
def confirm_endpoint(body: ConfirmIn, user: dict = Depends(get_current_user)):
    """建档确认落地：已迁移到 Agent 吸收层 profile.apply_confirmation（落地前不写库）。

    Step 4（G3 闭环）：确认 → 写库；取消 → **拒绝本次建档 ≠ 拒绝回答**——
    cancel_and_reanswer 用原问题（original_query）重新投入 Advisor 回答路径，
    返回正常回答（AgentResponse），不再只是「好的，已忽略」。
    """
    if body.confirmed:
        return apply_confirmation(user["family_id"], body.pending_id, True).model_dump()
    resp = cancel_and_reanswer(user, body.pending_id, llm=get_provider())
    return resp.model_dump()


@app.get("/api/report")
def get_report(user: dict = Depends(get_current_user)):
    _require_vip(user, "report")
    return report.build_report(user["family_id"])


@app.post("/api/decision")
def decision_endpoint(body: DecisionIn, user: dict = Depends(get_current_user)):
    _require_vip(user, "decision")
    return decision.simulate(user["family_id"], body.scenario, body.params)


# ---------- 看板直接编辑 ----------

def _ensure_owner(table: str, entity_id: int, user: dict) -> None:
    """校验实体属于当前登录用户的家庭（数据隔离）。"""
    owner = db.get_entity_owner(table, entity_id)
    if owner is None:
        raise HTTPException(404, "记录不存在")
    if owner != user["family_id"]:
        raise HTTPException(403, "无权操作该记录")


@app.post("/api/family/entity/{table}")
def create_entity(table: str, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    _ensure_table(table)
    return {"id": db.create_entity(table, user["family_id"], payload)}


@app.put("/api/entity/{table}/{entity_id}")
def update_entity(table: str, entity_id: int, payload: dict = Body(...), user: dict = Depends(get_current_user)):
    _ensure_table(table)
    _ensure_owner(table, entity_id, user)
    db.update_entity(table, entity_id, payload)
    return {"ok": True}


@app.delete("/api/entity/{table}/{entity_id}")
def delete_entity(table: str, entity_id: int, user: dict = Depends(get_current_user)):
    _ensure_table(table)
    _ensure_owner(table, entity_id, user)
    db.delete_entity(table, entity_id)
    return {"ok": True}


# 前端静态资源
_STATIC = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(str(_STATIC / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
