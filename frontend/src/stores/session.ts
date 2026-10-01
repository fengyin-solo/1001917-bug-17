import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    // 提交类接口用的角色令牌（ASCII，避免中文写进 HTTP 头被 latin-1 解成乱码）
    role: 'admin',
    roleLabel: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '风电场机组运维平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
  },
})
