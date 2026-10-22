// 一线执行模块接口封装
import request from '@/utils/request'

/**
 * 查询我的待办任务
 * GET /api/field/my-tasks
 * @param {Object} params 入参 { status, keyword }
 */
export function getMyTasks(params) {
  return request({
    url: '/field/my-tasks',
    method: 'get',
    params
  })
}

/**
 * 提交现场反馈
 * POST /api/field/feedback
 * @param {Object} data 入参 { taskId, content, images: File[] }（FormData 上传）
 */
export function submitFeedback(data) {
  return request({
    url: '/field/feedback',
    method: 'post',
    data
  })
}

/**
 * 查询我的历史任务（归档）
 * GET /api/field/task-history
 * @param {Object} params 入参 { page, size, keyword, date }
 */
export function getTaskHistory(params) {
  return request({
    url: '/field/task-history',
    method: 'get',
    params
  })
}

/**
 * 查询当前人员信息（个人中心）
 * GET /api/field/profile
 */
export function getFieldProfile() {
  return request({
    url: '/field/profile',
    method: 'get'
  })
}

/**
 * 提交状态变更申请
 * POST /api/field/status-applications
 * @param {Object} data 入参 { targetStatus, attachments }
 */
export function submitStatusApplication(data) {
  return request({
    url: '/field/status-applications',
    method: 'post',
    data
  })
}

/**
 * 查询我的状态申请记录
 * GET /api/field/status-applications
 * @param {Object} params 入参 { page, size }
 */
export function getMyStatusApplications(params) {
  return request({
    url: '/field/status-applications',
    method: 'get',
    params
  })
}