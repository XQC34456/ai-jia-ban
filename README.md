# AI家办 · 家庭财富智管家（MVP）

面向普通家庭的 AI 家庭财富管理操作系统 —— 第一版最小可用实现。

**核心主链路**：对话 → 结构化建档（含确认） → 确定性计算 → 3 问题体检 → 数据化回答。

---

## 快速开始

```bash
cd D:\Claude_Code\ai-jia-ban

# 1. 安装依赖（已装可跳过）
pip install -r requirements.txt

# 2. 启动（默认 http://127.0.0.1:8000）
python -m app.main
# 或
uvicorn app.main:app --reload
```

浏览器打开 `http://127.0.0.1:8000`，即可对话建档。

---

## 接入 DeepSeek（可选，强烈建议）

产品默认用**内置规则兜底**，开箱即用但抽取/回答较机械。接入 DeepSeek 后，抽取走 function calling、回答走 LLM。

1. 复制 `.env.example` 为 `.env`
2. 填入你的 key：

```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

3. 重启服务。右上角会显示「AI 引擎：已接入大模型」。

> 换豆包/通义/GLM 等 OpenAI 兼容接口，改 `LLM_BASE_URL` 和 `LLM_MODEL` 即可。

---

## 跑测试

```bash
# Windows 需带编码环境变量，否则中文输出乱码
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m pytest -q
```

---

## 架构

```
接入层       Web H5（static/，Vue 3 单页 App Shell + hash 路由，8 视图）
   ↓
对话编排层   app/chat.py    抽取 → 确认 → 落地 → 重算 → 反馈（状态机）
   ↓
抽取层       app/extraction.py  规则 / LLM(function calling) 可插拔
   ↓
计算引擎层   app/calc_engine.py 资产负债/现金流/储蓄率/应急月数/安全边际（纯函数）
体检层       app/health.py      「最值得关注的 3 个问题」规则引擎
   ↓
数据层       app/db.py       SQLite：users/family/person/asset/liability/cashflow/goal/reminder
```

**关键设计**：财务数字一律由 `calc_engine.py` 的纯函数计算，绝不交给 LLM；LLM 只做「听懂」和「说人话」。

---

## API

> 除 `/api/health`、注册/登录外，所有接口需带请求头 `Authorization: Bearer <token>`，未带/无效 → 401；数据随登录用户隔离。VIP 门（报告/决策/情景对比）：免费用户 → 403。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（无需鉴权），返回 `{ok, llm}` |
| POST | `/api/register` | 注册，返回 token（自动创建并绑定家庭） |
| POST | `/api/login` | 登录，返回 token |
| GET | `/api/me` | 当前用户信息 |
| POST | `/api/upgrade` | 模拟开通 VIP（无支付，TODO 接支付） |
| GET | `/api/family` | 家庭档案 + 快照 + 体检 |
| POST | `/api/chat` | 对话，返回 confirm 或 answer |
| POST | `/api/confirm` | 确认/撤销待定建档动作 |
| GET | `/api/wealth/overview` | 财富驾驶舱（评分/净资产/配置/现金流/养老/问题） |
| GET | `/api/wealth/issues` | 问题/告警/优先级/建议 |
| GET | `/api/wealth/goals` | 目标统一测算 |
| POST | `/api/wealth/scenario/{name}` | 情景模拟（VIP） |
| POST | `/api/wealth/scenario/{name}/compare` | 情景对比（VIP） |
| POST | `/api/agent/chat` | AI Agent 自然语言入口（结构化 AgentResponse） |
| GET | `/api/report` | 深度报告（VIP 专属） |
| POST | `/api/decision` | 决策模拟（VIP 专属） |
| POST | `/api/family/entity/{table}` | 看板新增实体 |
| PUT/DELETE | `/api/entity/{table}/{id}` | 看板编辑/删除实体 |

> `name ∈ {buy_house, prepay, invest, income_change}`；`table ∈ {person, asset, liability, cashflow, ...}`。

---

## 已完成

- 统一 App Shell（`/` 单页 + hash 路由：Sidebar 8 项 + Topbar + 主内容区）
- 8 个视图：家庭总览 / 财富健康 / 资产配置 / 退休规划 / 家庭目标 / 风险问题 / 情景沙盘 / AI 顾问
- 家庭总览：财富评分 / 净资产 / 资产配置 / 现金流 / 流动性 / 债务 / 保障 / 养老 + AI 主动洞察（确定性 `build_issues`，非 LLM）
- 情景沙盘：买房 / 提前还贷 / 投资 / 收入变化，1~3 方案对比（VIP）
- 深度报告（LLM 建议 + 打印导出 PDF，VIP）
- 决策模拟器（买房 / 提前还贷，VIP）
- 登录 + VIP 分层（免费=对话建档 + 体检 + 目标 + 问题 + 各只读视图；VIP=报告 + 决策 + 情景沙盘；模拟开通按钮）

## 下一步（V2/V3）

- 注册即送 1 天 VIP 试用（`users.vip_expires_at` 字段已预留，改注册逻辑 + 到期检查即可）
- 接入真实支付（替换 `/api/upgrade` 模拟路由）
- 家庭安全边际升级为完整指标
- 目标系统深化（教育/养老/买房缺口 + 每月需存测算）
- 多成员数据权限
