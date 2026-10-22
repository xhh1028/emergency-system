import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useFaultStore = defineStore('fault', () => {
  // 模拟设备台账，包含运行状态 run_status: normal / fault
  const devices = ref([
    { id: 1, name: '站台广播系统', line: '2号线', location: '站台', run_status: 'normal' },
    { id: 2, name: '出入口闸机', line: '2号线', location: '南出入口', run_status: 'normal' },
    { id: 3, name: '屏蔽门', line: '2号线', location: '2号站台', run_status: 'normal' },
    { id: 4, name: '照明系统', line: '2号线', location: '站厅', run_status: 'fault' },
    { id: 5, name: '区间信号设备', line: '2号线', location: 'A区', run_status: 'normal' }
  ])

  // 已上报的故障记录，status: open / resolved
  const faultReports = ref([
    {
      id: 1,
      deviceId: 4,
      deviceName: '照明系统',
      deviceLine: '2号线',
      deviceLocation: '站厅',
      description: '站厅主照明灯具闪烁，有灯条熄灭，影响乘客通行安全。',
      reporter: '李巡检',
      reportTime: new Date(Date.now() - 3600 * 1000).toLocaleString('zh-CN'),
      status: 'open'
    }
  ])

  const deviceTotal = computed(() => devices.value.length)
  const deviceNormal = computed(() => devices.value.filter((item) => item.run_status === 'normal').length)
  const deviceFault = computed(() => devices.value.filter((item) => item.run_status === 'fault').length)

  const openFaultReports = computed(() => faultReports.value.filter((item) => item.status === 'open'))
  const allFaultReports = computed(() => faultReports.value)

  function getDeviceById(deviceId) {
    return devices.value.find((item) => item.id === deviceId)
  }

  // 提交故障上报：更新设备状态为 fault，并新增故障上报记录
  function reportFault({ deviceId, description, reporter }) {
    const device = getDeviceById(deviceId)
    if (!device) {
      return null
    }

    if (device.run_status === 'normal') {
      device.run_status = 'fault'
    }

    const report = {
      id: Date.now(),
      deviceId: device.id,
      deviceName: device.name,
      deviceLine: device.line,
      deviceLocation: device.location,
      description: description || '未填写详细描述',
      reporter: reporter || '巡检人员',
      reportTime: new Date().toLocaleString('zh-CN'),
      status: 'open'
    }

    faultReports.value.unshift(report)
    return report
  }

  // 维修完成后将故障记录标记为已处理，并在该设备没有其它未处理故障时恢复设备状态为 normal
  function resolveFault(reportId) {
    const report = faultReports.value.find((item) => item.id === reportId)
    if (!report || report.status !== 'open') {
      return null
    }

    report.status = 'resolved'
    report.resolveTime = new Date().toLocaleString('zh-CN')

    const remainingOpen = faultReports.value.some(
      (item) => item.deviceId === report.deviceId && item.status === 'open'
    )

    if (!remainingOpen) {
      const device = getDeviceById(report.deviceId)
      if (device) {
        device.run_status = 'normal'
      }
    }

    return report
  }

  function getFaultReportById(reportId) {
    return faultReports.value.find((item) => item.id === reportId)
  }

  return {
    devices,
    faultReports,
    deviceTotal,
    deviceNormal,
    deviceFault,
    openFaultReports,
    allFaultReports,
    getDeviceById,
    reportFault,
    resolveFault,
    getFaultReportById
  }
})
