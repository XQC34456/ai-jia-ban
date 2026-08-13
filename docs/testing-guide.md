# AI家办 · 测试入口 & 验证清单

> 用途：进入「真实用户测试与稳定性验证」阶段前的入口速查 + 逐项勾选清单。
> 当前基线：**233 个测试全绿**（A1 契约 → A2 工具 → A3.1 Runtime → A3.2 Provider → A4 API）。

---

## 1. 测试入口

### 1.1 自动化测试

```bash
cd D:\Claude_Code\ai-jia-ban

# 全量（Windows 必须带编码环境变量，否则中文输出乱码）
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m pytest -q

# 单个文件 / 单个用例
python -m pytest tests/test_agent_api.py -v
python -m pytest tests/test_agent_api.py::test_agent_chat_requires_auth -v

# 只看关键铁律守门（隔离/契约/防编造）
python -m pytest tests/test_agent_contract.py tests/test_agent_provider.py tests/test_agent_api.py -q
```

| 测试文件 | 守什么 |
|---------|--------|
| `test_agent_contract.py` | A1 七意图封闭 + MetricRef.value 必带 source |
| `test_agent_tools.py` | A2 工具适配器（取数不计算） |
| `test_agent_runtime.py` | A3.1 Runtime：拒算门/路由/参数/零 engine |
| `test_agent_provider.py` | A3.2 Provider：隔离/结构化/降级/数字零伪造 |
| `test_agent_api.py` | A4 API：401/422/透传/密钥隔离 |
| `test_scenario_contract.py` | C3.5 场景参数契约（422/400 双层） |
| `test_api_wealth.py` / `test_api_scenario.py` / `test_api_goal.py` | 端点集成 + 数据隔离 |
| `test_apply_scenario.py` / `test_compare_scenarios.py` | 场景纯函数 + 对比 |

### 1.2 服务启动

```bash
# 默认（http://127.0.0.1:8000，热重载）
python -m app.main
# 或
uvicorn app.main:app --reload

# 隔离数据库（不碰真实 data.db，测试/演示用）
AIJIABAN_DB=/tmp/demo.db python -m app.main

# 无 key 启动（走确定性兜底，不连外部 LLM）
LLM_API_KEY= python -m app.main
```

### 1.3 前端入口

- 主页（对话建档 + 看板）：`http://127.0.0.1:8000/`
- 静态资源：`/static`

### 1.4 API 入口

除 `/api/health`、注册/登录外，**全部**接口需 `Authorization: Bearer <token>`。

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/health` | 无 | `{ok, llm}`，llm=是否已配 key |
| POST | `/api/register` | 无 | 返回 `{token, username, tier}` |
| POST | `/api/login` | 无 | 返回 `{token, ...}` |
| GET | `/api/me` | 登录 | `{username, tier}` |
| POST | `/api/upgrade` | 登录 | 模拟开通 VIP |
| GET | `/api/family` | 登录 | 档案 + 快照 + 体检 |
| POST | `/api/chat` | 登录 | 旧对话（confirm/answer） |
| POST | `/api/confirm` | 登录 | 确认/撤销建档 |
| GET | `/api/report` | VIP | 深度报告 |
| POST | `/api/decision` | VIP | 决策模拟 |
| POST | `/api/family/entity/{table}` | 登录 | 看板新增实体 |
| PUT/DELETE | `/api/entity/{table}/{id}` | 登录 | 看板编辑/删除 |
| GET | `/api/wealth/overview` | 登录 | 财富驾驶舱（核心） |
| GET | `/api/wealth/issues` | 登录 | 问题/告警/优先级/建议 |
| GET | `/api/wealth/goals` | 登录 | 目标统一测算 |
| POST | `/api/wealth/scenario/{name}` | VIP | 情景模拟 |
| POST | `/api/wealth/scenario/{name}/compare` | VIP | 情景对比（baseline+方案） |
| POST | `/api/agent/chat` | 登录 | **A4 自然语言入口**（新增） |

> `name ∈ {buy_house, prepay, invest, income_change}`；`table ∈ {person, asset, liability, cashflow, ...}`（见 `db.ENTITY_COLS`）。

---

## 2. 验证清单

### A. 启动前环境检查

- [ ] `pip install -r requirements.txt`（fastapi / uvicorn / pydantic / httpx / pytest）
- [ ] `.env` 已就位且含 `LLM_API_KEY`（不配置则走规则兜底，可先跳过）
- [ ] `.env` 在 `.gitignore` 内、git 状态不含它（`git status` 只看 `.env.example`）
- [ ] `data.db` 未入库（`.gitignore` 已排除 `*.db`）

### B. 回归测试（自动化，改动后必跑）

- [ ] `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m pytest -q` → **233 passed**
- [ ] 新增代码有对应测试（TDD 红→绿→提交）
- [ ] 无跳过/预期失败残留（`-q` 尾部无 `s`/`x`）

### C. 分层守门自检（铁律，改代码后重点看）

- [ ] **AI 不算钱**：`app/agent/**` 与 `app/api/agent.py` 源码不含 `engine`（`test_agent_layer_does_not_import_engine` / `test_agent_api_source_has_no_engine_or_http`）
- [ ] **Provider 隔离**：只有 `app/agent/providers/deepseek.py` import `httpx`，核心层零 HTTP
- [ ] **MetricRef 防编造**：带数值的指标必带 `source`（`overview.*` / `comparison.A.*` 路径）
- [ ] **API 层零加工**：端点响应 JSON == `handle()` 返回值序列化（透传闸）
- [ ] **模型名配置化**：源码不含具体型号，只读 `LLM_MODEL`

### D. API 冒烟清单（无 key，确定性兜底，不连外部）

先跑起来（隔离库 + 空 key），再按序验证：

```bash
AIJIABAN_DB=/tmp/smoke.db LLM_API_KEY= python -m app.main
```

- [ ] `GET /api/health` → `{"ok":true,"llm":false}`
- [ ] 注册拿 token：`POST /api/register` `{"username":"t","password":"secret123"}`
- [ ] `POST /api/agent/chat`（无 token）→ **401**
- [ ] `POST /api/agent/chat`（`Authorization: Bearer <坏token>`）→ **401**
- [ ] `POST /api/agent/chat`（缺 `message` / 空串 / 2001 字）→ **422**
- [ ] `POST /api/agent/chat` `{"message":"看看我的家庭财富"}` → **200**，`intent=VIEW_OVERVIEW`、`status=ok`、每个 `metrics[].value` 非空时带 `source`
- [ ] `POST /api/agent/chat` `{"message":"帮我算 100 万复利 20 年"}` → **200**、`status=refused`（拒算门）
- [ ] `POST /api/agent/chat` `{"message":"我想投资 30 万"}`（免费用户）→ 缺参数走 `need_clarification`
- [ ] `POST /api/upgrade` 后 `POST /api/wealth/scenario/invest/compare`（带参数）→ **200**（VIP 门放行）
- [ ] 免费用户 `GET /api/report` → **403**

### E. 真实 Key 端到端（手动，连 DeepSeek，可选但建议上线前做）

> 差异点：真实 key 会启用 LLM 意图兜底 + 参数提取；当前自动化测试全走 Fake/Null。

- [ ] `.env` 填真实 `LLM_API_KEY` + `LLM_MODEL`，重启服务
- [ ] `GET /api/health` → `{"llm":true}`
- [ ] `POST /api/agent/chat` `{"message":"我想投资 30 万到股票"}`（VIP）→ `status=ok` 且 9 个对比指标齐全、`source=comparison.A.*`
- [ ] 用**口语/别称**测试参数提取（如「买套 300 万的房」「提前还 20 万」）→ 参数被正确抽取
- [ ] 观察一次**超时降级**：临时把 `LLM_BASE_URL` 指向不可达地址 → 请求仍 200、走兜底，不 500
- [ ] 确认响应体**不泄露** key / Provider 原始错误文本

### F. 稳定性 / 边界

- [ ] 空家庭数据（新注册、不建档）→ 各接口仍返回合法结构，不 500
- [ ] 两个用户数据隔离（A 建档，B 读不到，`/api/wealth/overview` 各看各的）
- [ ] 同一 token 并发请求无状态串扰（端点无全局锁）
- [ ] 超长/畸形 JSON body → 4xx，不崩溃

---

## 3. 已知文档债

- [ ] `README.md` 的 API 表已过时：缺 `/api/wealth/*`、`/api/agent/chat` 及 VIP 门说明，建议补。
