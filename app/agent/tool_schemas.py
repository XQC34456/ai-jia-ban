"""V2.2 Tool Schema 注册表：9 个只读工具的 OpenAI schema + execute_tool 执行器。

铁律：
- 工具 = AI 顾问的眼睛和手；只读 Engine/Decision（data_origin="real"）或沙盘
  （data_origin="scenario"），绝不写库（create_action 留 V2.6）。
- execute_tool 只调 A2 工具 / db / service，绝不自行计算财富数字。
- 工具结果带 data_origin，供 LLM 与 metrics 取数区分「现状」与「模拟」。
- scenario 工具受 VIP 门，复用 A2 契约（resolve_scenario_name + SCENARIO_PARAM_MODELS）。
"""
from __future__ import annotations

from pydantic import ValidationError

from .. import db
from ..schemas.scenario import SCENARIO_PARAM_MODELS
from ..services.scenario import compare_scenarios
from .tools import ToolError, get_goals, get_issues, get_overview, resolve_scenario_name

__all__ = ["TOOL_SCHEMAS", "execute_tool"]


# ---------- 9 工具 OpenAI function schema ----------

def _fn(name: str, desc: str, properties: dict | None = None,
        required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


TOOL_SCHEMAS = [
    _fn("get_family_profile",
        "读取家庭全貌：成员、资产、负债、保险、现金流、目标。需要了解「这个家庭是谁」时调用。"),
    _fn("get_wealth_overview",
        "读取财富全景基线：财富评分、净资产、现金流、负债率 DTI、应急月数。需要现状基线时调用。"),
    _fn("get_wealth_issues",
        "读取财富问题清单（P0→P2）：风险点 + 建议。需要判断风险时调用。"),
    _fn("get_cashflow",
        "读取现金流：月收入、月支出、结余、储蓄率。用户问现金流/收支/压力时调用。"),
    _fn("get_allocation",
        "读取资产配置：各类资产占比、房产占比、适配度。用户问配置/集中度/持仓时调用。"),
    _fn("get_retirement",
        "读取养老测算：RFR、NWC。用户问退休/养老时调用。"),
    _fn("get_goals",
        "读取家庭目标与进度：目标缺口、每月需存。用户问目标/教育金/攒钱时调用。"),
    _fn("run_scenario",
        "单方案情景模拟：给定场景名与参数，返回模拟后各指标与 baseline 的对比。"
        "用户问「如果…会怎样」且只有一个方案时调用。",
        properties={
            "name": {"type": "string",
                     "description": "场景名：买房/提前还贷/投资/收入下降（中文或英文 frozen name）"},
            "params": {"type": "object",
                       "description": "场景参数。买房 price/down_payment_ratio/loan_rate/loan_years；"
                                     "提前还贷 prepay_amount/method；投资 amount/to_class；"
                                     "收入下降 pct_change（如 -0.3）"},
        },
        required=["name", "params"]),
    _fn("compare_scenarios",
        "同一场景多参数组对比：一次模拟多个方案并对比各指标 delta。"
        "用户在同一决策下比较多个参数（如买 500 万 vs 400 万）时调用。",
        properties={
            "name": {"type": "string", "description": "场景名"},
            "options": {"type": "array",
                        "description": "多个参数组，每个含 params",
                        "items": {"type": "object",
                                  "properties": {"name": {"type": "string"},
                                                 "params": {"type": "object"}}}},
        },
        required=["name", "options"]),
]


# ---------- execute_tool ----------

def _run_scenarios(user: dict, name: str, params_list: list[dict]) -> dict:
    """多方案执行器：复用 A2 契约（VIP 门 + resolve + Pydantic 校验），一次 compare_scenarios。

    id 依序 A/B/C…；params_list 为空时至少跑一个默认参数方案（防御）。
    """
    if user.get("tier") != "vip":
        raise ToolError("forbidden", {"feature": "情景模拟"})
    resolved = resolve_scenario_name(name)
    model = SCENARIO_PARAM_MODELS[resolved]
    options = []
    for i, params in enumerate(params_list or [{}]):
        try:
            validated = model(**params).model_dump()
        except ValidationError as e:
            errs = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
                    for err in e.errors()]
            raise ToolError("invalid_params", {"errors": errs})
        options.append({"id": chr(ord("A") + i), "params": validated})
    data = db.dump_family(user["family_id"])
    try:
        return compare_scenarios(data, resolved, options)
    except ValueError as e:
        raise ToolError("unexecutable", {"message": str(e)})


def execute_tool(name: str, args: dict, user: dict) -> dict:
    """执行一个只读工具，返回带 data_origin 的结构化结果。

    real 工具返回 {"data_origin": "real", <字段>...}；
    scenario 工具返回 {"data_origin": "scenario", **compare_result}。
    """
    if name == "get_family_profile":
        return {"data_origin": "real", "family": db.dump_family(user["family_id"])}
    if name == "get_wealth_overview":
        return {"data_origin": "real", "overview": get_overview(user)}
    if name == "get_wealth_issues":
        return {"data_origin": "real", **get_issues(user)}
    if name == "get_cashflow":
        return {"data_origin": "real",
                "cashflow": (get_overview(user) or {}).get("cashflow") or {}}
    if name == "get_allocation":
        return {"data_origin": "real",
                "asset_allocation": (get_overview(user) or {}).get("asset_allocation") or {}}
    if name == "get_retirement":
        return {"data_origin": "real",
                "retirement": (get_overview(user) or {}).get("retirement") or {}}
    if name == "get_goals":
        return {"data_origin": "real", **get_goals(user)}
    if name == "run_scenario":
        return {"data_origin": "scenario",
                **_run_scenarios(user, args.get("name", ""), [args.get("params") or {}])}
    if name == "compare_scenarios":
        options = args.get("options") or []
        params_list = [o.get("params") or {} for o in options]
        return {"data_origin": "scenario",
                **_run_scenarios(user, args.get("name", ""), params_list)}
    raise ToolError("unexecutable", {"message": f"未知工具 {name}"})
