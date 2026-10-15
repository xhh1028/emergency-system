const TOKEN_KEY = 'metro_emergency_token'
const USER_KEY = 'metro_emergency_user'
// 登录时间戳：用于判断本地会话是否已过期（长时间未登录需要重新登录）
const LOGIN_AT_KEY = 'metro_emergency_login_at'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function getUser() {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function removeUser() {
  localStorage.removeItem(USER_KEY)
}

export function clearAuth() {
  removeToken()
  removeUser()
  removeLoginAt()
}

/** 记录登录成功的时间戳（毫秒），用于会话有效期判断 */
export function setLoginAt(time = Date.now()) {
  localStorage.setItem(LOGIN_AT_KEY, String(time))
}

/** 读取上次登录的时间戳，不存在或非法时返回 0 */
export function getLoginAt() {
  const raw = localStorage.getItem(LOGIN_AT_KEY)
  const time = Number(raw)
  return Number.isFinite(time) && time > 0 ? time : 0
}

export function removeLoginAt() {
  localStorage.removeItem(LOGIN_AT_KEY)
}

export const ROLE_MAP = {
  admin: { key: 'admin', label: '调度指挥', order: 1 },
  station: { key: 'station', label: '车站管理', order: 2 },
  field: { key: 'field', label: '一线执行', order: 3 },
  support: { key: 'support', label: '后勤安保', order: 4 }
}

export const ROLE_LIST = Object.values(ROLE_MAP)