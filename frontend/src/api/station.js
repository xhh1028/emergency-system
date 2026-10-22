// 车站模块接口封装（含指令接收、人员管理、故障、态势）
import request from '@/utils/request'

/** 查询当前管理员所属车站的事件待办。 */
export function getStationEvents(params) {
  return request({ url: '/station/events', method: 'get', params })
}

/** 查询本站事件详情及匹配预案。 */
export function getStationEventDetail(id) {
  return request({ url: `/station/events/${id}`, method: 'get' })
}

/** 确认 AI 研判或人工改判，并选择站内处置/上报调度。 */
export function decideStationEvent(id, data) {
  return request({ url: `/station/events/${id}/decision`, method: 'post', data })
}

/** 车站管理员驳回普通险情事件，退回一线补全信息（紧急险情禁止驳回）。 */
export function rejectStationEvent(id, data) {
  return request({ url: `/station/events/${id}/reject`, method: 'post', data })
}

/** 查询事件最新 AI 候选答案及其版本状态。 */
export function getLatestAnswerCandidate(eventId) {
  return request({ url: `/workflow/answers/event/${eventId}/latest`, method: 'get' })
}

/** 对候选答案执行独立校验。 */
export function validateAnswerCandidate(answerId) {
  return request({ url: `/workflow/answers/${answerId}/validate`, method: 'post' })
}

/** 接受、修改或驳回候选答案。 */
export function reviewAnswerCandidate(answerId, data) {
  return request({ url: `/workflow/answers/${answerId}/review`, method: 'post', data })
}

/** 查询本站可分派任务的一线与后勤人员。 */
export function getStationPersonnelOptions() {
  return request({ url: '/station/personnel/options', method: 'get' })
}

/** 为指定事件批量创建站内子任务。 */
export function createStationEventTasks(id, data) {
  return request({ url: `/station/events/${id}/tasks`, method: 'post', data })
}

/**
 * 查询车站列表
 * GET /api/stations
 * @param {Object} params 入参 { keyword, line }
 */
export function getStations(params) {
  return request({
    url: '/stations',
    method: 'get',
    params
  })
}

/**
 * 查询车站监控详情
 * GET /api/stations/:id/monitor
 * @param {Number|String} id 车站ID
 */
export function getStationMonitor(id) {
  return request({
    url: `/stations/${id}/monitor`,
    method: 'get'
  })
}

/**
 * 查询全站任务完成率（调度全站进度）
 * GET /api/stations/progress
 * @param {Object} params 入参 { line }
 */
export function getStationProgress(params) {
  return request({
    url: '/stations/progress',
    method: 'get',
    params
  })
}

/**
 * 查询本站态势（设备/客流/物资汇总）
 * GET /api/stations/:id/situation
 * @param {Number|String} id 车站ID
 */
/**
 * 接收站收到的调度指令列表
 * GET /api/station/commands
 * @param {Object} params 入参 { status: 'ALL'|'UNREAD'|'READ', keyword, page, size }
 */
export function getStationCommands(params) {
  return request({
    url: '/station/commands',
    method: 'get',
    params
  })
}

/** 查询调度指令详情。 */
export function getStationCommandDetail(id) {
  return request({ url: `/station/commands/${id}`, method: 'get' })
}

/**
 * 签收调度指令
 * POST /api/station/commands/:id/sign
 * @param {Number|String} id 指令ID
 */
export function signCommand(id) {
  return request({
    url: `/station/commands/${id}/sign`,
    method: 'post'
  })
}

/**
 * 查询人员台账列表
 * GET /api/personnel
 * @param {Object} params 入参 { keyword, position, status }
 */
export function getPersonnel(params) {
  return request({
    url: '/station/personnel/options',
    method: 'get',
    params
  })
}

/** 查询一线执行和后勤安保的真实岗位字典。 */
export function getPersonnelPosts() {
  return request({ url: '/station/personnel/posts', method: 'get' })
}

/**
 * 新增人员
 * POST /api/personnel
 * @param {Object} data 入参 { username, name, position, area, status, phone, canBeLeader }
 */
export function createPersonnel(data) {
  return request({
    url: '/station/personnel',
    method: 'post',
    data
  })
}

/**
 * 编辑人员
 * PUT /api/personnel/:id
 * @param {Number|String} id 人员ID
 * @param {Object} data 入参 { username, name, position, area, status, phone, canBeLeader }
 */
export function updatePersonnel(id, data) {
  return request({
    url: `/station/personnel/${id}`,
    method: 'put',
    data
  })
}


/** 车站管理员为本站工作人员设置新密码。 */
export function resetPersonnelPassword(id, data) {
  return request({
    url: `/station/personnel/${id}/reset-password`,
    method: 'post',
    data
  })
}

/**
 * 查询设备台账
 * GET /api/devices
 * @param {Object} params 入参 { station }
 */
export function getDevices(params) {
  return request({
    url: '/devices',
    method: 'get',
    params
  })
}

/**
 * 查询故障上报列表
 * GET /api/faults
 * @param {Object} params 入参 { status: 'open'|'resolved' }
 */
export function getFaults(params) {
  return request({
    url: '/faults',
    method: 'get',
    params
  })
}

/**
 * 故障上报
 * POST /api/faults
 * @param {Object} data 入参 { deviceId, description, reporter }
 */
export function reportFault(data) {
  return request({
    url: '/faults',
    method: 'post',
    data
  })
}

/** 查询本站真实任务进度。 */
export function getStationTaskProgress(params) {
  return request({ url: '/station/tasks/progress', method: 'get', params })
}

/** 查询本站各顶层事件的子任务总进度（进度监控页顶部事件级进度条）。 */
export function getStationEventProgress() {
  return request({ url: '/station/tasks/progress/events', method: 'get' })
}


/** 查询任务详情和一线现场反馈报告。 */
export function getStationTaskDetail(id) {
  return request({ url: `/station/tasks/${id}`, method: 'get' })
}
