# A4 Agent API · 密钥注入与安全边界设计

> 状态：待评审。本文件冻结 A4 的最小闭环 + 密钥注入方案 + 安全边界。
> 完成 A3.2（DeepSeek Provider）后，进入真实 LLM 边界前必须先定这一份，避免回头改已冻结的 Provider/Runtime 契约。

## 一句话目标

打通「自然语言 → Agent → Wealth Engine → 结构化结果」这一条最小链，把 `handle()` 挂到
`POST /api/agent/chat`，同时守住「AI 不算钱」铁律。

---

## 1. 密钥注入（已定：系统级单一 Key）

### 1.1 归属模型

**系统级单一 DeepSeek Key**：服务端持有唯一 key，所有用户共享；前端**永不接触** key，
无 key 输入框，key 对前端完全透明。成本由运营方承担。后续如需 BYOK 再平滑升级（不在 A4）。

### 1.2 读取链（已实现，A3.2 无需改动）

```
环境变量 LLM_API_KEY / LLM_MODEL / LLM_BASE_URL / LLM_PROVIDER
        ↓
app/agent/providers/__init__.py → get_provider()
        ↓
DeepSeekProvider  |  NullProvider（缺 key/model / provider 不支持）
```

- key **只从环境变量读**，不硬编码进代码，不进 git（`.gitignore` 已排除 `.env`）。
- **dev / prod 同机制**：本地读 `.env`，生产读 secret manager 注入的环境变量；代码不感知区别。
- 缺 key → `get_provider()` 返回 `NullProvider` → `handle()` 走确定性兜底，**不 500、不猜、不编**。

### 1.3 日志脱敏（硬约束）

- 任何日志**不得**打印：`LLM_API_KEY`、`Authorization` header、Provider 原始响应体。
- 错误日志只记 `status` 与通用原因（如 `timeout`），不落原始 payload。

---

## 2. A4 安全边界

| 维度 | 约束 |
|------|------|
| **认证** | `POST /api/agent/chat` 必须 Bearer token（复用 `get_user_by_token`），**禁止匿名**，未带 token → 401 |
| **授权** | SCENARIO_COMPARE 的 VIP 门已在 A2 `compare_scenario` 内（403 → refused），端点**不重复判断**，只透传 |
| **错误隔离** | Provider 原始响应/异常**绝不原样返回前端**；统一收敛到 `AgentResponse.status ∈ {ok, need_clarification, refused, error}`，`error` 只回通用文案，不泄露内部细节 |
| **超时/并发** | DeepSeek 超时 30s（Provider 默认）→ `None` → 确定性兜底；端点无状态，天然并发安全，**不引入全局锁/队列** |
| **输入约束** | `message` 长度上限 2000 字，超限 → 422 |

---

## 3. A4 最小闭环（只做 6 件事）

```text
POST /api/agent/chat
        │  AgentRequest
        ▼
get_user_by_token()  → user dict（family_id / tier）
        │
        ▼
get_provider()  →  LLMProvider（DeepSeek | Null）
        │
        ▼
handle(message, user, llm=provider)   ← A3.1 Runtime，一字不改
        │
        ├── A2 Tool → Wealth Engine（数字唯一来源）
        ▼
AgentResponse  →  JSON（response_model=AgentResponse，原样契约化返回）
```

1. **AgentRequest Schema** — `message: str`（必填，≤2000），`context: dict | None`（可选，供 EXPLAIN_RESULT 复用）。
2. **`POST /api/agent/chat`** — 依赖 `get_user_by_token`。
3. **用户身份/家庭数据获取** — `user` dict 直接喂给 `handle()`（内部经 `db.dump_family` 取数）。
4. **`get_provider()` 注入** — 每次请求惰性取一次（读环境变量，成本可忽略）。
5. **`handle()` 调用** — `llm=get_provider()`。
6. **AgentResponse 原样返回** — `response_model=AgentResponse`，序列化即契约。

---

## 4. 新增铁律：API 层不得修改 AgentResponse

```text
handle()
   ↓
AgentResponse   ← 唯一事实源
   ↓
API 只做 JSON 序列化
```

**禁止** API 层：
- 补 `metrics` / `summary` / `recommendations` / `next_actions`
- 改写 `status` / `intent`
- 自行拼财富数字或自然语言话术（话术在 A3 模板 / LLM 解释层，数字在 Engine）

守门测试：`handle()` 返回值 `model_dump()` == 端点响应 JSON（逐字段相等）。

**禁止** API 层 import `engine` / `httpx`（数字与 HTTP 都不该出现在 API 层）。

---

## 5. 明确不做（A4 一期）

```
❌ 流式输出（SSE）      ❌ 多轮记忆          ❌ 对话数据库
❌ WebSocket            ❌ RAG               ❌ Prompt 管理后台
❌ 多 Agent             ❌ 自动执行调仓       ❌ 自动写回家庭资产
❌ 前端传 Key / BYOK    ❌ per-user Key 存储
```

---

## 6. 组件与文件

| 文件 | 动作 | 职责 |
|------|------|------|
| `app/schemas/agent.py` | 修改 | 新增 `AgentRequest`（message / context），`AgentResponse` 已冻结不改 |
| `app/api/agent.py` | 新建 | `POST /api/agent/chat` 端点 |
| `app/main.py` | 修改 | 挂路由 `include_router(agent_router)` |
| `app/api/deps.py` | 复用 | `get_user_by_token`（不新增） |
| `tests/test_agent_api.py` | 新建 | 端点契约 + 守门测试 |

---

## 7. A4 验收门槛

1. 未带 token → **401**。
2. `VIEW_OVERVIEW` 等意图 → `AgentResponse` 原样 JSON（`status=ok` + `metrics` 带 source）。
3. `SCENARIO_COMPARE` 免费用户 → `status=refused` + `next_actions=["upgrade"]`。
4. 未配置 key（`LLM_PROVIDER` 缺/`LLM_API_KEY` 缺）→ 确定性兜底，仍返回合法 `AgentResponse`，**不 500**。
5. **守门**：端点响应 JSON == `handle()` 返回值序列化（API 层零加工）。
6. **守门**：`app/api/agent.py` 源码不含 `engine` / `httpx`。
7. `message` 超 2000 字 → **422**。
