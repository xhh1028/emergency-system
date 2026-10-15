// 调度指挥模块接口封装（含预案、指令下发、站点地理、看板）
import request from '@/utils/request'

/** 查询进入调度范围的真实事件。 */
export function getDispatchEvents(params) {
  return request({ url: '/dispatch/events', method: 'get', params })
}

/** 查询调度事件完整详情和历史指令。 */
export function getDispatchEventDetail(id) {
  return request({ url: `/dispatch/events/${id}`, method: 'get' })
}

/** 标记调度已阅读严重事件。 */
export function confirmDispatchEvent(id) {
  return request({ url: `/dispatch/events/${id}/confirm`, method: 'post' })
}

/** 为已确认的事件下发正式处置指令。 */
export function sendDispatchEventCommand(id, data) {
  return request({ url: `/dispatch/events/${id}/commands`, method: 'post', data })
}

/** 在全部任务闭环后关闭事件。 */
export function closeDispatchEvent(id, data = {}) {
  return request({ url: `/dispatch/events/${id}/close`, method: 'post', data })
}

/** 查询全网全部真实 task 工单。 */
export function getDispatchProgress(params) {
  return request({ url: '/dispatch/progress', method: 'get', params })
}

/** 查询全线车站筛选字典。 */
export function getDispatchStations() {
  return request({ url: '/dispatch/stations', method: 'get' })
}

/** 调度中心对已完成任务填写真实评价。 */
export function evaluateDispatchTask(id, evaluation) {
  return request({ url: `/dispatch/tasks/${id}/evaluation`, method: 'post', data: { evaluation } })
}

/**
 * 查询预案列表
 * GET /api/plans
 * @param {Object} params 入参 { type, level }
 */
export function getPlans(params) {
  return request({
    url: '/plans',
    method: 'get',
    params
  })
}

/**
 * 查询预案详情（含执行步骤）
 * GET /api/plans/:id
 * @param {Number|String} id 预案ID
 */
export function getPlanDetail(id) {
  return request({
    url: `/plans/${id}`,
    method: 'get'
  })
}

/**
 * 启动预案并绑定到事件
 * POST /api/plans/:id/activate
 * @param {Number|String} planId 预案ID
 * @param {Object} data 入参 { eventId }
 */
export function activatePlan(planId, data) {
  return request({
    url: `/plans/${planId}/activate`,
    method: 'post',
    data
  })
}

/**
 * 下发调度指令
 * POST /api/commands
 * @param {Object} data 入参 { content, priority, targetStation }
 */
export function sendCommand(data) {
  return request({
    url: '/commands',
    method: 'post',
    data
  })
}

/**
 * 查询指令下发历史
 * GET /api/commands
 * @param {Object} params 入参 { status }
 */
export function getCommands(params) {
  return request({
    url: '/commands',
    method: 'get',
    params
  })
}

/** 查询调度大屏统计、各站活跃险情和最新事件。 */
export function getDispatchOverview() {
  return request({ url: '/dispatch/overview', method: 'get' })
}

/** 查询已关闭事件归档。 */
export function getDispatchArchive(params) {
  return request({ url: '/dispatch/archive', method: 'get', params })
}

/** 查询已有归档年份。 */
export function getDispatchArchiveYears() {
  return request({ url: '/dispatch/archive/years', method: 'get' })
}

/**
 * 查询最新预警列表
 * GET /api/alerts/latest
 * @param {Object} params 入参 { limit }
 */
export function getLatestAlerts(params) {
  return request({
    url: '/alerts/latest',
    method: 'get',
    params
  })
}

/**
 * 查询地图站点坐标与告警状态
 * GET /api/stations/geo
 * @param {Object} params 入参 { line }
 */
export function getStationsGeo(params) {
  return request({
    url: '/stations/geo',
    method: 'get',
    params
  })
}

/**
 * AI 事件研判
 * POST /api/ai/analyze
 * @param {Object} data 入参 { eventId } 或 { title, type, level, description }
 */
export function analyzeEvent(data) {
  return request({
    url: '/ai/analyze',
    method: 'post',
    data
  })
}
