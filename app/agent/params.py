"""A3 参数提取契约：场景 alias 转译 + C3.5 校验 + 缺字段追问，绝不脑补财务数字。

铁律：
- 场景识别是确定性的（hint / 关键词），LLM 只负责从自然语言里「提取」数字参数。
- 参数必须过 C3.5 Pydantic 模型（SCENARIO_PARAM_MODELS），缺必填字段 → missing 追问，
  绝不填默认值、绝不猜数。
- PARAM_LABELS 是追问话术 + LLM prompt 的唯一字段中文名来源。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from ..schemas.scenario import SCENARIO_PARAM_MODELS
from .provider import LLMProvider
from .tools import ToolError, resolve_scenario_name

__all__ = ["PARAM_LABELS", "ParamResult", "extract_scenario_params"]

# 参数字段中文名（与 C3.5 Field(description=) 对齐，作为追问话术唯一来源）。
PARAM_LABELS = {
    "buy_house": {
        "price": "房价（元）",
        "down_payment_ratio": "首付比例（0~1）",
        "loan_rate": "贷款利率（%）",
        "loan_years": "贷款年限（年）",
    },
    "prepay": {
        "prepay_amount": "提前还款额（元）",
        "method": "方式（shorten / reduce_payment）",
    },
    "invest": {
        "amount": "投资金额（元）",
        "to_class": "投向资产大类（cash/fixed_income/equity/real_estate/alternative/other）",
    },
    "income_change": {
        "pct_change": "收入变动幅度（如 0.1 = +10%）",
    },
}

# 确定性场景关键词（→ frozen scenario name）。
_SCENARIO_KEYWORDS = (
    ("buy_house", ("买房", "购房", "买套")),
    ("prepay", ("提前还贷", "提前还款", "还贷")),
    ("invest", ("投资", "投股票", "投入", "买入", "理财")),
    ("income_change", ("收入下降", "降薪", "涨薪", "加薪", "收入变化")),
)

_SCENARIO_HINT = "场景（买房 / 提前还贷 / 投资 / 收入变化）"


@dataclass
class ParamResult:
    scenario: str | None = None    # frozen name（已转译）
    params: dict | None = None     # 已通过 C3.5 校验的参数
    missing: list[str] = field(default_factory=list)   # 缺失字段中文名
    error: str | None = None       # ToolError.kind（场景未知等）


def _required_fields(scenario: str) -> list[str]:
    """从 C3.5 模型取必填字段（is_required），单一事实来源在 schema。"""
    model = SCENARIO_PARAM_MODELS[scenario]
    return [n for n, f in model.model_fields.items() if f.is_required()]


def _detect_scenario(message: str) -> str | None:
    """确定性场景识别（无 LLM）。"""
    for name, words in _SCENARIO_KEYWORDS:
        if any(w in message for w in words):
            return name
    return None


def _extract_params(message: str, scenario: str, llm: LLMProvider) -> dict | None:
    """LLM 从自然语言提取数字参数；缺的字段不编造、直接省略。"""
    props = {}
    for fname, label in PARAM_LABELS[scenario].items():
        props[fname] = {"description": label}
    raw = llm.complete_json(
        system="从用户消息提取情景参数，只输出 JSON，缺失的字段不要编造、直接省略。",
        user=message,
        schema={"type": "object", "properties": props},
    )
    if not raw:
        return None
    return {k: v for k, v in raw.items() if v is not None and v != ""}


def extract_scenario_params(message: str, llm: LLMProvider | None,
                            scenario_hint: str | None = None) -> ParamResult:
    """从消息提取场景与参数。

    - 场景：hint > 确定性关键词（无 LLM）；都无 → missing 追问。
    - 参数：LLM 提取后过 C3.5 校验；校验失败/缺必填 → missing（绝不填默认值）。
    """
    if scenario_hint:
        try:
            frozen = resolve_scenario_name(scenario_hint)
        except ToolError as e:
            return ParamResult(error=e.kind, missing=[_SCENARIO_HINT])
    else:
        scenario = _detect_scenario(message)
        if scenario is None:
            return ParamResult(missing=[_SCENARIO_HINT])
        frozen = scenario

    params_raw = _extract_params(message, frozen, llm) if llm is not None else None

    validated = None
    if params_raw is not None:
        try:
            validated = SCENARIO_PARAM_MODELS[frozen](**params_raw).model_dump()
        except ValidationError:
            validated = None

    if validated is None:
        required = _required_fields(frozen)
        return ParamResult(scenario=frozen, missing=[PARAM_LABELS[frozen][f] for f in required])

    return ParamResult(scenario=frozen, params=validated)
