// 视图：家庭数据（Phase 6A 可编辑闭环）：成员/收入/支出/资产/负债/目标 的查看·新增·编辑·删除。
// 铁律：本页 100% 复用后端既有 entity CRUD（/api/family/entity/{table}、/api/entity/{table}/{id}），
//       零财富计算、零新增后端逻辑；写操作后仅做缓存失效，让 overview/goals/issues 下次访问时重取。
// 注意：收入/支出共用 cashflow 表，靠 flow_type 区分；本页不新增任何字段，只透传白名单列。
import { store, loadFamily, createEntity, updateEntity, deleteEntity } from '../store.js';
import { fmtMoney } from '../format.js';

const { reactive, computed, onMounted } = Vue;

// 6 个逻辑分区：income/expense 共用 cashflow 表，靠 flowType 固定写入。
const SECTIONS = [
  {
    key: 'person', label: '成员', table: 'person',
    fields: [
      { key: 'name', label: '姓名', type: 'text', required: true },
      { key: 'relation', label: '关系', type: 'select', options: ['本人', '配偶', '子女', '老人', '其他'] },
      { key: 'birth_year', label: '出生年份', type: 'number' },
      { key: 'job', label: '职业', type: 'text' },
    ],
    columns: [
      { key: 'name', label: '姓名' },
      { key: 'relation', label: '关系' },
      { key: 'birth_year', label: '出生年' },
      { key: 'job', label: '职业' },
    ],
  },
  {
    key: 'income', label: '收入', table: 'cashflow', flowType: 'income',
    fields: [
      { key: 'category', label: '收入来源', type: 'text', def: '工资' },
      { key: 'amount', label: '金额（元）', type: 'number', required: true },
      { key: 'period', label: '周期', type: 'select', options: ['月', '年'], def: '月' },
    ],
    columns: [
      { key: 'category', label: '来源' },
      { key: 'amount', label: '金额', money: true },
      { key: 'period', label: '周期' },
    ],
  },
  {
    key: 'expense', label: '支出', table: 'cashflow', flowType: 'expense',
    fields: [
      { key: 'category', label: '支出类别', type: 'text', def: '其他' },
      { key: 'amount', label: '金额（元）', type: 'number', required: true },
      { key: 'period', label: '周期', type: 'select', options: ['月', '年'], def: '月' },
    ],
    columns: [
      { key: 'category', label: '类别' },
      { key: 'amount', label: '金额', money: true },
      { key: 'period', label: '周期' },
    ],
  },
  {
    key: 'asset', label: '资产', table: 'asset',
    fields: [
      { key: 'type', label: '资产类型', type: 'select', options: ['房产', '存款', '基金', '股票', '理财', '保险现金价值', '其他'], def: '其他' },
      { key: 'name', label: '资产名称', type: 'text' },
      { key: 'value', label: '金额（元）', type: 'number', required: true },
    ],
    columns: [
      { key: 'type', label: '类型' },
      { key: 'name', label: '名称' },
      { key: 'value', label: '金额', money: true },
    ],
  },
  {
    key: 'liability', label: '负债', table: 'liability',
    fields: [
      { key: 'type', label: '负债类型', type: 'select', options: ['房贷', '车贷', '消费贷', '信用卡', '其他'], def: '房贷' },
      { key: 'name', label: '名称', type: 'text' },
      { key: 'principal', label: '剩余本金（元）', type: 'number', required: true },
      { key: 'monthly_payment', label: '月供（元）', type: 'number' },
      { key: 'interest_rate', label: '年利率（%）', type: 'number' },
      { key: 'remaining_months', label: '剩余月数', type: 'number' },
    ],
    columns: [
      { key: 'type', label: '类型' },
      { key: 'name', label: '名称' },
      { key: 'principal', label: '本金', money: true },
      { key: 'monthly_payment', label: '月供', money: true },
      { key: 'interest_rate', label: '利率', pct: true },
      { key: 'remaining_months', label: '剩余月' },
    ],
  },
  {
    key: 'goal', label: '目标', table: 'goal',
    fields: [
      { key: 'type', label: '目标类型', type: 'select', options: ['教育', '养老', '买房', '创业', '其他'], def: '教育' },
      { key: 'name', label: '目标名称', type: 'text', required: true },
      { key: 'target_amount', label: '目标金额（元）', type: 'number' },
      { key: 'target_date', label: '目标日期', type: 'text' },
      { key: 'current_saved', label: '已备资金（元）', type: 'number' },
      { key: 'monthly_contribution', label: '每月定投（元）', type: 'number' },
    ],
    columns: [
      { key: 'type', label: '类型' },
      { key: 'name', label: '名称' },
      { key: 'target_amount', label: '目标金额', money: true },
      { key: 'target_date', label: '目标日期' },
      { key: 'current_saved', label: '已备', money: true },
      { key: 'monthly_contribution', label: '每月定投', money: true },
    ],
  },
];

const SECTIONS_BY_KEY = Object.fromEntries(SECTIONS.map((s) => [s.key, s]));

function sectionRows(section, data) {
  if (!data) return [];
  if (section.key === 'income' || section.key === 'expense')
    return (data.cashflows || []).filter((c) => c.flow_type === section.flowType);
  const map = { person: 'persons', asset: 'assets', liability: 'liabilities', goal: 'goals' };
  return data[map[section.key]] || [];
}

function fmtCell(col, v) {
  if (v == null || v === '') return '—';
  if (col.money) return fmtMoney(v);
  if (col.pct) return Number(v).toFixed(2) + '%';
  return v;
}

export const DataView = {
  setup() {
    const st = reactive({
      section: 'person',
      editing: null,     // { mode: 'create' } 或 { mode: 'edit', id }
      form: {},          // 当前弹窗字段值
      saving: false,
      error: null,
    });

    onMounted(() => { loadFamily().catch(() => {}); });

    const active = computed(() => SECTIONS_BY_KEY[st.section]);
    const rows = computed(() => sectionRows(active.value, store.family.data));

    function defaultForm(section) {
      const p = {};
      for (const f of section.fields) p[f.key] = f.def != null ? f.def : '';
      return p;
    }

    function openCreate() {
      st.form = defaultForm(active.value);
      st.editing = { mode: 'create' };
      st.error = null;
    }
    function openEdit(row) {
      const p = {};
      for (const f of active.value.fields) p[f.key] = row[f.key] != null ? row[f.key] : '';
      st.form = p;
      st.editing = { mode: 'edit', id: row.id };
      st.error = null;
    }
    function closeModal() { st.editing = null; st.error = null; }

    function buildPayload() {
      const sec = active.value;
      const payload = {};
      for (const f of sec.fields) {
        let v = st.form[f.key];
        if (v === '' || v == null) { payload[f.key] = null; continue; }
        if (f.type === 'number') v = Number(v);
        payload[f.key] = v;
      }
      if (sec.flowType) payload.flow_type = sec.flowType;
      return payload;
    }

    function validate() {
      for (const f of active.value.fields) {
        if (f.required) {
          const v = st.form[f.key];
          if (v === '' || v == null) return `「${f.label}」为必填项`;
        }
      }
      return null;
    }

    async function save() {
      const msg = validate();
      if (msg) { st.error = msg; return; }
      st.saving = true; st.error = null;
      try {
        const payload = buildPayload();
        if (st.editing.mode === 'edit') await updateEntity(active.value.table, st.editing.id, payload);
        else await createEntity(active.value.table, payload);
        await loadFamily();
        st.editing = null;
      } catch (e) {
        st.error = e.message || '保存失败';
      } finally {
        st.saving = false;
      }
    }

    async function remove(row) {
      const label = row.name || row.category || row.type || ('记录 #' + row.id);
      if (!confirm(`确认删除「${label}」？此操作不可撤销，财富评分将按新数据重算。`)) return;
      st.error = null;
      try {
        await deleteEntity(active.value.table, row.id);
        await loadFamily();
      } catch (e) {
        st.error = e.message || '删除失败';
      }
    }

    return {
      store, st, SECTIONS, active, rows, fmtCell,
      openCreate, openEdit, closeModal, save, remove,
    };
  },
  template: `
  <div class="view">
    <p class="lead">在这里直接增删改家庭基础数据。每次保存 / 删除后，财富评分、目标、风险问题会自动按新数据重新计算（本页只读写数据，不做任何财富计算）。</p>

    <div class="tabs">
      <button v-for="s in SECTIONS" :key="s.key" class="tab"
              :class="{ active: st.section === s.key }" @click="st.section = s.key">
        {{ s.label }}
      </button>
    </div>

    <div v-if="store.family.loading" class="state-hint">加载中…</div>
    <div v-else-if="store.family.error" class="state-hint error">{{ store.family.error }}</div>

    <template v-else>
      <div class="data-toolbar">
        <span class="data-count">共 {{ rows.length }} 条</span>
        <button class="btn-primary btn-sm" @click="openCreate">＋ 新增{{ active.label }}</button>
      </div>

      <div v-if="st.error" class="err-box"><span>{{ st.error }}</span></div>

      <div v-if="!rows.length" class="panel">
        <div class="empty-hint">暂无{{ active.label }}数据。点右上角「新增」手动录入，或在「AI 顾问」里对话建档。</div>
      </div>

      <div v-else class="panel data-panel">
        <table class="cmp-table data-table">
          <thead>
            <tr>
              <th v-for="c in active.columns" :key="c.key">{{ c.label }}</th>
              <th class="ops">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td v-for="c in active.columns" :key="c.key" :class="{ num: c.money || c.pct }">{{ fmtCell(c, row[c.key]) }}</td>
              <td class="ops">
                <button class="btn-mini" @click="openEdit(row)">编辑</button>
                <button class="btn-mini danger" @click="remove(row)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 新增 / 编辑弹窗 -->
    <div v-if="st.editing" class="modal-mask" @click.self="closeModal">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">{{ st.editing.mode === 'edit' ? '编辑' : '新增' }}{{ active.label }}</div>
          <button class="modal-close" @click="closeModal">×</button>
        </div>
        <div class="modal-body">
          <div v-if="st.error" class="form-error">{{ st.error }}</div>
          <div class="modal-form">
            <label v-for="f in active.fields" :key="f.key" class="field">
              <span class="f-label">{{ f.label }}{{ f.required ? ' *' : '' }}</span>
              <input v-if="f.type === 'text'" v-model="st.form[f.key]" />
              <input v-else-if="f.type === 'number'" type="number" step="any" v-model.number="st.form[f.key]" />
              <select v-else-if="f.type === 'select'" v-model="st.form[f.key]">
                <option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
              </select>
            </label>
          </div>
          <div class="modal-actions">
            <button class="btn-ghost" @click="closeModal">取消</button>
            <button class="btn-primary" :disabled="st.saving" @click="save">{{ st.saving ? '保存中…' : '保存' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>`,
};
