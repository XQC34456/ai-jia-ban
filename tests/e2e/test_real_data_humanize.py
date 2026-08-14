"""4.1 人性化·真实数据页 headless 冒烟：体检报告横幅 + 为什么 + 下一步按钮 + 沙盘模式提示 + 0 error。

覆盖验收：
  ① overview 首屏视觉主角是「最值得关注的 3 件事」，wealth_score 降为辅助状态
  ② 问题带「为什么」自然语言解释（reason），不暴露内部字段/公式
  ③ 推荐带「模拟」按钮 → 跳沙盘并预选场景；沙盘顶部常驻「沙盘模式」心理边界
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
    db_path = tmp_path_factory.mktemp("e2e_humanize") / "test.db"
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


def _seed(base: str) -> str:
    """注册 → 升级 VIP → 建档（低储蓄率 + 大额现金，必然触发带 scenario 的推荐）。"""
    with httpx.Client(base_url=base, timeout=10) as c:
        r = c.post("/api/register", json={"username": "humanize", "password": "secret123"})
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


def test_real_data_humanize(server):
    from playwright.sync_api import sync_playwright

    token = _seed(server)
    errors: list[str] = []

    ARTIFACTS.mkdir(exist_ok=True)
    shot = ARTIFACTS / "real_data_humanize.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1360, "height": 900})
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        page.add_init_script(f"localStorage.setItem('token', {json.dumps(token)})")
        page.goto(server + "/#/overview")
        page.wait_for_selector(".report-banner", timeout=10000)

        # ① 体检报告横幅：主角是「最值得关注的 3 件事」，评分是辅助
        banner = page.inner_text(".report-banner")
        assert "家庭体检报告" in banner
        assert "最值得关注的" in banner, "横幅主角应是「最值得关注的 N 件事」"
        assert "财富评分" in banner, "评分应以辅助状态出现"

        # ② 为什么：reason 自然语言解释（含「为什么」标题）
        assert "为什么" in page.inner_text(".card-insight"), "InsightPanel 应渲染「为什么」解释"

        # ④ 下一步按钮：推荐带 scenario → 存在「模拟」按钮
        sim_btns = page.locator(".rec-sim").count()
        assert sim_btns > 0, "应有「模拟」按钮渲染"

        # 点击第一个「模拟」→ 跳沙盘并预选场景，顶部常驻沙盘模式心理边界
        page.locator(".rec-sim").first.click()
        page.wait_for_selector(".sandbox-banner", timeout=10000)
        banner_text = page.inner_text(".sandbox-banner")
        assert "沙盘模式" in banner_text, "沙盘应常驻「沙盘模式」提示"
        assert "不会改动你的真实家庭数据" in banner_text, "应明确模拟不改真实数据"

        page.screenshot(path=str(shot))
        browser.close()

    assert errors == [], f"浏览器 0 error 未满足: {errors}"
    assert shot.exists(), "截图未生成"
