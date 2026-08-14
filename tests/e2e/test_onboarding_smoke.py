"""冷启动 Humanization headless 冒烟：新用户注册 → 3 步向导 → 60 秒反馈 → 0 error。

覆盖计划验收：
  ① 新用户登录后不是「请输入家庭资产」，而是「认识你的家庭」
  ② 粗画像 slider（很多/一般/很少/不知道）+ 60 秒反馈（画像 + 问题）
  ③ 反馈明确声明「仅演示，非真实数据」+ 3 个 CTA 优先级
  ④ 0 console error / pageerror

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
    db_path = tmp_path_factory.mktemp("e2e_onboard") / "test.db"
    port = _free_port()
    env = dict(os.environ, AIJIABAN_DB=str(db_path), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


def _register(base: str) -> str:
    """注册新用户（不建档），返回 token。"""
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/register", json={"username": "newuser", "password": "secret123"})
        assert r.status_code == 200, r.text
        return r.json()["token"]


def test_onboarding_smoke(server):
    from playwright.sync_api import sync_playwright

    token = _register(server)
    errors: list[str] = []

    ARTIFACTS.mkdir(exist_ok=True)
    shot = ARTIFACTS / "cold_start_smoke.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        page.add_init_script(f"localStorage.setItem('token', {json.dumps(token)})")
        page.goto(server + "/")
        page.wait_for_selector(".onboard-card", timeout=10000)

        # ① 第一屏是「认识你的家庭」，不是「请输入家庭资产」
        body = page.inner_text(".onboard-card")
        assert "认识一下你的家庭" in body, "第一屏应是认识家庭"
        assert "请输入" not in body, "不应甩「请输入资产」"

        # 选兴趣 → 下一步
        page.locator(".interest-card").first.click()
        page.click(".onboard-card .btn-primary")

        # ② 粗画像：点「很多」+「不知道」各一个，然后看画像
        page.locator(".level-pill").first.click()       # 资产 → 很多
        page.click(".onboard-card .btn-primary")

        # ③ 60 秒反馈：画像 + 问题 + 声明 + CTA
        page.wait_for_selector(".profile-score", timeout=10000)
        result = page.inner_text(".onboard-card")
        assert "财富评分" in result
        assert "先留意" in result, "应展示 1-3 个问题"
        assert "演示" in result and "真实" in result, "应声明非真实数据"
        assert "录入我的真实数据" in result, "主 CTA 应是录入真实数据"
        assert "换一个家庭情况看看" in result, "应有次 CTA"
        assert "先看看产品" in result, "应有弱 CTA"

        page.screenshot(path=str(shot))
        browser.close()

    assert errors == [], f"浏览器 0 error 未满足: {errors}"
    assert shot.exists(), "截图未生成"
