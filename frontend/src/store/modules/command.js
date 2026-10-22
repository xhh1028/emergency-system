import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useNotificationStore } from '@/store/modules/notification'

export const useCommandStore = defineStore('command', () => {
  const commandHistory = ref([])

  const pendingCommands = computed(() =>
    commandHistory.value.filter(cmd => cmd.status === 'pending')
  )

  const receivedCommands = ref([])

  function sendCommand(command) {
    const newCommand = {
      id: Date.now(),
      content: command.content,
      priority: command.priority || 'normal',
      targetStation: command.targetStation || '',
      sender: command.sender || 'admin',
      sendTime: new Date().toLocaleString('zh-CN'),
      status: 'pending',
      receipts: []
    }

    commandHistory.value.unshift(newCommand)

    const notificationStore = useNotificationStore()
    notificationStore.addMessage({
      type: '新指令',
      title: '指令下发成功',
      content: `已向 ${command.targetStation || '所有车站'} 下发指令`
    })

    return newCommand
  }

  function updateReceipt(commandId, stationId, status) {
    const command = commandHistory.value.find(cmd => cmd.id === commandId)
    if (command) {
      const receipt = command.receipts.find(r => r.stationId === stationId)
      if (receipt) {
        receipt.status = status
        receipt.receiptTime = new Date().toLocaleString('zh-CN')
      } else {
        command.receipts.push({
          stationId,
          status,
          receiptTime: status === 'received' ? new Date().toLocaleString('zh-CN') : ''
        })
      }

      if (command.receipts.every(r => r.status === 'received')) {
        command.status = 'received'
      }
    }
  }

  function confirmReceipt(commandId, stationId) {
    updateReceipt(commandId, stationId, 'received')

    const notificationStore = useNotificationStore()
    notificationStore.addMessage({
      type: '任务更新',
      title: '指令已签收',
      content: '您已确认签收调度指令'
    })
  }

  function addReceivedCommand(command) {
    const exists = receivedCommands.value.find(cmd => cmd.id === command.id)
    if (!exists) {
      receivedCommands.value.unshift({
        ...command,
        receiptStatus: 'pending'
      })
    }
  }

  function getCommandById(commandId) {
    return commandHistory.value.find(cmd => cmd.id === commandId)
  }

  return {
    commandHistory,
    pendingCommands,
    receivedCommands,
    sendCommand,
    updateReceipt,
    confirmReceipt,
    addReceivedCommand,
    getCommandById
  }
})
