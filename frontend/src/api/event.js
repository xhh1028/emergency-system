import request from '@/utils/request'

/**
 * 一线或后勤人员提交险情，data 必须为 FormData。
 * POST /api/events/report
 */
export function reportEvent(data) {
  return request({
    url: '/events/report',
    method: 'post',
    data
  })
}

/** 一线补全信息后重新提交被驳回的普通险情事件。POST /api/events/{id}/resubmit */
export function resubmitEvent(id, data) {
  return request({
    url: `/events/${id}/resubmit`,
    method: 'post',
    data
  })
}

/** 撤回自己发起、待处理状态的事件（逻辑删除）。POST /api/events/{id}/withdraw */
export function withdrawEvent(id) {
  return request({
    url: `/events/${id}/withdraw`,
    method: 'post'
  })
}

/** 查询当前登录人员上报的事件。GET /api/events/my-reports */
export function getMyReportedEvents(params) {
  return request({
    url: '/events/my-reports',
    method: 'get',
    params
  })
}

/** 查询当前登录人员已经完成的任务。GET /api/events/my-completed-tasks */
export function getMyCompletedTasks(params) {
  return request({
    url: '/events/my-completed-tasks',
    method: 'get',
    params
  })
}

// 以下接口由车站和调度模块继续使用，后续阶段再接入真实后端。
export function getEvents(params) {
  return request({ url: '/events', method: 'get', params })
}

export function getEventDetail(id) {
  return request({ url: `/events/${id}`, method: 'get' })
}

export function createEvent(data) {
  return request({ url: '/events', method: 'post', data })
}

export function updateEventStatus(id, data) {
  return request({ url: `/events/${id}/status`, method: 'put', data })
}
