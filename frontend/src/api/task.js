import request from '@/utils/request'

// 当前登录的一线或后勤人员只能查询分配给自己的任务。
export function getTasks(params) {
  return request({
    url: '/tasks',
    method: 'get',
    params
  })
}

export function getTaskDetail(id) {
  return request({
    url: `/tasks/${id}`,
    method: 'get'
  })
}

export function startTask(id) {
  return request({
    url: `/tasks/${id}/start`,
    method: 'post'
  })
}

export function completeTask(id, data) {
  const formData = new FormData()
  formData.append('feedbackText', data.feedbackText)
  ;(data.images || []).forEach(file => formData.append('images', file))
  return request({
    url: `/tasks/${id}/complete`,
    method: 'post',
    data: formData
  })
}
