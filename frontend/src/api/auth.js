// 认证模块接口封装
// 统一使用 src/utils/request.js 的 axios 实例（baseURL = /api）
import request from '@/utils/request'

/**
 * 用户登录
 * POST /api/auth/login
 * @param {Object} data 入参 { username, password }
 * @returns {Promise<{ code, message, data: { token, userInfo } }>}
 */
export function loginApi(data) {
  return request({
    url: '/auth/login',
    method: 'post',
    data
  })
}

/**
 * 获取登录身份列表
 * GET /api/auth/roles
 * 登录页下拉框身份数据由后端动态提供，不再写死在前端
 * @returns {Promise<{ code, message, data: Array<{ id, roleKey, roleName, defaultPath }> }>}
 */
export function getRolesApi() {
  return request({
    url: '/auth/roles',
    method: 'get'
  })
}

/**
 * 退出登录
 * POST /api/auth/logout
 * @returns {Promise<{ code, message }>}
 */
export function logoutApi() {
  return request({
    url: '/auth/logout',
    method: 'post'
  })
}

/**
 * 修改当前登录账号密码。
 * POST /api/auth/change-password
 */
export function changePasswordApi(data) {
  return request({
    url: '/auth/change-password',
    method: 'post',
    data
  })
}

/** 查询当前登录账号的真实岗位、车站及在岗状态。 */
export function getProfileApi() {
  return request({ url: '/auth/profile', method: 'get' })
}
