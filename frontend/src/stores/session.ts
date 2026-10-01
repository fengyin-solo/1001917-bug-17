import { defineStore } from 'pinia'

// 角色 code 与后端 X-Operator-Role 取值对齐：admin/manager 可登记，viewer 只读。
export const ROLES = [
  { code: 'manager', label: '值班管理员' },
  { code: 'viewer', label: '观察员' },
] as const
export type RoleCode = (typeof ROLES)[number]['code']

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    role: 'manager' as RoleCode,
    shiftLabel: '白班 08:00-20:00',
    scope: '风电场机组运维平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    canSubmit: (state) => state.role !== 'viewer',
    roleLabel: (state) => ROLES.find((item) => item.code === state.role)?.label ?? state.role,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(role: RoleCode) {
      this.role = role
      this.operator = role === 'viewer' ? '外单位观察员' : '值班管理员'
    },
  },
})
