<template>
  <section class="page" data-module="windfarm">
    <header class="page-head">
      <div>
        <h2>风电场站管理</h2>
        <p class="page-desc">维护风电场站，围绕场站编码、场站名称、所在区域、装机容量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" :disabled="!store.canSubmit" @click="openCreate">
          登记风电场站
        </button>
        <button class="btn" type="button" :disabled="exporting" @click="exportRows">
          {{ exporting ? '导出中…' : '导出风电场站清单' }}
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无风电场站数据，可先登记风电场站</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条风电场站记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记风电场站</h3>
        <label v-for="field in requiredFields" :key="field" class="modal-field">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type Stat = { label: string; value: number }

const store = useSessionStore()

const ENDPOINT = '/api/windfarm'
const columns = ["场站编码", "场站名称", "所在区域", "装机容量", "并网日期", "运营单位", "海拔高度", "场站状态"]
const actions = ["并网投运", "申请限功率", "转入检修"]
const requiredFields = ["场站编码", "场站名称", "所在区域"]
// 后端查询参数用固定英文键，避免中文参数名在服务端被当成未知字段忽略。
const filterFields = [
  { key: 'code', label: '场站编码' },
  { key: 'name', label: '场站名称' },
  { key: 'region', label: '所在区域' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<Stat[]>([])
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const exporting = ref(false)

const createOpen = ref(false)
const submitting = ref(false)
const createError = ref('')
const createForm = reactive<Record<string, string>>({ 场站编码: '', 场站名称: '', 所在区域: '' })

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters.value[field.key]?.trim()
    if (value) {
      params.set(field.key, value)
    }
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  exporting.value = true
  try {
    // 走统一请求封装带上身份与基地址，并把当前筛选条件一并传给导出接口。
    const response = await request(`${ENDPOINT}/export${buildQuery()}`)
    if (!response.ok) {
      throw new Error(`导出失败（${response.status}），请稍后重试`)
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '风电场站清单.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电场站清单导出失败'
  } finally {
    exporting.value = false
  }
}

function openCreate() {
  if (!store.canSubmit) {
    errorMessage.value = '当前身份为观察员，无权登记风电场站'
    return
  }
  createError.value = ''
  createOpen.value = true
}

function closeCreate() {
  createOpen.value = false
  createError.value = ''
}

async function submitCreate() {
  createError.value = ''
  const values: Record<string, string> = {}
  for (const field of requiredFields) {
    values[field] = createForm[field].trim()
  }
  const missing = requiredFields.filter((field) => !values[field])
  if (missing.length) {
    createError.value = `请填写必填字段：${missing.join('、')}`
    return
  }
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Operator-Role': store.role },
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json().catch(() => null)) as
      | { ok?: boolean; message?: string; detail?: unknown }
      | null
    if (response.status === 403) {
      createError.value = typeof payload?.detail === 'string' ? payload.detail : '当前身份无权登记风电场站'
      return
    }
    if (!response.ok || !payload?.ok) {
      createError.value = payload?.message || '风电场站登记失败，请稍后重试'
      return
    }
    closeCreate()
    errorMessage.value = payload.message || '风电场站已登记'
    for (const field of requiredFields) {
      createForm[field] = ''
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '风电场站登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('风电场站动作未生效，请稍后重试')
    }
    await reload()
    await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电场站操作失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (response.ok) {
      const payload = (await response.json()) as { items?: Stat[] }
      stats.value = payload.items ?? []
    }
  } catch {
    // 统计卡不阻塞列表，保留上一次的值即可
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      throw new Error('风电场站列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电场站列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 380px;
  background: #fff;
  border-radius: 8px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modal-card h3 { margin: 0 0 4px; font-size: 16px; }
.modal-field span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.modal-field input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
