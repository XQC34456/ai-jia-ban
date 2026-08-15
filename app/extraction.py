"""对话抽取层：把自然语言转成结构化的建档动作列表。

两种实现：
1. RuleExtractor —— 内置正则规则，无需 API key，保证产品开箱即用。
2. LLMExtractor —— 通过 OpenAI 兼容接口调用 DeepSeek/豆包/通义，用 function
   calling 做抽取，需要设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。

动作 schema（与 db.apply_action 对齐）：
  {"kind": "person|income|expense|asset|liability|goal", "fields": {...},
   "summary": "人类可读的确认文案"}
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

# ---------- 金额解析 ----------

_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(万)?\s*(\d+)?")


def _amount(text: str) -> float | None:
    """解析中文口语金额：'2万'→20000, '1万5'→15000, '1.5万'→15000, '8000'→8000。"""
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    base = float(m.group(1))
    if m.group(2):  # 带"万"
        val = base * 10000
        if m.group(3):  # "1万5" 的 "5"
            extra = m.group(3)
            val += int(extra) * 1000 if len(extra) == 1 else int(extra)
        return val
    return base


# 金额子模式：裸数字 / X万 / X万Y（Y 为千位尾数）
_AMT = r"\d+(?:\.\d+)?\s*(?:万|千)?\s*\d*"


# ---------- 规则抽取 ----------

class RuleExtractor:
    """基于正则的抽取器，覆盖文档中典型说法的子集。"""

    def extract(self, text: str) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        # 1) 收入（带关键词）：'我月薪2万' / '我一个月大概2万'
        for m in re.finditer(
            rf"(我|老公|老婆|妻子|丈夫|她|他)?\s*(?:月薪|一个月|每月|工资|月入|收入)\s*"
            rf"(?:大概|差不多|约|左右)?\s*({_AMT})",
            text,
        ):
            amt = _amount(m.group(2))
            if amt is None:
                continue
            person = "本人" if (not m.group(1) or m.group(1) == "我") else m.group(1)
            actions.append({
                "kind": "income",
                "fields": {"category": "工资", "amount": amt, "period": "月",
                           "person_name": person},
                "summary": f"{person}月收入 {amt:,.0f} 元",
            })

        # 2) 收入（关系词 + 裸金额，无关键词）：'她1万5' / '老婆1万5'
        for m in re.finditer(
            rf"(老婆|妻子|太太|老公|丈夫|爱人|她|他)\s*({_AMT})",
            text,
        ):
            amt = _amount(m.group(2))
            if amt is None:
                continue
            actions.append({
                "kind": "income",
                "fields": {"category": "工资", "amount": amt, "period": "月",
                           "person_name": m.group(1)},
                "summary": f"{m.group(1)}月收入 {amt:,.0f} 元",
            })

        # 3) 负债月供：'房贷月供8000'
        for m in re.finditer(
            rf"(房贷|车贷|消费贷|信用卡)\s*(?:月供|每月还|月还)\s*({_AMT})",
            text,
        ):
            amt = _amount(m.group(2))
            if amt is None:
                continue
            actions.append({
                "kind": "liability",
                "fields": {"type": m.group(1), "name": m.group(1), "monthly_payment": amt},
                "summary": f"{m.group(1)}月供 {amt:,.0f} 元",
            })

        # 4) 现金/存款资产：'存款50万'
        for m in re.finditer(
            rf"(存款|现金|活期|货币基金)\s*({_AMT})",
            text,
        ):
            amt = _amount(m.group(2))
            if amt is None:
                continue
            actions.append({
                "kind": "asset",
                "fields": {"type": "存款", "name": "存款", "value": amt},
                "summary": f"存款 {amt:,.0f} 元",
            })

        # 5) 房产估值：'房子值300万'
        for m in re.finditer(
            rf"房(?:子|产)?\s*(?:值|价值|估值)\s*({_AMT})",
            text,
        ):
            amt = _amount(m.group(1))
            if amt is None:
                continue
            actions.append({
                "kind": "asset",
                "fields": {"type": "房产", "name": "房产", "value": amt},
                "summary": f"房产估值 {amt:,.0f} 元",
            })

        # 6) 成员年龄：'孩子今年12岁'
        for m in re.finditer(r"(孩子|儿子|女儿|小孩)\s*(?:今年|已经)?\s*(\d+)\s*岁", text):
            age = int(m.group(2))
            actions.append({
                "kind": "person",
                "fields": {"name": m.group(1), "relation": "子女",
                           "birth_year": date.today().year - age},
                "summary": f"子女（{age} 岁）",
            })

        # 7) 目标金额：'目标是100万' / '给孩子准备教育金，目标100万，2035年'
        _GOAL_TYPES = [("教育", "教育"), ("养老", "养老"), ("退休", "养老"),
                       ("买房", "买房"), ("创业", "创业")]

        def _goal_type(s: str) -> str:
            for k, v in _GOAL_TYPES:
                if k in s:
                    return v
            return "其他"

        year_match = re.search(r"(20\d{2})\s*年", text)
        target_date = f"{year_match.group(1)}-01-01" if year_match else None
        date_label = f"（{target_date[:4]}年）" if target_date else ""

        for m in re.finditer(
            rf"(?:目标|需要准备|要准备|准备)\s*(?:是|要|大概|约|需要|大约)?\s*({_AMT})",
            text,
        ):
            amt = _amount(m.group(1))
            if amt is None:
                continue
            gtype = _goal_type(text)
            actions.append({
                "kind": "goal",
                "fields": {"type": gtype, "name": f"{gtype}目标",
                           "target_amount": amt, "target_date": target_date},
                "summary": f"{gtype}目标 {amt:,.0f} 元{date_label}",
            })

        return actions


# ---------- LLM 抽取（OpenAI 兼容 / function calling） ----------

_EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_family_info",
        "description": (
            "从用户关于家庭财务的表述中抽取结构化信息用于建档。"
            "金额一律换算成「元」的数值（1万=10000，1万5=15000）。"
            "规则："
            "1) 房贷/车贷/信用卡等负债的月供，只抽成 liability.monthly_payment，"
            "不要同时抽成 expense；expense 仅用于日常消费（餐饮/教育/医疗/交通等）。"
            "2) 说收入时 person_name 用关系词（本人/配偶/子女/老人），不要因为提到某人就单独建 person；"
            "只有明确介绍家庭成员（年龄、关系、姓名）时才抽 person。"
            "3) 除 person（成员信息，如年龄/关系）外，没有明确金额的信息不要抽取。"
            "字段名：person: name/relation/birth_year/monthly_income/job；"
            "income: amount(月收入元)/person_name/category/period(月|年)；"
            "expense: amount(月支出元)/category/period；"
            "asset: value(资产当前价值元)/type/name；"
            "liability: monthly_payment(月供元)/principal(剩余本金元)/type(房贷|车贷|消费贷|信用卡)/name；"
            "goal: target_amount(目标金额元)/target_date(YYYY-MM-DD)/type(教育|养老|买房|创业)/name/current_saved。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string",
                                     "enum": ["person", "income", "expense", "asset", "liability", "goal"]},
                            "fields": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "relation": {"type": "string"},
                                    "birth_year": {"type": "number"},
                                    "monthly_income": {"type": "number"},
                                    "job": {"type": "string"},
                                    "category": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "value": {"type": "number"},
                                    "principal": {"type": "number"},
                                    "monthly_payment": {"type": "number"},
                                    "interest_rate": {"type": "number"},
                                    "remaining_months": {"type": "number"},
                                    "type": {"type": "string"},
                                    "target_amount": {"type": "number"},
                                    "target_date": {"type": "string"},
                                    "current_saved": {"type": "number"},
                                    "period": {"type": "string", "enum": ["月", "年"]},
                                    "person_name": {"type": "string"},
                                },
                            },
                        },
                        "required": ["kind", "fields"],
                    },
                }
            },
            "required": ["actions"],
        },
    },
}


def _normalize_action(action: dict[str, Any]) -> dict[str, Any] | None:
    """把 LLM 返回的动作规整到内部 schema；缺关键字段返回 None（跳过）。"""
    kind = action.get("kind")
    f = dict(action.get("fields") or {})

    def first(*keys: str) -> Any:
        for k in keys:
            v = f.get(k)
            if v not in (None, "", 0):
                return v
        return None

    if kind == "asset":
        f["value"] = first("value", "amount", "total")
    elif kind in ("income", "expense"):
        f["amount"] = first("amount", "value")
        f.setdefault("period", "月")
        f.setdefault("category", "工资" if kind == "income" else "其他")
    elif kind == "goal":
        f["target_amount"] = first("target_amount", "amount", "value")
    elif kind == "liability":
        f["monthly_payment"] = first("monthly_payment", "amount", "payment")
        f["principal"] = first("principal")
    elif kind == "person":
        if not f.get("name"):
            f["name"] = first("name", "relation") or "成员"

    action["fields"] = f

    # 关键字段缺失则丢弃该动作
    required = {"asset": "value", "income": "amount", "expense": "amount",
                "goal": "target_amount"}
    if kind in required and f.get(required[kind]) in (None, ""):
        return None
    if kind == "liability" and not (f.get("monthly_payment") or f.get("principal")):
        return None
    if kind == "person" and not f.get("name"):
        return None
    return action


class LLMExtractor:
    """通过 OpenAI 兼容接口做抽取。未配置 key 时不可用。

    ⚠️ 当前为死代码（profile.py 已改用确定性 RuleExtractor，见 docs 审计）。
    保留不删：AI Advisor V2.2 Tool Calling 将复用 LLM 结构化抽取能力。
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = os.environ.get("LLM_MODEL", "deepseek-chat")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def extract(self, text: str) -> list[dict[str, Any]]:
        import httpx

        if not self.available:
            return []
        resp = httpx.post(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": f"当前年份是 {date.today().year} 年。"},
                    {"role": "user", "content": text},
                ],
                "tools": [_EXTRACT_TOOL],
                "tool_choice": "auto",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        actions: list[dict[str, Any]] = []
        for call in calls:
            try:
                args = json.loads(call["function"]["arguments"])
            except (KeyError, json.JSONDecodeError):
                continue
            for a in args.get("actions", []):
                norm = _normalize_action(a)
                if norm is None:
                    continue
                norm["summary"] = _summarize(norm)
                actions.append(norm)
        return actions


def _summarize(action: dict[str, Any]) -> str:
    f = action["fields"]
    kind = action["kind"]

    if kind == "liability":
        label = f.get("type") or f.get("name") or "负债"
        if f.get("monthly_payment"):
            return f"{label}月供 {f['monthly_payment']:,.0f} 元"
        if f.get("principal"):
            return f"{label}本金 {f['principal']:,.0f} 元"
        return label

    if kind == "person":
        name = f.get("name") or "成员"
        if f.get("birth_year"):
            age = date.today().year - int(f["birth_year"])
            return f"{name}（{age} 岁）"
        return name

    if kind == "income":
        who = f.get("person_name") or ""
        per = "年收入" if f.get("period") == "年" else "月收入"
        return f"{who}{per} {f['amount']:,.0f} 元" if f.get("amount") is not None else f"{who}{per}"

    if kind == "expense":
        cat = f.get("category") or "其他"
        per = "年" if f.get("period") == "年" else "月"
        return f"{cat} {f['amount']:,.0f} 元/{per}" if f.get("amount") is not None else cat

    if kind == "asset":
        label = f"{f.get('type') or '资产'}{f.get('name') or ''}".strip()
        return f"{label} {f['value']:,.0f} 元" if f.get("value") is not None else label

    if kind == "goal":
        g = f.get("type") or "目标"
        return f"{g} {f['target_amount']:,.0f} 元" if f.get("target_amount") is not None else g

    return kind


def extract_with_llm(message: str, llm) -> list[dict[str, Any]]:
    """用注入的 LLMProvider（chat + function-calling）做一次结构化抽取。

    返回规范化动作列表；llm 为 None / chat 返回 None / 无 tool_calls → []。
    金额全部来自用户原话转写（非计算），符合铁律。
    """
    result = llm.chat(
        [
            {"role": "system", "content": f"当前年份是 {date.today().year} 年。"},
            {"role": "user", "content": message},
        ],
        [_EXTRACT_TOOL],
    )
    if not result:
        return []
    actions: list[dict[str, Any]] = []
    for call in result.get("tool_calls") or []:
        if call.get("name") != "record_family_info":
            continue
        args = call.get("arguments") or {}
        for a in args.get("actions", []):
            norm = _normalize_action(a)
            if norm is None:
                continue
            norm["summary"] = _summarize(norm)
            actions.append(norm)
    return actions


def validate_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """确定性校验：金额必须正数/有限、period 合法、批内去重。不过则丢弃该动作。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in actions:
        norm = _normalize_action(a)
        if norm is None:
            continue
        f = norm["fields"]
        bad = False
        for k in ("amount", "value", "monthly_payment", "principal", "target_amount"):
            v = f.get(k)
            if v is not None and (not isinstance(v, (int, float)) or v != v or v <= 0):
                bad = True
        if bad:
            continue
        if f.get("period") not in (None, "月", "年"):
            f["period"] = "月"
        key = (norm["kind"], json.dumps(f, ensure_ascii=False, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def get_extractor() -> Any:
    """返回可用的抽取器：优先 LLM，否则规则。"""
    llm = LLMExtractor()
    return llm if llm.available else RuleExtractor()
