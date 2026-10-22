import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useNotificationStore } from '@/store/modules/notification'

export const useEventStore = defineStore('event', () => {
  const events = ref([])

  const eventStatusFlow = ['reported', 'confirmed', 'planActivated', 'executing', 'closed']

  const statusLabelMap = {
    reported: '事件上报',
    confirmed: '调度确认',
    planActivated: '预案启动',
    executing: '执行中',
    closed: '已关闭'
  }

  const statusTagMap = {
    reported: 'warning',
    confirmed: 'primary',
    planActivated: 'info',
    executing: 'danger',
    closed: 'success'
  }

  const activeEvents = computed(() =>
    events.value.filter(e => e.status !== 'closed')
  )

  function addEvent(eventData) {
    const newEvent = {
      id: Date.now(),
      title: eventData.title,
      type: eventData.type,
      level: eventData.level || 'medium',
      station: eventData.station,
      line: eventData.line,
      description: eventData.description,
      images: eventData.images || [],
      status: 'reported',
      reportTime: new Date().toLocaleString('zh-CN'),
      timeline: [
        {
          status: 'reported',
          label: '事件上报',
          time: new Date().toLocaleString('zh-CN'),
          operator: eventData.reporter || '车站人员',
          description: '事件已上报，等待调度确认'
        }
      ],
      // 事后复盘材料列表（前端存储、演示用）：
      // 每项 { id, type, files, uploader, status('uploaded'|'received'), reviewBy, receivedAt, synced, createTime }
      postmortems: [],
      boundPlanId: null,
      boundPlanName: null
    }

    events.value.unshift(newEvent)

    const notificationStore = useNotificationStore()
    notificationStore.addMessage({
      type: '事件上报',
      title: '新事件上报',
      content: `${eventData.station || '某站'} 上报了 ${eventData.title}`
    })

    return newEvent
  }

  // 添加事后复盘材料（仅前端存储）
  function addPostmortem(eventId, postmortem) {
    const event = events.value.find(e => e.id === eventId)
    if (event) {
      const pm = {
        id: Date.now(),
        type: postmortem.type || '事故总结',
        files: postmortem.files || [],
        uploader: postmortem.uploader || '本站',
        status: 'uploaded', // uploaded -> received
        reviewBy: null,
        receivedAt: null,
        synced: false,
        createTime: new Date().toLocaleString('zh-CN')
      }
      event.postmortems = event.postmortems || []
      event.postmortems.push(pm)
      event.timeline.push({
        status: 'postmortem_uploaded',
        label: '上传事后复盘材料',
        time: new Date().toLocaleString('zh-CN'),
        operator: pm.uploader,
        description: `上传 ${pm.type}`
      })
      return pm
    }
    return null
  }

  // 站内确认接收事后材料（改变状态，记录timeline）
  function confirmPostmortem(eventId, postmortemId, reviewer) {
    const event = events.value.find(e => e.id === eventId)
    if (event && event.postmortems) {
      const pm = event.postmortems.find(p => p.id === postmortemId)
      if (pm) {
        pm.status = 'received'
        pm.reviewBy = reviewer || '站管理'
        pm.receivedAt = new Date().toLocaleString('zh-CN')
        event.timeline.push({
          status: 'postmortem_received',
          label: '确认接收',
          time: pm.receivedAt,
          operator: pm.reviewBy,
          description: `确认接收 ${pm.type}`
        })
        return pm
      }
    }
    return null
  }

  // 同步事后材料到调度中心（前端标记为已同步，演示用）
  function syncPostmortem(eventId, postmortemId, operator) {
    const event = events.value.find(e => e.id === eventId)
    if (event && event.postmortems) {
      const pm = event.postmortems.find(p => p.id === postmortemId)
      if (pm && pm.status === 'received') {
        pm.synced = true
        event.timeline.push({
          status: 'postmortem_synced',
          label: '同步归档',
          time: new Date().toLocaleString('zh-CN'),
          operator: operator || '站管理',
          description: `已同步 ${pm.type} 到调度中心`
        })
        return pm
      }
    }
    return null
  }

  function updateEventStatus(eventId, newStatus, operator, description) {
    const event = events.value.find(e => e.id === eventId)
    if (event) {
      event.status = newStatus
      event.timeline.push({
        status: newStatus,
        label: statusLabelMap[newStatus],
        time: new Date().toLocaleString('zh-CN'),
        operator: operator || '系统',
        description: description || ''
      })
    }
    return event
  }

  function bindPlan(eventId, planId, planName) {
    const event = events.value.find(e => e.id === eventId)
    if (event) {
      event.boundPlanId = planId
      event.boundPlanName = planName
      updateEventStatus(eventId, 'planActivated', '调度员', `已启动预案：${planName}`)
    }
    return event
  }

  function getEventById(eventId) {
    return events.value.find(e => e.id === eventId)
  }

  return {
    events,
    eventStatusFlow,
    statusLabelMap,
    statusTagMap,
    activeEvents,
    addEvent,
    updateEventStatus,
    bindPlan,
    getEventById
  }
})
