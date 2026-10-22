<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDispatchStations, getDispatchProgress } from '@/api/dispatch'

const stationList = ref([])
const loading = ref(false)
const lineFilter = ref('')

const filteredStations = computed(() => {
  if (!lineFilter.value) return stationList.value
  return stationList.value.filter(s => s.line === `${lineFilter.value}号线`)
})

function getStatusColor(station) {
  if (station.status === 'offline') return 'rgba(255,255,255,0.3)'
  if (station.alertCount > 0) return 'var(--red)'
  return 'var(--green)'
}

function getStatusText(station) {
  if (station.status === 'offline') return '离线'
  if (station.alertCount > 0) return '告警'
  return '正常'
}

function getProgressColor(rate) {
  if (rate >= 80) return 'var(--green)'
  if (rate >= 50) return 'var(--orange)'
  return 'var(--red)'
}

async function loadData() {
  loading.value = true
  try {
    const stationsRes = await getDispatchStations()
    const stations = stationsRes.data || []
    const progressRes = await getDispatchProgress({ page: 1, size: 100 })
    const tasks = progressRes.data?.list || []

    stationList.value = stations.map(s => {
      const stationTasks = tasks.filter(t => t.stationId === s.id)
      const done = stationTasks.filter(t => t.rawStatus === 'COMPLETED').length
      return {
        ...s,
        name: s.name,
        line: `${s.line}号线`,
        status: 'online',
        alertCount: 0,
        taskTotal: stationTasks.length,
        taskDone: done,
        completionRate: stationTasks.length ? Math.round((done / stationTasks.length) * 100) : 0
      }
    })
  } catch {
    stationList.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="progress-page">
    <div class="page-header">
      <div class="page-title">
        <h2>全站进度</h2>
        <span class="page-desc">各车站应急处置任务完成率统计</span>
      </div>
      <div class="filters">
        <select v-model="lineFilter" class="select-field">
          <option value="">全部线路</option>
          <option v-for="i in 5" :key="i" :value="i">{{ i }}号线</option>
        </select>
      </div>
    </div>

    <div class="main-panel">
      <div class="panel-header">
        <span class="panel-title">车站状态总览</span>
      </div>
      <div class="panel-body">
        <div class="station-grid">
          <div
            v-for="station in filteredStations"
            :key="station.id"
            class="station-card"
            :class="{ 'station-offline': station.status === 'offline', 'station-alert': station.alertCount > 0 }"
          >
            <div class="station-header">
              <span class="station-name">{{ station.name }}</span>
              <div v-if="station.alertCount > 0" class="alert-badge">{{ station.alertCount }}</div>
            </div>
            <div class="station-line">{{ station.line }}</div>
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: `${station.completionRate}%`, background: getProgressColor(station.completionRate) }"
              ></div>
            </div>
            <div class="station-footer">
              <span class="task-count">任务：{{ station.taskDone }}/{{ station.taskTotal }}</span>
              <span class="status-tag" :style="{ color: getStatusColor(station) }">
                {{ getStatusText(station) }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="filteredStations.length === 0" class="empty-state">
          <div class="empty-icon">📊</div>
          <div class="empty-text">暂无站点数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-page {
  min-height: 100%;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.page-desc {
  font-size: 13px;
  color: var(--text-tertiary);
}

.filters {
  display: flex;
  gap: 10px;
}

.select-field {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  font-family: inherit;
  transition: all 0.2s ease;
  outline: none;
  min-width: 140px;
}

.select-field:focus {
  border-color: rgba(10, 132, 255, 0.6);
  box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
}

.main-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-body {
  padding: 20px;
}

.station-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.station-card {
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  transition: all 0.2s ease;
}

.station-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.station-offline {
  opacity: 0.6;
}

.station-alert {
  border-left: 3px solid var(--red);
}

.station-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.station-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.alert-badge {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--red);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}

.station-line {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.station-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-count {
  font-size: 12px;
  color: var(--text-tertiary);
}

.status-tag {
  font-size: 12px;
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 48px 20px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-text {
  font-size: 14px;
  color: var(--text-tertiary);
}
</style>
