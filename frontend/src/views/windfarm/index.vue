<template>
  <section class="page" data-module="windfarm">
    <header class="page-head">
      <div>
        <h2>风电场站管理</h2>
        <p class="page-desc">维护风电场站，围绕场站编码、场站名称、所在区域、装机容量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记风电场站</button>
        <button class="btn" type="button" @click="exportRows">导出风电场站清单</button>
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
      <span v-else-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
    </footer>

    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记风电场站</h3>
        <label v-for="field in createFields" :key="field" class="modal-item">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <div v-if="errorMessage" class="error-text modal-error">{{ errorMessage }}</div>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '提交登记' }}</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const session = useSessionStore()
const ENDPOINT = '/api/windfarm'
const columns = ["场站编码", "场站名称", "所在区域", "装机容量", "并网日期", "运营单位", "海拔高度", "场站状态"]
const actions = ["并网投运", "申请限功率", "转入检修"]
const statuses = ["在建", "运行中", "限功率", "停运检修"]
const stats = [{"label": "在运场站", "value": 0}, {"label": "装机容量", "value": 0}, {"label": "限功率场站", "value": 0}]

// 前端筛选字段与后端查询参数一一对应：场站编码 -> keyword，所在区域 -> region
const filterFields = [
  { key: 'keyword', label: '场站编码' },
  { key: 'region', label: '所在区域' },
] as const
const createFields = ["场站编码", "场站名称", "所在区域"] as const

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', region: '' })

const createOpen = ref(false)
const submitting = ref(false)
const createForm = ref<Record<string, string>>({ 场站编码: '', 场站名称: '', 所在区域: '' })

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
  filters.value = { keyword: '', region: '' }
  void reload()
}

function openCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  createForm.value = { 场站编码: '', 场站名称: '', 所在区域: '' }
  createOpen.value = true
}

function closeCreate() {
  createOpen.value = false
}

async function readDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    return payload.detail || payload.message || ''
  } catch {
    return ''
  }
}

async function exportRows() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/export${buildQuery()}`)
    if (!response.ok) {
      const detail = await readDetail(response)
      throw new Error(detail || '风电场站清单导出失败')
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
  }
}

async function submitCreate() {
  errorMessage.value = ''
  submitting.value = true
  try {
    const values: Record<string, string> = {}
    for (const field of createFields) {
      values[field] = createForm.value[field].trim()
    }
    const response = await request(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Operator-Role': session.role },
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json()) as { ok?: boolean; detail?: string; message?: string }
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || '风电场站登记失败')
    }
    if (!payload.ok) {
      throw new Error(payload.message || '风电场站登记失败')
    }
    closeCreate()
    noticeMessage.value = payload.message || '风电场站已登记'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电场站登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Operator-Role': session.role },
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok?: boolean; detail?: string; message?: string }
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || '风电场站动作未生效，请稍后重试')
    }
    if (!payload.ok) {
      throw new Error(payload.message || '风电场站动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电场站操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      const detail = await readDetail(response)
      throw new Error(detail || '风电场站列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电场站列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.notice-text {
  color: #067647;
}
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
  width: 360px;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modal-title {
  margin: 0;
  font-size: 16px;
}
.modal-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.modal-item input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.modal-error {
  font-size: 12px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>
