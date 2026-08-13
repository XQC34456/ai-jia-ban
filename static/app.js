// AI家办 · 前端逻辑
const $ = (sel) => document.querySelector(sel);

let token = localStorage.getItem("aijiaban_token") || null;
let me = null; // { username, tier }
let state = { data: null, snapshot: null, problems: null };
let activeTab = "overview";
let modalCtx = null; // { entityKey, id }
let authMode = "login";

// 统一请求封装：自动带 token
async function api(path, opts = {}) {
  opts.headers = Object.assign({}, opts.headers);
  if (token) opts.headers["Authorization"] = "Bearer " + token;
  if (opts.body) opts.headers["Content-Type"] = "application/json";
  return fetch(path, opts);
}

// ===== 实体元数据 =====
const ASSET_TYPES = ["存款", "房产", "基金", "股票", "理财", "保险现金价值", "其他"];
const LIABILITY_TYPES = ["房贷", "车贷", "消费贷", "信用卡", "其他"];
const INCOME_CATS = ["工资", "奖金", "经营", "理财收益", "其他"];
const EXPENSE_CATS = ["餐饮", "教育", "医疗", "交通", "居住", "保险", "其他"];
const GOAL_TYPES = ["教育", "养老", "买房", "创业", "其他"];
const RELATIONS = ["本人", "配偶", "子女", "老人", "其他"];

const ENTITY_META = {
  assets: {
    api: "asset", label: "资产", icon: "💎",
    columns: [
      { key: "name", label: "名称" },
      { key: "type", label: "类型" },
      { key: "value", label: "价值", money: true },
    ],
    fields: [
      { key: "name", label: "名称", placeholder: "如：存款 / 自住房产" },
      { key: "type", label: "类型", type: "select", options: ASSET_TYPES },
      { key: "value", label: "当前价值", money: true, placeholder: "如：50万 或 500000", required: true },
    ],
  },
  liabilities: {
    api: "liability", label: "负债", icon: "🏦",
    columns: [
      { key: "name", label: "名称" },
      { key: "type", label: "类型" },
      { key: "principal", label: "剩余本金", money: true },
      { key: "monthly_payment", label: "月供", money: true },
    ],
    fields: [
      { key: "name", label: "名称", placeholder: "如：房贷" },
      { key: "type", label: "类型", type: "select", options: LIABILITY_TYPES },
      { key: "principal", label: "剩余本金", money: true, placeholder: "如：200万" },
      { key: "monthly_payment", label: "月供", money: true, placeholder: "如：8000" },
      { key: "interest_rate", label: "年利率(%)", number: true, placeholder: "如：3.8" },
      { key: "remaining_months", label: "剩余期数(月)", number: true, placeholder: "如：240" },
    ],
  },
  cashflow: {
    api: "cashflow", label: "现金流", icon: "💸",
    columns: [
      { key: "flow_type", label: "类型", map: (v) => v === "income"
          ? '<span class="tag tag-in">收入</span>' : '<span class="tag tag-out">支出</span>' },
      { key: "category", label: "分类" },
      { key: "amount", label: "金额", money: true },
      { key: "period", label: "周期" },
    ],
    fields: [
      { key: "flow_type", label: "类型", type: "select",
        options: [{ value: "income", label: "收入" }, { value: "expense", label: "支出" }], required: true },
      { key: "category", label: "分类", type: "select", options: INCOME_CATS },
      { key: "amount", label: "金额", money: true, placeholder: "如：1万5", required: true },
      { key: "period", label: "周期", type: "select", options: ["月", "年"] },
    ],
  },
  persons: {
    api: "person", label: "成员", icon: "👥",
    columns: [
      { key: "name", label: "姓名/称呼" },
      { key: "relation", label: "关系" },
      { key: "age", label: "年龄", map: (_v, row) => row.birth_year ? (new Date().getFullYear() - row.birth_year) + " 岁" : "—" },
    ],
    fields: [
      { key: "name", label: "姓名/称呼", placeholder: "如：孩子", required: true },
      { key: "relation", label: "关系", type: "select", options: RELATIONS },
      { key: "birth_year", label: "出生年份", number: true, placeholder: "如：2014" },
      { key: "monthly_income", label: "月收入", money: true, placeholder: "如：2万" },
      { key: "job", label: "职业", placeholder: "如：教师" },
    ],
  },
  goals: {
    api: "goal", label: "目标", icon: "🎯",
    fields: [
      { key: "name", label: "目标名称", placeholder: "如：孩子教育金", required: true },
      { key: "type", label: "类型", type: "select", options: GOAL_TYPES },
      { key: "target_amount", label: "目标金额", money: true, placeholder: "如：100万", required: true },
      { key: "target_date", label: "目标日期", type: "date" },
      { key: "current_saved", label: "已存金额", money: true, placeholder: "如：10万" },
    ],
  },
};

// ===== 工具 =====
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtMoney(v) {
  if (v == null) return "—";
  if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + "万";
  return Number(v).toLocaleString("zh-CN");
}
function fmtMoneyInput(v) {
  if (v == null || v === "") return "";
  if (v % 10000 === 0) return (v / 10000) + "万";
  return String(v);
}
function parseMoney(s) {
  s = String(s).trim().replace(/,/g, "");
  if (!s) return null;
  const m = s.match(/^(\d+(?:\.\d+)?)\s*(万)?\s*(\d+)?$/);
  if (!m) return null;
  let v = parseFloat(m[1]);
  if (m[2]) { v *= 10000; if (m[3]) v += (m[3].length === 1 ? parseInt(m[3]) * 1000 : parseInt(m[3])); }
  return v;
}

// ===== 初始化 =====
async function init() {
  if (token) {
    try {
      const r = await api("/api/me");
      if (r.ok) me = await r.json();
      else { token = null; me = null; localStorage.removeItem("aijiaban_token"); }
    } catch (e) { token = null; me = null; }
  }
  if (token && me) {
    $("#authMask").hidden = true;
    renderUserBox();
    await refresh();
  } else {
    $("#authMask").hidden = false;
  }
  try {
    const h = await (await fetch("/api/health")).json();
    $("#llmBadge").textContent = h.llm
      ? "AI 引擎：已接入大模型" : "AI 引擎：规则兜底（未配置 LLM key）";
  } catch (e) {}
}

async function refresh() {
  const r = await api("/api/family");
  if (!r.ok) return;
  const d = await r.json();
  state = { data: d.data, snapshot: d.snapshot, problems: d.problems };
  render();
}

function render() {
  if (activeTab === "overview") renderOverview();
  else if (activeTab === "goals") renderGoals();
  else renderTable(activeTab);
}

// ===== Tab 切换 =====
$("#tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  activeTab = btn.dataset.tab;
  $("#pane-" + activeTab).classList.add("active");
  render();
});

// ===== 总览 =====
function renderOverview() {
  const s = state.snapshot, sm = s.safety_margin || {};
  const m = (v) => (v == null ? "—" : Number(v).toLocaleString("zh-CN"));
  $("#pane-overview").innerHTML = `
    <div class="metrics">
      <div class="metric"><label>总资产</label><b>${m(s.total_assets)}</b></div>
      <div class="metric"><label>总负债</label><b>${m(s.total_liabilities)}</b></div>
      <div class="metric hl"><label>净资产</label><b>${m(s.net_worth)}</b></div>
      <div class="metric"><label>月收入</label><b>${m(s.monthly_income)}</b></div>
      <div class="metric"><label>月支出</label><b>${m(s.monthly_expense)}</b></div>
      <div class="metric"><label>月结余</label><b>${m(s.monthly_surplus)}</b></div>
      <div class="metric"><label>安全边际</label><b>${sm.score != null ? sm.score + " 分 · " + sm.level : "—"}</b></div>
      <div class="metric"><label>应急月数</label><b>${s.emergency_months != null ? s.emergency_months + " 个月" : "—"}</b></div>
    </div>
    <h3>💎 资产配置</h3>
    <div class="donut-wrap" id="assetDonut"></div>
    <h3>⚠️ 最值得关注的 3 个问题</h3>
    <div class="problems" id="problems"></div>`;
  renderAssetDonut(state.data.assets);
  renderProblems(state.problems);
}

const ASSET_COLORS = { "房产": "#D97706", "存款": "#059669", "基金": "#E0A458", "股票": "#C2410C",
  "理财": "#7C5CBF", "保险现金价值": "#0E9AA7", "其他": "#A89B8C" };

function renderAssetDonut(assets) {
  const el = $("#assetDonut");
  const groups = {};
  let total = 0;
  for (const a of assets) {
    const t = a.type || "其他";
    groups[t] = (groups[t] || 0) + (a.value || 0);
    total += a.value || 0;
  }
  if (total <= 0) {
    el.innerHTML = `<div class="empty">还没有资产数据，去「资产」页添加，或在对话里说「存款50万」</div>`;
    return;
  }
  let acc = 0;
  const segs = [], legend = [];
  const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]);
  for (const [t, v] of sorted) {
    const start = (acc / total) * 360;
    acc += v;
    const end = (acc / total) * 360;
    segs.push(`${ASSET_COLORS[t] || "#9ca3af"} ${start}deg ${end}deg`);
    legend.push(`<div class="lg-row"><span class="lg-dot" style="background:${ASSET_COLORS[t] || "#9ca3af"}"></span>
      <span>${escapeHtml(t)}</span><b>${Math.round((v / total) * 100)}%</b></div>`);
  }
  el.innerHTML = `
    <div class="donut" style="background: conic-gradient(${segs.join(", ")})">
      <div class="donut-hole"><b>${fmtMoney(total)}</b><span>总资产</span></div>
    </div>
    <div class="legend">${legend.join("")}</div>`;
}

function renderProblems(problems) {
  const el = $("#problems");
  if (!problems || !problems.length) {
    el.innerHTML = `<div class="empty">还没有足够数据，先聊几句吧</div>`;
    return;
  }
  el.innerHTML = problems.map((p) => `
    <div class="item"><b>${escapeHtml(p.title)}</b><br/>${escapeHtml(p.why)}
      <div class="advice">建议：${escapeHtml(p.advice)}</div></div>`).join("");
}

// ===== 表格类实体 =====
function renderTable(entityKey) {
  const el = $("#pane-" + entityKey);
  const meta = ENTITY_META[entityKey];
  let rows = state.data[meta.api + "s"] || [];
  if (entityKey === "cashflow") {
    rows = [...rows].sort((a, b) => (a.flow_type === b.flow_type ? 0 : a.flow_type === "income" ? -1 : 1));
  }
  const head = `<div class="panel-head"><span>${meta.icon} ${meta.label}<em>(${rows.length})</em></span>
    <button class="btn-add" data-add="${entityKey}">+ 新增</button></div>`;
  if (!rows.length) {
    el.innerHTML = head + `<div class="empty">还没有${meta.label}记录，点「+ 新增」手动录入，或在左边对话里说一句</div>`;
    return;
  }
  const th = meta.columns.map((c) => `<th>${c.label}</th>`).join("") + '<th class="th-op"></th>';
  const body = rows.map((row) => {
    const tds = meta.columns.map((c) => {
      let v = row[c.key];
      if (c.money) v = fmtMoney(v);
      else if (c.map) v = c.map(v, row);
      else v = v == null ? "—" : escapeHtml(v);
      return `<td>${v}</td>`;
    }).join("");
    return `<tr>${tds}<td class="td-op">
      <button class="op" data-edit="${entityKey}" data-id="${row.id}">编辑</button>
      <button class="op del" data-del="${entityKey}" data-id="${row.id}">删除</button></td></tr>`;
  }).join("");
  el.innerHTML = head + `<table class="tbl"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>`;
}

// ===== 目标（进度卡片） =====
function renderGoals() {
  const el = $("#pane-goals");
  const goals = state.snapshot.goals || [];
  const head = `<div class="panel-head"><span>🎯 目标<em>(${goals.length})</em></span>
    <button class="btn-add" data-add="goals">+ 新增</button></div>`;
  if (!goals.length) {
    el.innerHTML = head + `<div class="empty">还没有目标，点「+ 新增」手动录入，或在对话里说「给孩子准备教育金，目标100万，2035年」</div>`;
    return;
  }
  el.innerHTML = head + goals.map((g) => {
    const pct = Math.max(0, Math.min(100, Math.round((g.progress || 0) * 100)));
    const need = g.monthly_needed != null ? `每月需存 ${fmtMoney(g.monthly_needed)}` : "未设期限";
    const deadline = g.months_remaining != null ? ` · 剩 ${g.months_remaining} 个月` : "";
    return `<div class="goal">
      <div class="goal-top"><span>${escapeHtml(g.name)}</span>
        <span class="goal-ops">
          <button class="op" data-edit="goals" data-id="${g.goal_id}">编辑</button>
          <button class="op del" data-del="goals" data-id="${g.goal_id}">删除</button>
        </span></div>
      <div class="goal-need">${need}</div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="goal-bottom">${fmtMoney(g.current_saved)} / ${fmtMoney(g.target_amount)} · 缺口 ${fmtMoney(g.gap)}${deadline}</div>
    </div>`;
  }).join("");
}

// ===== 弹窗（新增/编辑） =====
function openModal(entityKey, existing) {
  const meta = ENTITY_META[entityKey];
  modalCtx = { entityKey, id: existing ? existing.id : null };
  $("#modalTitle").textContent = (existing ? "编辑" : "新增") + meta.label;
  const existingCat = existing ? existing.category : "";
  $("#modalBody").innerHTML = meta.fields.map((f) => {
    const raw = existing ? (existing[f.key] ?? "") : "";
    const val = f.money ? fmtMoneyInput(raw) : raw;
    const req = f.required ? ' <span class="req">*</span>' : "";
    if (f.type === "select") {
      const opts = f.options.map((o) => {
        const ov = typeof o === "string" ? o : o.value;
        const ol = typeof o === "string" ? o : o.label;
        return `<option value="${escapeHtml(ov)}" ${String(ov) === String(val) ? "selected" : ""}>${escapeHtml(ol)}</option>`;
      }).join("");
      return `<label>${f.label}${req}<select data-field="${f.key}">${opts}</select></label>`;
    }
    const itype = f.type === "date" ? "date" : (f.number ? "number" : "text");
    return `<label>${f.label}${req}<input type="${itype}" data-field="${f.key}"
      placeholder="${escapeHtml(f.placeholder || "")}" value="${escapeHtml(val)}"></label>`;
  }).join("");

  // 现金流：切换收支时联动分类选项
  const ft = $("#modalBody").querySelector('[data-field="flow_type"]');
  const cat = $("#modalBody").querySelector('[data-field="category"]');
  if (ft && cat) {
    const updateCat = () => {
      const opts = ft.value === "expense" ? EXPENSE_CATS : INCOME_CATS;
      cat.innerHTML = opts.map((o) => `<option value="${o}" ${o === existingCat ? "selected" : ""}>${o}</option>`).join("");
    };
    ft.addEventListener("change", updateCat);
    updateCat();
  }
  $("#modalMask").hidden = false;
}

function closeModal() {
  $("#modalMask").hidden = true;
  modalCtx = null;
}

function collectForm() {
  const meta = ENTITY_META[modalCtx.entityKey];
  const out = {};
  for (const f of meta.fields) {
    const el = document.querySelector(`#modalBody [data-field="${f.key}"]`);
    if (!el) continue;
    let v = el.value.trim();
    if (f.money) {
      if (!v) { if (f.required) return alert(`请填写「${f.label}」`); out[f.key] = null; continue; }
      const parsed = parseMoney(v);
      if (parsed == null) return alert(`「${f.label}」金额格式不对，试试「50万」或「500000」`);
      out[f.key] = parsed;
    } else if (f.number) {
      if (!v) { out[f.key] = null; continue; }
      const n = Number(v);
      if (Number.isNaN(n)) return alert(`「${f.label}」需为数字`);
      out[f.key] = n;
    } else {
      if (f.required && !v) return alert(`请填写「${f.label}」`);
      out[f.key] = v;
    }
  }
  return out;
}

async function saveModal() {
  const payload = collectForm();
  if (!payload) return;
  const meta = ENTITY_META[modalCtx.entityKey];
  const { entityKey, id } = modalCtx;
  const url = id ? `/api/entity/${meta.api}/${id}` : `/api/family/entity/${meta.api}`;
  const method = id ? "PUT" : "POST";
  const r = await api(url, { method, body: JSON.stringify(payload) });
  if (!r.ok) { alert("保存失败：" + await r.text()); return; }
  closeModal();
  await refresh();
}

async function deleteEntity(entityKey, id) {
  const meta = ENTITY_META[entityKey];
  if (!confirm(`确定删除这条${meta.label}记录？`)) return;
  await api(`/api/entity/${meta.api}/${id}`, { method: "DELETE" });
  await refresh();
}

// ===== 看板事件委托 =====
$(".side-body").addEventListener("click", (e) => {
  const add = e.target.closest("[data-add]");
  if (add) { openModal(add.dataset.add, null); return; }
  const edit = e.target.closest("[data-edit]");
  if (edit) {
    const entityKey = edit.dataset.edit;
    const id = Number(edit.dataset.id);
    const meta = ENTITY_META[entityKey];
    const rawList = state.data[meta.api + "s"] || [];
    openModal(entityKey, rawList.find((x) => x.id === id));
    return;
  }
  const del = e.target.closest("[data-del]");
  if (del) deleteEntity(del.dataset.del, Number(del.dataset.id));
});

$("#modalSave").addEventListener("click", saveModal);
$("#modalCancel").addEventListener("click", closeModal);
$("#modalClose").addEventListener("click", closeModal);
$("#modalMask").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeModal(); });

// ===== 对话 =====
function addMsg(text, who) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.textContent = text;
  $("#chatBody").appendChild(div);
  $("#chatBody").scrollTop = $("#chatBody").scrollHeight;
}

function addConfirmCard(pendingId, items) {
  const div = document.createElement("div");
  div.className = "confirm-card";
  div.innerHTML = `
    <div>我理解到以下信息，确认后为你建档：</div>
    <ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
    <div class="confirm-actions">
      <button class="btn-ok" data-pid="${pendingId}" data-ok="1">确认</button>
      <button class="btn-no" data-pid="${pendingId}" data-ok="0">取消</button>
    </div>`;
  $("#chatBody").appendChild(div);
  $("#chatBody").scrollTop = $("#chatBody").scrollHeight;
}

async function send() {
  const text = $("#msgInput").value.trim();
  if (!text) return;
  $("#msgInput").value = "";
  addMsg(text, "user");
  try {
    const r = await api("/api/chat", {
      method: "POST", body: JSON.stringify({ message: text }),
    });
    const d = await r.json();
    if (d.type === "confirm") addConfirmCard(d.pending_id, d.items);
    else { addMsg(d.message, "bot"); await refresh(); }
  } catch (e) {
    addMsg("请求失败：" + e.message, "bot");
  }
}

async function confirm(pendingId, ok) {
  const r = await api("/api/confirm", {
    method: "POST", body: JSON.stringify({ pending_id: pendingId, confirmed: ok }),
  });
  const d = await r.json();
  addMsg(d.message, "bot");
  await refresh();
}

$("#sendBtn").addEventListener("click", send);
$("#msgInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
$("#chatBody").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-pid]");
  if (!btn) return;
  const pid = btn.dataset.pid;
  const ok = btn.dataset.ok === "1";
  confirm(pid, ok);
  btn.closest(".confirm-card").remove();
});

// ===== 深度报告 =====
function fmtMd(s) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

function renderAdvice(md) {
  const lines = String(md || "").split("\n");
  let html = "", inList = false;
  for (const line of lines) {
    if (line.startsWith("## ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h4>${fmtMd(line.slice(3).trim())}</h4>`;
    } else if (line.trim().startsWith("- ")) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${fmtMd(line.trim().slice(2))}</li>`;
    } else if (line.trim()) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p>${fmtMd(line.trim())}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
}

function renderReport(d) {
  const s = d.snapshot, sm = s.safety_margin || {};
  const m = (v) => (v == null ? "—" : Number(v).toLocaleString("zh-CN"));
  const members = d.members && d.members.length
    ? d.members.map((p) => `${p.name}${p.relation ? "（" + p.relation + "）" : ""}${p.age ? " · " + p.age + "岁" : ""}`).join("、")
    : "未录入";

  const alloc = (d.asset_allocation || []).map((a) => `
    <div class="lg-row"><span class="lg-dot" style="background:${ASSET_COLORS[a.type] || "#9ca3af"}"></span>
      <span>${escapeHtml(a.type)}</span><b>${fmtMoney(a.value)} · ${a.pct}%</b></div>`).join("");

  const goals = (s.goals || []).map((g) => {
    const pct = Math.max(0, Math.min(100, Math.round((g.progress || 0) * 100)));
    return `<div class="goal">
      <div class="goal-top"><span>${escapeHtml(g.name)}</span>
        <span class="goal-need">${g.monthly_needed != null ? "每月需存 " + fmtMoney(g.monthly_needed) : "未设期限"}</span></div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="goal-bottom">已存 ${fmtMoney(g.current_saved)} / 目标 ${fmtMoney(g.target_amount)} · 缺口 ${fmtMoney(g.gap)}</div>
    </div>`;
  }).join("");

  const problems = (d.problems || []).length
    ? d.problems.map((p, i) => `<div class="item"><b>${i + 1}. ${escapeHtml(p.title)}</b><br/>${escapeHtml(p.why)}<div class="advice">建议：${escapeHtml(p.advice)}</div></div>`).join("")
    : `<div class="empty">暂未发现明显风险</div>`;

  $("#reportTitle").textContent = `${d.family_name} · 家庭财富报告`;
  $("#reportBody").innerHTML = `
    <div class="rp-meta">生成日期：${d.generated_at}　|　成员：${escapeHtml(members)}</div>

    <h4>一、家庭概览</h4>
    <div class="metrics">
      <div class="metric"><label>总资产</label><b>${m(s.total_assets)}</b></div>
      <div class="metric"><label>总负债</label><b>${m(s.total_liabilities)}</b></div>
      <div class="metric hl"><label>净资产</label><b>${m(s.net_worth)}</b></div>
      <div class="metric"><label>月收入</label><b>${m(s.monthly_income)}</b></div>
      <div class="metric"><label>月支出</label><b>${m(s.monthly_expense)}</b></div>
      <div class="metric"><label>月结余</label><b>${m(s.monthly_surplus)}</b></div>
      <div class="metric"><label>安全边际</label><b>${sm.score != null ? sm.score + " 分 · " + sm.level : "—"}</b></div>
      <div class="metric"><label>应急月数</label><b>${s.emergency_months != null ? s.emergency_months + " 个月" : "—"}</b></div>
    </div>

    <h4>二、资产配置</h4>
    ${alloc ? `<div class="legend">${alloc}</div>` : `<div class="empty">暂无资产数据</div>`}

    <h4>三、健康体检</h4>
    ${problems}

    <h4>四、目标规划</h4>
    ${goals || `<div class="empty">暂无目标</div>`}

    <h4>五、综合建议</h4>
    <div class="rp-advice">${renderAdvice(d.advice)}</div>

    <div class="rp-disclaimer">本报告由 AI 自动生成，仅供参考，不构成任何投资、信贷、保险或法律建议。</div>`;

  $("#reportMask").hidden = false;
}

$("#reportBtn").addEventListener("click", async () => {
  if (!me || me.tier !== "vip") { showUpgrade(); return; }
  const btn = $("#reportBtn");
  btn.textContent = "生成中…";
  btn.disabled = true;
  try {
    const r = await api("/api/report");
    if (r.status === 403) { showUpgrade(); return; }
    const d = await r.json();
    renderReport(d);
  } catch (e) {
    alert("报告生成失败：" + e.message);
  } finally {
    btn.textContent = "📄 生成报告";
    btn.disabled = false;
  }
});
$("#reportPrint").addEventListener("click", () => window.print());
$("#reportClose").addEventListener("click", () => { $("#reportMask").hidden = true; });
$("#reportMask").addEventListener("click", (e) => { if (e.target === e.currentTarget) $("#reportMask").hidden = true; });

// ===== 决策模拟器 =====
const DECISION_SCENARIOS = {
  buy_house: {
    label: "买房",
    fields: [
      { key: "price", label: "房价(元)", money: true, required: true, placeholder: "如：300万" },
      { key: "down_payment_ratio", label: "首付比例(%)", number: true, percent: true, default: 30 },
      { key: "loan_rate", label: "贷款利率(年,%)", number: true, percent: true, default: 3.5 },
      { key: "loan_years", label: "贷款年限(年)", number: true, default: 30 },
      { key: "current_rent", label: "当前每月租金(元)", money: true, default: 0 },
      { key: "house_growth", label: "房产年增值率(%)", number: true, percent: true, default: 0 },
      { key: "horizon_years", label: "模拟年限(年)", number: true, default: 10 },
    ],
  },
  prepay: {
    label: "提前还贷",
    fields: [
      { key: "prepay_amount", label: "提前还款金额(元)", money: true, required: true, placeholder: "如：30万" },
      { key: "method", label: "还款方式", type: "select",
        options: [{ value: "shorten", label: "缩短年限（月供不变）" }, { value: "reduce_payment", label: "减少月供（年限不变）" }] },
    ],
  },
};

function renderDecisionForm() {
  const meta = DECISION_SCENARIOS[$("#decisionScenario").value];
  $("#decisionForm").innerHTML = meta.fields.map((f) => {
    const req = f.required ? ' <span class="req">*</span>' : "";
    if (f.type === "select") {
      const opts = f.options.map((o) => `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`).join("");
      return `<label>${f.label}${req}<select data-field="${f.key}">${opts}</select></label>`;
    }
    const itype = f.money ? "text" : "number";
    const dv = f.default != null ? `value="${f.default}"` : "";
    return `<label>${f.label}${req}<input type="${itype}" data-field="${f.key}" placeholder="${escapeHtml(f.placeholder || "")}" ${dv}></label>`;
  }).join("");
  $("#decisionResult").innerHTML = "";
}

function collectDecisionForm() {
  const meta = DECISION_SCENARIOS[$("#decisionScenario").value];
  const params = {};
  for (const f of meta.fields) {
    const el = document.querySelector(`#decisionForm [data-field="${f.key}"]`);
    let v = el.value.trim();
    if (f.money) {
      if (!v) { if (f.required) return alert(`请填写「${f.label}」`); params[f.key] = f.default || 0; continue; }
      const parsed = parseMoney(v);
      if (parsed == null) return alert(`「${f.label}」金额格式不对，试试「300万」或「3000000」`);
      params[f.key] = parsed;
    } else if (f.number) {
      const n = v === "" ? (f.default || 0) : Number(v);
      if (Number.isNaN(n)) return alert(`「${f.label}」需为数字`);
      params[f.key] = f.percent ? n / 100 : n;
    } else {
      params[f.key] = v;
    }
  }
  return params;
}

function renderDecisionResult(d) {
  const el = $("#decisionResult");
  if (d.error) {
    el.innerHTML = `<div class="decision-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  const summary = (d.summary || []).map((s) =>
    `<div class="metric"><label>${escapeHtml(s.label)}</label><b>${s.money ? fmtMoney(s.value) : escapeHtml(s.value)}</b></div>`).join("");
  const fmtVal = (v, r) => {
    if (v == null) return "—";
    if (r.money) return fmtMoney(v);
    if (r.months) return v + " 个月";
    return Number(v).toLocaleString("zh-CN");
  };
  const rows = (d.rows || []).map((r) => {
    const cls = r.highlight ? ' class="hl-row"' : "";
    return `<tr${cls}><td>${escapeHtml(r.label)}</td><td>${fmtVal(r.a, r)}</td><td>${fmtVal(r.b, r)}</td></tr>`;
  }).join("");
  el.innerHTML = `
    ${summary ? `<div class="metrics">${summary}</div>` : ""}
    <table class="tbl"><thead><tr><th>指标</th><th>方案A · ${escapeHtml(d.plan_a_label)}</th><th>方案B · ${escapeHtml(d.plan_b_label)}</th></tr></thead>
      <tbody>${rows}</tbody></table>
    <div class="decision-conclusion">💡 ${escapeHtml(d.conclusion)}</div>`;
}

$("#decisionBtn").addEventListener("click", () => {
  if (!me || me.tier !== "vip") { showUpgrade(); return; }
  $("#decisionMask").hidden = false;
  renderDecisionForm();
});
$("#decisionScenario").addEventListener("change", renderDecisionForm);
$("#decisionClose").addEventListener("click", () => { $("#decisionMask").hidden = true; });
$("#decisionRun").addEventListener("click", async () => {
  const params = collectDecisionForm();
  if (!params) return;
  const r = await api("/api/decision", {
    method: "POST", body: JSON.stringify({ scenario: $("#decisionScenario").value, params }),
  });
  if (r.status === 403) { showUpgrade(); $("#decisionMask").hidden = true; return; }
  const d = await r.json();
  renderDecisionResult(d);
});

// ===== 登录 / 注册 / 升级 =====
function renderUserBox() {
  const tierTag = me.tier === "vip"
    ? '<span class="tag-vip">VIP</span>'
    : '<span class="tag-free">免费</span>';
  let html = `<span class="user-name">👤 ${escapeHtml(me.username)}</span>${tierTag}`;
  if (me.tier !== "vip") html += `<button class="op-upgrade" id="topUpgrade">升级VIP</button>`;
  html += `<button class="op-logout" id="logoutBtn">退出</button>`;
  $("#userBox").innerHTML = html;
  const up = $("#topUpgrade");
  if (up) up.addEventListener("click", showUpgrade);
  $("#logoutBtn").addEventListener("click", () => {
    token = null; me = null;
    localStorage.removeItem("aijiaban_token");
    location.reload();
  });
}

function showUpgrade() {
  $("#upgradeMask").hidden = false;
}

async function doAuth() {
  const username = $("#authUser").value.trim();
  const password = $("#authPass").value;
  const err = $("#authError");
  err.hidden = true;
  if (!username || !password) { err.textContent = "请填写用户名和密码"; err.hidden = false; return; }
  const path = authMode === "login" ? "/api/login" : "/api/register";
  try {
    const r = await api(path, { method: "POST", body: JSON.stringify({ username, password }) });
    const d = await r.json();
    if (!r.ok) { err.textContent = d.detail || "操作失败"; err.hidden = false; return; }
    token = d.token;
    localStorage.setItem("aijiaban_token", token);
    me = { username: d.username, tier: d.tier };
    $("#authMask").hidden = true;
    renderUserBox();
    await refresh();
  } catch (e) {
    err.textContent = "网络错误：" + e.message; err.hidden = false;
  }
}

$("#authSubmit").addEventListener("click", doAuth);
$("#authPass").addEventListener("keydown", (e) => { if (e.key === "Enter") doAuth(); });
$("#authToggle").addEventListener("click", () => {
  authMode = authMode === "login" ? "register" : "login";
  $("#authSubmit").textContent = authMode === "login" ? "登 录" : "注 册";
  $("#authSub").textContent = authMode === "login" ? "登录后开始管理你的家庭财富" : "注册即免费体验 AI 家庭财富管理";
  $("#authToggle").textContent = authMode === "login" ? "免费注册" : "已有账号，去登录";
  $("#authError").hidden = true;
});

$("#upgradeOk").addEventListener("click", async () => {
  const r = await api("/api/upgrade", { method: "POST" });
  if (r.ok) {
    me.tier = "vip";
    renderUserBox();
    $("#upgradeMask").hidden = true;
    alert("已开通 VIP，深度报告和决策模拟已解锁 🎉");
  } else {
    alert("开通失败，请稍后再试");
  }
});
$("#upgradeCancel").addEventListener("click", () => { $("#upgradeMask").hidden = true; });
$("#upgradeClose").addEventListener("click", () => { $("#upgradeMask").hidden = true; });

init();
