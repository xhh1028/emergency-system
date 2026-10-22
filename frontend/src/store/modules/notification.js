import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getToken } from '@/utils/auth'

export const useNotificationStore = defineStore('notification', () => {
  const messages = ref([])
  const intervalId = ref(null)
  const eventSource = ref(null)

  const unreadCount = computed(() => messages.value.filter(m => !m.read).length)

  const roleMessageTypes = {
    admin: ['新指令', '任务更新', '事件上报'],
    station: ['新指令', '任务更新', '事件上报'],
    field: ['任务更新', '任务分配'],
    support: ['任务更新', '物资调配']
  }

  function startPolling() {
    if (eventSource.value || !getToken()) return
    const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
    eventSource.value = new EventSource(`${apiBase}/notifications/stream?access_token=${encodeURIComponent(getToken())}`)
    eventSource.value.addEventListener('notification', event => {
      const message = JSON.parse(event.data)
      if (message.type === 'CONNECTED') return
      addMessage({ ...message, time: formatTime(message.time) })
      window.dispatchEvent(new CustomEvent('emergency-realtime', { detail: message }))
    })
  }

  function stopPolling() {
    if (intervalId.value) clearInterval(intervalId.value)
    intervalId.value = null
    eventSource.value?.close()
    eventSource.value = null
  }

  function markAsRead(messageId) {
    const msg = messages.value.find(m => m.id === messageId)
    if (msg) {
      msg.read = true
    }
  }

  function markAllAsRead() {
    messages.value.forEach(m => m.read = true)
  }

  function clearMessages() {
    messages.value = []
  }

  function addMessage(message) {
    messages.value.unshift({
      id: Date.now() + Math.random(),
      ...message,
      time: message.time || new Date().toLocaleString('zh-CN'),
      read: false
    })
  }

  function formatTime(value) {
    return value ? String(value).replace('T', ' ').slice(0, 19) : new Date().toLocaleString('zh-CN')
  }

  return {
    messages,
    unreadCount,
    roleMessageTypes,
    startPolling,
    stopPolling,
    markAsRead,
    markAllAsRead,
    clearMessages,
    addMessage
  }
})
