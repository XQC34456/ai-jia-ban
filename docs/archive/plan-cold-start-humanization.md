# Cold Start Humanization 实现计划

> **Goal:** 让新用户登录后不再面对空 overview 或「请输入家庭资产」，而是走 3 步温暖冷启动：认识家庭 → 粗画像 → 60 秒反馈。

**Architecture:** 粗画像档位 → 典型值 → 构造临时 `family_data` → 复用 `build_overview`（纯函数，零 DB 依赖）实算画像 + 问题。**不落库、不接 LLM、不新增财富计算**——Engine 算 / Decision 判断 / 前端只做「人话 + 向导」。

**Tech Stack:** FastAPI（新增 onboarding router）· Vue 3 CDN（新增 onboarding 视图）· Playwright + pytest + node --test。

## 铁律对齐（红线）

- 粗画像数据**绝不写 DB**：后端 preview 接口纯计算；前端用 `localStorage.onboarded` 标记「已完成冷启动」（前端状态，非落库）。
- 财富数字**只来自 `build_overview`**：preview 只是给它喂「典型值假设输入」，结论（wealth_score/net_worth/issues）全部后端实算。
- LLM **绝不参与**：60 秒反馈的 1-3 个问题 = `overview.issues`（build_issues 确定性），画像 = `wealth_level`/`net_worth`，文案用模板不调 LLM。
- 冻结契约（A1-A4、Engine、Decision、API Schema、Agent Runtime）**一律不改**：新增独立 router，不碰现有 `/api/wealth/*`。

## 典型值映射表（演示用假设输入，非用户真实数据）

| 档位 | 总资产 | 月收入 | 负债本金 | 储蓄率 |
|------|--------|--------|----------|--------|
| `high`（很多） | 500 万 | 8 万 | 200 万 | 50% |
| `mid`（一般） | 200 万 | 3 万 | 50 万 | 30% |
| `low`（少） | 50 万 | 1 万 | 0 | 10% |
| `unknown`（不知道） | 200 万 | 3 万 | 50 万 | 30%（= mid 中性） |

构造规则：存款 = 总资产 × 0.4，房产 = 总资产 × 0.6；月支出 = 月收入 × (1 − 储蓄率)；负债 > 0 时生成一条房贷（月供 = 本金 × 0.005，利率 3.5%，300 期）。

---

## Task 1: 后端典型值构造器（纯函数）

**Files:**
- Create: `app/services/onboarding.py`
- Test: `tests/test_onboarding.py`

**Interfaces:**
- Produces: `typical_family(profile: dict) -> dict`，返回 `family_data` 形状（`persons/assets/liabilities/cashflows/goals/...`），可直接喂 `build_overview`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_onboarding.py
from app.services.onboarding import typical_family

def test_typical_family_high():
    d = typical_family({"assets": "high", "income": "high", "debt": "high", "savings": "high"})
    inc = d["cashflows"][0]["amount"]
    assert inc == 80000
    assert sum(a["value"] for a in d["assets"]) == 5_000_000
    assert d["liabilities"][0]["principal"] == 2_000_000

def test_typical_family_unknown_is_mid():
    d = typical_family({})  # 全 unknown
    assert d["cashflows"][0]["amount"] == 30000
    assert d["assets"][0]["value"] == 2_000_000 * 0.4

def test_typical_family_low_has_no_liability():
    d = typical_family({"debt": "low"})
    assert d["liabilities"] == []
```

- [ ] **Step 2: 跑测试确认失败** → `pytest tests/test_onboarding.py -v`，预期 `ModuleNotFoundError`
- [ ] **Step 3: 实现**

```python
# app/services/onboarding.py
"""冷启动典型值构造：把粗画像档位映射成 build_overview 可消费的 family_data（纯函数、零 DB、不落库）。"""
from __future__ import annotations

TYPICAL = {
    "high":    (5_000_000, 80_000, 2_000_000, 0.5),
    "mid":     (2_000_000, 30_000, 500_000, 0.3),
    "low":     (500_000, 10_000, 0, 0.1),
    "unknown": (2_000_000, 30_000, 500_000, 0.3),
}

def typical_family(profile: dict | None = None) -> dict:
    profile = profile or {}
    assets = TYPICAL.get(profile.get("assets", "unknown"), TYPICAL["unknown"])
    income = TYPICAL.get(profile.get("income", "unknown"), TYPICAL["unknown"])
    debt = TYPICAL.get(profile.get("debt", "unknown"), TYPICAL["unknown"])
    savings = TYPICAL.get(profile.get("savings", "unknown"), TYPICAL["unknown"])
    total_assets, monthly_income, debt_principal, savings_rate = assets[0], income[1], debt[2], savings[3]
    deposit = total_assets * 0.4
    house = total_assets * 0.6
    expense = monthly_income * (1 - savings_rate)
    return {
        "family": {"name": "示例家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1990, "monthly_income": monthly_income}],
        "assets": [
            {"type": "存款", "name": "现金", "value": deposit},
            {"type": "房产", "name": "自住房", "value": house},
        ],
        "liabilities": (
            [{"type": "房贷", "name": "房贷", "principal": debt_principal,
              "monthly_payment": round(debt_principal * 0.005, 2), "interest_rate": 3.5, "remaining_months": 300}]
            if debt_principal > 0 else []
        ),
        "cashflows": [
            {"flow_type": "income", "category": "工资", "amount": monthly_income, "period": "月"},
            {"flow_type": "expense", "category": "日常", "amount": round(expense, 2), "period": "月"},
        ],
        "goals": [], "reminders": [], "insurance": [], "family_profile": None,
    }
```

- [ ] **Step 4: 跑测试确认通过**
- [ ] **Step 5: Commit** `feat(onboarding): add typical family builder`

---

## Task 2: 后端 preview 接口（不落库）

**Files:**
- Create: `app/schemas/onboarding.py`
- Create: `app/api/onboarding.py`
- Modify: `app/main.py`（注册 router）
- Test: `tests/test_onboarding.py`

**Interfaces:**
- Consumes: `typical_family`（Task 1）、`build_overview`（`app.services`）、`get_current_user`（`app.api.deps`）
- Produces: `POST /api/onboarding/preview` → `{interests, overview}`（overview 即 `build_overview` 完整返回，含 `issues`）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_onboarding.py（追加）
def test_preview_does_not_write_db(client, auth_header):
    r = client.post("/api/onboarding/preview",
                    json={"interests": ["买房 / 投资"], "profile": {"assets": "high"}},
                    headers=auth_header)
    assert r.status_code == 200
    body = r.json()
    assert "overview" in body and "issues" in body["overview"]
    assert body["overview"]["wealth_score"] is not None
    # 不落库：db 里没有任何新增 family/entity
```

（`client` / `auth_header` 沿用现有测试的 fixture，见 `tests/conftest.py`；若不存在则本任务补一个最小 fixture：注册→拿 token。）

- [ ] **Step 2: 跑测试确认失败**（`404` 或 `router 未注册`）
- [ ] **Step 3: 实现 schemas + router**

```python
# app/schemas/onboarding.py
from enum import Enum
from pydantic import BaseModel, Field

class ProfileLevel(str, Enum):
    high = "high"; mid = "mid"; low = "low"; unknown = "unknown"

class ProfileLevels(BaseModel):
    assets: ProfileLevel = ProfileLevel.unknown
    income: ProfileLevel = ProfileLevel.unknown
    debt: ProfileLevel = ProfileLevel.unknown
    savings: ProfileLevel = ProfileLevel.unknown

class OnboardingPreviewRequest(BaseModel):
    interests: list[str] = Field(default_factory=list)
    profile: ProfileLevels = Field(default_factory=ProfileLevels)
```

```python
# app/api/onboarding.py
"""冷启动 preview：粗画像 → 典型值 → build_overview 实算，绝不写库。"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from ..schemas.onboarding import OnboardingPreviewRequest
from ..services import build_overview
from ..services.onboarding import typical_family
from .deps import get_current_user

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

@router.post("/preview")
def onboarding_preview(req: OnboardingPreviewRequest, user: dict = Depends(get_current_user)):
    data = typical_family(req.profile.model_dump())
    return {"interests": req.interests, "overview": build_overview(data)}
```

- [ ] **Step 4: 在 `app/main.py` 注册**（`from .api import onboarding` + `app.include_router(onboarding.router)`，对齐现有 router 注册写法）
- [ ] **Step 5: 跑测试确认通过** + 全量 pytest 无回归
- [ ] **Step 6: Commit** `feat(onboarding): add preview endpoint (no DB write)`

---

## Task 3: 前端 onboarding 视图（3 步向导）

**Files:**
- Create: `static/views/onboarding.js`
- Modify: `static/shell.js`（未建档检测 + 覆盖渲染）
- Modify: `static/store.js`（`onboarded` 标志）
- Modify: `static/style.css`（向导样式）

**Interfaces:**
- Consumes: `api()`（`static/api.js`）、`POST /api/onboarding/preview`
- Produces: `OnboardingView`（export，供 shell 引用）；`store.onboarded` 标志

- [ ] **Step 1: store 加 onboarded 标志**

```js
// static/store.js（store 对象内加一行）
onboarded: localStorage.getItem('onboarded') === '1',
```

- [ ] **Step 2: 实现 `static/views/onboarding.js`**

```js
// 冷启动 3 步向导：认识家庭 → 粗画像 → 60 秒反馈。铁律：不落库、不接 LLM、只消费 preview。
import { store, ensureOverview } from '../store.js';
import { api } from '../api.js';
import { fmtMoney } from '../format.js';
import { navigate } from '../router.js';

const { reactive, ref, computed } = Vue;

const INTERESTS = [
  { key: 'asset', label: '买房 / 投资', desc: '首付、房贷、钱生钱' },
  { key: 'goal', label: '养老 / 教育', desc: '退休金、教育金储备' },
  { key: 'safety', label: '现金流 / 负债', desc: '月光、债务压力' },
  { key: 'curious', label: '只是随便看看', desc: '先了解一下' },
];
const DIMENSIONS = [
  { key: 'assets', label: '家庭资产', hint: '房子、存款、投资加起来' },
  { key: 'income', label: '每月收入', hint: '全家月入大概多少' },
  { key: 'debt', label: '家庭负债', hint: '房贷、车贷、信用卡' },
  { key: 'savings', label: '每月结余', hint: '每月能存下多少' },
];
const LEVELS = [
  { v: 'high', l: '很多' }, { v: 'mid', l: '一般' },
  { v: 'low', l: '很少' }, { v: 'unknown', l: '不知道' },
];

export const OnboardingView = {
  setup(_, { emit }) {
    const step = ref(1);
    const interests = reactive({});
    const levels = reactive({ assets: 'unknown', income: 'unknown', debt: 'unknown', savings: 'unknown' });
    const busy = ref(false);
    const error = ref(null);
    const preview = ref(null);

    function next() { step.value++; }
    async function runPreview() {
      busy.value = true; error.value = null;
      try {
        preview.value = await api('/api/onboarding/preview', {
          method: 'POST', token: store.auth.token,
          body: { interests: Object.keys(interests).filter(k => interests[k]), profile: { ...levels } },
        });
      } catch (e) { error.value = e.message; }
      finally { busy.value = false; step.value = 3; }
    }
    function finish(goData) {
      localStorage.setItem('onboarded', '1');
      store.onboarded = true;
      emit('done');
      if (goData) navigate('data');
    }
    const o = computed(() => preview.value && preview.value.overview);
    const topIssues = computed(() => {
      const is = o.value && o.value.issues;
      return (is || []).slice(0, 3);
    });
    return { step, interests, levels, busy, error, preview, o, topIssues,
             INTERESTS, DIMENSIONS, LEVELS, next, runPreview, finish, fmtMoney };
  },
  template: `
  <div class="onboard-mask">
    <div class="onboard-card">
      <div class="onboard-step">第 {{ step }} / 3 步</div>

      <!-- Step 1：认识你的家庭 -->
      <template v-if="step === 1">
        <h2>先认识一下你的家庭 👋</h2>
        <p class="onboard-sub">你最近最关心哪方面？可多选，选错了没关系。</p>
        <div class="interest-grid">
          <button v-for="it in INTERESTS" :key="it.key" class="interest-card"
                  :class="{ active: interests[it.key] }" @click="interests[it.key] = !interests[it.key]">
            <b>{{ it.label }}</b><span>{{ it.desc }}</span>
          </button>
        </div>
        <button class="btn-primary" @click="next">下一步</button>
      </template>

      <!-- Step 2：粗画像（不知道也没关系） -->
      <template v-else-if="step === 2">
        <h2>大概描述一下你的家庭</h2>
        <p class="onboard-sub">不用精确，凭感觉选就行——「不知道」也没关系。</p>
        <div v-for="d in DIMENSIONS" :key="d.key" class="dim-row">
          <div class="dim-head"><b>{{ d.label }}</b><span>{{ d.hint }}</span></div>
          <div class="level-pills">
            <button v-for="lv in LEVELS" :key="lv.v" class="level-pill"
                    :class="{ active: levels[d.key] === lv.v }" @click="levels[d.key] = lv.v">{{ lv.l }}</button>
          </div>
        </div>
        <div v-if="error" class="form-error">{{ error }}</div>
        <button class="btn-primary" :disabled="busy" @click="runPreview">{{ busy ? '正在生成…' : '看看我的家庭画像' }}</button>
      </template>

      <!-- Step 3：60 秒反馈 -->
      <template v-else>
        <h2>这是你现在的家庭画像</h2>
        <template v-if="o">
          <div class="profile-hero">
            <div class="profile-score"><b>{{ o.wealth_score }}</b><span>财富评分</span></div>
            <div class="profile-net">净资产 {{ fmtMoney(o.net_worth) }}<span class="profile-level">{{ o.wealth_level }}</span></div>
          </div>
          <div class="profile-issues" v-if="topIssues.length">
            <div class="profile-issues-title">先留意这 {{ topIssues.length }} 件事</div>
            <div v-for="(iss, i) in topIssues" :key="iss.issue_id" class="profile-issue">
              <span class="issue-rank">{{ i + 1 }}</span>{{ iss.title }}
            </div>
          </div>
          <p class="onboard-sub">这些是基于你粗略选择的「示例画像」算出来的，不是你的真实数字。</p>
        </template>
        <div class="onboard-cta">
          <button class="btn-primary" @click="runPreview">换个选法再算</button>
          <button class="btn-ghost" @click="finish(true)">录入真实数据，看准的</button>
          <button class="btn-link" @click="finish(false)">先随便逛逛</button>
        </div>
      </template>
    </div>
  </div>`,
};
```

- [ ] **Step 3: 在 shell.js 接入「未建档 → onboarding 覆盖」**

```js
// static/shell.js（import 增加 OnboardingView，App 内加 needOnboarding + watch loggedIn）
const needOnboarding = ref(!store.onboarded);
watch(loggedIn, async (v) => {
  if (!v || store.onboarded) { needOnboarding.value = false; return; }
  try {
    await ensureOverview();
    const b = store.overview;
    // 有数据（已建档）→ 跳过；空数据 → 走冷启动
    if (b && !(b.net_worth === 0 && (!b.issues || !b.issues.length))) {
      localStorage.setItem('onboarded', '1'); store.onboarded = true; needOnboarding.value = false;
    } else {
      needOnboarding.value = true;
    }
  } catch { needOnboarding.value = false; }
});
// template: <onboarding-view v-if="loggedIn && needOnboarding" @done="needOnboarding=false" />
```

- [ ] **Step 4: 样式**（`.onboard-mask/.onboard-card/.interest-grid/.level-pills/.profile-hero/.profile-issues`，复用现有 `--positive-soft/--warn-soft/--line` 变量）
- [ ] **Step 5: Commit** `feat(onboarding): add 3-step cold start wizard`

---

## Task 4: 浏览器冒烟测试

**Files:**
- Create: `tests/e2e/test_onboarding_smoke.py`

- [ ] **Step 1: 写测试**（对齐 `test_sandbox_smoke.py` 的 server fixture 模式）

```python
def test_onboarding_smoke(server):
    # 注册新用户（不建档）→ 注入 token → 进首页 → 断言出现「认识你的家庭」
    # → 选兴趣 → 下一步 → 选粗画像 → 「看看我的家庭画像」→ 断言出现「财富评分」+ 问题
    # → 0 console error / pageerror → 截图 artifacts/cold_start_smoke.png
```

- [ ] **Step 2: 跑测试确认通过**（复用 chromium 缓存）
- [ ] **Step 3: 全量验证**：`pytest -q` + `node --test tests/js/*.test.js` 全绿
- [ ] **Step 4: Commit** `test(onboarding): add browser smoke test for cold start`

---

## 自我审查

1. **Spec 覆盖**：① 不面对「请输入资产」→ onboarding 覆盖空 overview；② 认识家庭 → Step 1 兴趣；③ 粗画像 slider + 不知道 → Step 2；④ 60 秒反馈 → Step 3 preview。✅
2. **铁律**：不落库（preview 纯计算 + localStorage 标志）、LLM 不参与、Engine 实算、不碰冻结契约。✅
3. **占位符扫描**：无 TBD/TODO；`client/auth_header` fixture 已标注「沿用或补最小 fixture」。✅
