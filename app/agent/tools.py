"""A2 Tool Adapter：把 4 个财富查询意图接到服务层（纯取数，零 LLM、零财富计算）。

分层铁律：Tool = 获取事实，Decision = 判断，LLM = 理解 + 解释。

本层只做：
- intent → service 映射（VIEW_OVERVIEW/CHECK_ISSUES/CHECK_GOALS/SCENARIO_COMPARE）
- 场景 alias（中文）→ frozen scenario name 转译
- C3.5 Pydantic 参数校验（类型/范围错误 → invalid_params）
- 403/400/422 结构化错误转译（kind 机器可读，本层不写自然语言话术）
- API JSON 原样透传

本层绝不：计算 Wealth Score / RFR / NWC / DTI / 占比 / 风险 / 推荐，调 LLM，改 Engine/Decision。
CHECK_RETIREMENT / CHECK_ALLOCATION 不新增工具，复用 get_overview() 后读子字段。
"""
from __future__ import annotations

from pydantic import ValidationError

from .. import db
from ..decision import build_issues
from ..schemas.agent import SCENARIO_ALIASES
from ..schemas.scenario import SCENARIO_NAMES, SCENARIO_PARAM_MODELS
from ..services import build_goals, build_overview
from ..services.scenario import compare_scenarios

__all__ = [
    "ToolError", "resolve_scenario_name",
    "get_overview", "get_issues", "get_goals", "compare_scenario",
]


class ToolError(Exception):
    """结构化工具错误。kind 是机器可读状态（A3 据此决定话术），detail 承载结构化详情。

    kind ∈ {forbidden, unknown_scenario, invalid_params, unexecutable}
    """
    def __init__(self, kind: str, detail: dict | None = None):
        self.kind = kind
        self.detail = detail or {}
        super().__init__(kind)


def resolve_scenario_name(name: str) -> str:
    """场景 alias（中文）→ frozen scenario name；已是 frozen name 则原样返回。"""
    if name in SCENARIO_NAMES:
        return name
    frozen = SCENARIO_ALIASES.get(name)
    if frozen is None:
        raise ToolError("unknown_scenario", {"name": name})
    return frozen


def get_overview(user: dict) -> dict:
    """VIEW_OVERVIEW → build_overview（只读；CHECK_RETIREMENT/CHECK_ALLOCATION 复用此工具读子字段）。"""
    data = db.dump_family(user["family_id"])
    return build_overview(data)


def get_issues(user: dict) -> dict:
    """CHECK_ISSUES → build_issues（只读）。"""
    data = db.dump_family(user["family_id"])
    return build_issues(data)


def get_goals(user: dict) -> dict:
    """CHECK_GOALS → {"goals": build_goals(...)}（与 /api/wealth/goals 同形）。"""
    data = db.dump_family(user["family_id"])
    return {"goals": build_goals(data)}


def compare_scenario(user: dict, name: str, params: dict) -> dict:
    """SCENARIO_COMPARE → compare_scenarios（编排层重算，本层绝不重算 comparison）。

    调用链：apply_scenario → build_overview → CompareResponse（全部在 service 层完成）。
    错误转译：tier != vip → forbidden；未知场景 → unknown_scenario；
    参数类型/范围非法 → invalid_params（422 等价）；业务不可执行 → unexecutable（400 等价）。
    """
    if user.get("tier") != "vip":
        raise ToolError("forbidden")
    resolved = resolve_scenario_name(name)

    model = SCENARIO_PARAM_MODELS[resolved]
    try:
        validated = model(**params).model_dump()
    except ValidationError as e:
        errs = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise ToolError("invalid_params", {"errors": errs})

    data = db.dump_family(user["family_id"])
    try:
        return compare_scenarios(data, resolved, [{"id": "A", "params": validated}])
    except ValueError as e:
        raise ToolError("unexecutable", {"message": str(e)})
