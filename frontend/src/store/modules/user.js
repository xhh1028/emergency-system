import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getToken,
  setToken,
  removeToken,
  getUser,
  setUser,
  removeUser,
  setLoginAt,
  clearAuth
} from '@/utils/auth'
import { loginApi } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(getToken() || '')
  const userInfo = ref(getUser() || null)

  const isLoggedIn = computed(() => !!token.value)

  const role = computed(() => userInfo.value?.role || '')

  const roleLabel = computed(() => userInfo.value?.roleLabel || '')

  const nickname = computed(() => userInfo.value?.nickname || '未登录')

  // 子角色（后勤安保四类：security/medical/warehouse/cleaner）
  const subRole = computed(() => userInfo.value?.subRole || '')
  const subRoleLabel = computed(() => userInfo.value?.subRoleLabel || '')

  async function login(username, password) {
    // 调用 Spring Boot 登录接口，返回结构为 { code, message, data }。
    const response = await loginApi({ username, password })
    const { data } = response
    token.value = data.token
    userInfo.value = {
      id: data.userInfo.id,
      username: data.userInfo.username,
      nickname: data.userInfo.nickname,
      role: data.userInfo.role,
      roleLabel: data.userInfo.roleLabel,
      subRole: data.userInfo.subRole || '',
      subRoleLabel: data.userInfo.subRoleLabel || '',
      avatar: data.userInfo.avatar
    }
    setToken(data.token)
    setUser(userInfo.value)
    // 记录登录时间，用于"长时间未登录需重新登录、短时间重开免登录"的会话判断
    setLoginAt()
    return data
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    clearAuth()
  }

  function hasPermission(requiredRole) {
    if (!requiredRole) return true
    if (Array.isArray(requiredRole)) {
      return requiredRole.includes(role.value)
    }
    return role.value === requiredRole
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    role,
    roleLabel,
    nickname,
    subRole,
    subRoleLabel,
    login,
    logout,
    hasPermission
  }
})
