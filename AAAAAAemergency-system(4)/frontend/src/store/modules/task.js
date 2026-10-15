import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useNotificationStore } from '@/store/modules/notification'

export const useTaskStore = defineStore('task', () => {
  const tasks = ref([])
  const assignedTasks = ref([])

  const statusLabelMap = {
    pending: '待执行',
    in_progress: '进行中',
    completed: '已完成'
  }

  const statusTagMap = {
    pending: 'warning',
    in_progress: 'primary',
    completed: 'success'
  }

  const priorityLabelMap = {
    urgent: '紧急',
    high: '高',
    normal: '普通'
  }

  const priorityTagMap = {
    urgent: 'danger',
    high: 'warning',
    normal: ''
  }

  function assignTask(taskData) {
    const newTask = {
      id: Date.now(),
      title: taskData.title,
      type: taskData.type,
      priority: taskData.priority || 'normal',
      assignee: taskData.assignee,
      assigneeId: taskData.assigneeId,
      leaderName: taskData.leaderName || '',
      participants: taskData.participants || [],
      stationName: taskData.stationName || '',
      deadline: taskData.deadline,
      description: taskData.description || '',
      status: 'pending',
      progress: 0,
      createTime: new Date().toLocaleString('zh-CN'),
      startTime: null,
      completeTime: null,
      report: null
    }

    tasks.value.unshift(newTask)
    assignedTasks.value.unshift({ ...newTask })

    const notificationStore = useNotificationStore()
    notificationStore.addMessage({
      type: '任务分配',
      title: '新任务分配',
      content: `您有新任务待执行：${taskData.title}`
    })

    return newTask
  }

  function startTask(taskId) {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      task.status = 'in_progress'
      task.startTime = new Date().toLocaleString('zh-CN')
    }
    return task
  }

  function completeTask(taskId, report) {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      task.status = 'completed'
      task.progress = 100
      task.completeTime = new Date().toLocaleString('zh-CN')
      task.report = report
    }
    return task
  }

  function reassignTask(taskId, newAssigneeId, newAssigneeName, reason = '') {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      task.assigneeId = newAssigneeId
      task.assignee = newAssigneeName
      if (!task.history) {
        task.history = []
      }
      task.history.unshift({
        time: new Date().toLocaleString('zh-CN'),
        event: '重新调度',
        detail: `任务已由${newAssigneeName}接手执行${reason ? `，原因：${reason}` : ''}`
      })
    }
    return task
  }

  function updateTaskProgress(taskId, progress) {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) {
      task.progress = Math.min(100, Math.max(0, progress))
    }
    return task
  }

  function getTaskById(taskId) {
    return tasks.value.find(t => t.id === taskId)
  }

  function getTasksByAssignee(assigneeId) {
    return tasks.value.filter(t => t.assigneeId === assigneeId)
  }

  const pendingTasks = computed(() =>
    tasks.value.filter(t => t.status === 'pending')
  )

  const inProgressTasks = computed(() =>
    tasks.value.filter(t => t.status === 'in_progress')
  )

  const completedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'completed')
  )

  return {
    tasks,
    assignedTasks,
    statusLabelMap,
    statusTagMap,
    priorityLabelMap,
    priorityTagMap,
    pendingTasks,
    inProgressTasks,
    completedTasks,
    assignTask,
    startTask,
    completeTask,
    reassignTask,
    updateTaskProgress,
    getTaskById,
    getTasksByAssignee
  }
})
