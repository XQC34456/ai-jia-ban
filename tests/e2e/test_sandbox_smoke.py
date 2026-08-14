"""C3 沙盘 headless 冒烟：真实 DOM 渲染 + 决策叙事卡 + 0 console/pageerror。

覆盖计划 §8 验收 ⑤⑥：
  ⑤ 建档 → 跑 compare → 断言 9 行指标渲染 + 叙事卡渲染 + position 徽标存在
  ⑥ 收集 console error / pageerror，断言 0 error

前置：`python -m playwright install chromium`（浏览器二进制 ~150MB，一次性）。
隔离：AIJIABAN_DB 指向临时 SQLite + 独立 uvicorn 子进程，绝不污染 data.db。
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """启动独立 uvicorn（临时 DB），返回 base_url。"""
    db_path = tmp_path_factory.mktemp("e2e") / "test.db"
    port = _free_port()
    env = dict(
        os.environ,
        AIJIABAN_DB=str(db_path),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(base + "/api/health", timeout=1).status_code == 200:
                    break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("uvicorn 启动超时")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _seed(base: str) -> str:
    """通过 API 注册 → 升级 VIP → 建档，返回 token。"""
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/register", json={"username": "smoketest", "password": "secret123"})
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        h = {"Authorization": "Bearer " + token}
        assert c.post("/api/upgrade", headers=h).status_code == 200

        entities = [
            ("person", {"name": "本人", "relation": "本人", "birth_year": 1988}),
            ("cashflow", {"flow_type": "income", "category": "工资", "amount": 30000, "period": "月"}),
            ("cashflow", {"flow_type": "expense", "category": "日常", "amount": 28000, "period": "月"}),
            ("asset", {"type": "房产", "name": "自住房", "value": 3000000}),
            ("asset", {"type": "存款", "name": "活期", "value": 2000000}),
        ]
        for table, payload in entities:
            rr = c.post(f"/api/family/entity/{table}", headers=h, json=payload)
            assert rr.status_code == 200, f"{table} 建档失败: {rr.text}"
        return token


def test_sandbox_smoke(server):
    from playwright.sync_api import sync_playwright

    token = _seed(server)
    errors: list[str] = []

    ARTIFACTS.mkdir(exist_ok=True)
    shot = ARTIFACTS / "c3_sandbox_smoke.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        # 注入 token 跳过登录门 → 直达沙盘（init_script 在每次页面脚本加载前写入 localStorage）
        page.add_init_script(f"localStorage.setItem('token', {json.dumps(token)})")
        page.goto(server + "/#/sandbox")
        page.wait_for_selector(".actions .btn-primary", timeout=10000)

        # 加两个方案 → A/B/C 三个，覆盖多方案渲染
        page.click("button.add-opt")
        page.click("button.add-opt")
        page.click(".actions .btn-primary")

        # 等待叙事卡渲染（后端 apply→build_overview→compare 完成后）
        page.wait_for_selector(".interp-card", timeout=15000)

        # ⑤ 9 行指标 + 叙事卡 + 定位徽标
        metric_rows = page.locator(".cmp-table tbody tr").count()
        interp_cards = page.locator(".interp-card").count()
        badges = page.locator(".pos-badge").count()

        assert metric_rows == 9, f"应渲染 9 行指标，实际 {metric_rows}"
        assert interp_cards == 3, f"应有 3 张叙事卡，实际 {interp_cards}"
        assert badges == 3, f"应有 3 个定位徽标，实际 {badges}"

        # 「关键变化」chip（已算好的 changes 渲染，回答「变了什么」）
        change_chips = page.locator(".change-chip").count()
        assert change_chips > 0, "应有「关键变化」chip 渲染"

        # 顾问感：不出现强制排名结论（「最佳方案」「最优」），允许「没有绝对更优」这类反排名表述
        body_text = page.inner_text(".result")
        assert "最佳方案" not in body_text and "最优" not in body_text, "沙盘不应出现强制排名结论"

        page.screenshot(path=str(shot))
        browser.close()

    # ⑥ 0 console error / pageerror
    assert errors == [], f"浏览器 0 error 未满足: {errors}"

    assert shot.exists(), "截图未生成"
