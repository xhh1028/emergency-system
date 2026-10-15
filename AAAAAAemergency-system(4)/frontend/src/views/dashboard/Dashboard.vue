<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getDispatchOverview } from '@/api/dispatch'
import { useUserStore } from '@/store/modules/user'
import { useNotificationStore } from '@/store/modules/notification'

const userStore = useUserStore()
const notificationStore = useNotificationStore()

const stats = ref({ totalEvents: 0, activeEvents: 0, finishedEvents: 0, alertStations: 0, stationsOnline: 0, stationsTotal: 0 })
const alertList = ref([])
const lineStatusList = ref([])
const currentTime = ref(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
const loading = ref(false)

let timeInterval = null

const statCards = [
  { key: 'totalEvents', label: '事件总数', symbol: '—', trend: '+3', trendUp: true },
  { key: 'activeEvents', label: '处置中', symbol: '·', trend: '+1', trendUp: false, highlightOnValue: true, highlightColor: 'var(--orange)' },
  { key: 'finishedEvents', label: '已闭环', symbol: '✓', trend: '+8', trendUp: true },
  { key: 'alertStations', label: '告警车站', symbol: '◦', trend: '+2', trendUp: true, highlightOnValue: true, highlightColor: 'var(--red)' },
  { key: 'stationsOnline', label: '正常车站', symbol: '·', trend: '+5', trendUp: true },
  { key: 'stationsTotal', label: '车站总数', symbol: '—', trend: '-2', trendUp: false }
]

const lineColors = ['var(--red)', 'var(--accent)', 'var(--green)', 'var(--orange)', '#bf5af2', '#64d2ff', '#ff375f']

const statusLabelMap = {
  PENDING_ASSIGN: '待复核',
  STATION_HANDLE: '车站处置中',
  REPORTED_TO_DISPATCH: '已上报调度',
  FINISHED: '已闭环'
}

const levelColors = { GENERAL: 'var(--accent)', SERIOUS: 'var(--orange)', EXTREMELY_SERIOUS: 'var(--red)' }

function getStatusStyle(status) {
  if (status === 'PENDING_ASSIGN') return { background: 'rgba(255,69,58,0.12)', color: 'var(--red)' }
  if (status === 'STATION_HANDLE' || status === 'REPORTED_TO_DISPATCH') return { background: 'rgba(255,159,10,0.12)', color: 'var(--orange)' }
  return { background: 'rgba(48,209,88,0.12)', color: 'var(--green)' }
}

function getLevelColor(level) {
  return levelColors[level] || 'var(--accent)'
}

// 仅调度角色可读取真实总览数据；其他角色登录后应进入各自业务首页
const canViewDispatch = computed(() => ['admin', 'dispatch_center'].includes(userStore.role))

const notifications = computed(() =>
  notificationStore.messages.slice(0, 5).map(m => ({
    time: m.time,
    content: m.title || m.content || ''
  }))
)

async function loadData() {
  if (!canViewDispatch.value) return
  loading.value = true
  try {
    const response = await getDispatchOverview()
    const data = response.data || {}
    const s = data.statistics || {}
    const stations = data.stations || []
    const latest = data.latestEvents || []

    stats.value = {
      totalEvents: s.totalEvents ?? 0,
      activeEvents: s.activeEvents ?? 0,
      finishedEvents: s.finishedEvents ?? 0,
      alertStations: s.alertStations ?? 0,
      stationsOnline: stations.filter(st => !st.activeEventCount).length,
      stationsTotal: stations.length
    }

    alertList.value = latest.map(ev => ({
      id: ev.id,
      level: ev.level,
      title: `${ev.eventNo || ''} ${ev.description || ''}`.trim(),
      station: ev.stationName || '',
      line: ev.lineName ? `${ev.lineName}号线` : '',
      time: ev.createTime,
      status: ev.status
    }))

    // 线路运行状态：按线路分组，存在未闭环事件即为异常
    const groups = new Map()
    stations.forEach(st => {
      const key = String(st.line)
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key).push(st)
    })
    lineStatusList.value = [...groups.entries()].map(([line, items]) => {
      const hasAlert = items.some(st => st.activeEventCount > 0)
      return {
        line: `${line}号线`,
        color: lineColors[(Number(line) - 1) % lineColors.length] || 'var(--accent)',
        status: hasAlert ? 'abnormal' : 'normal',
        label: hasAlert ? '有未闭环事件' : '正常运行'
      }
    })
  } catch {
    // 接口异常时保持空数据展示
  } finally {
    loading.value = false
  }
}

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  loadData()
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <div class="page-header">
      <div class="page-title">
        <h1>应急指挥看板</h1>
        <span class="page-subtitle">城市级应急指挥调度平台</span>
      </div>
      <span class="current-time">{{ currentTime }}</span>
    </div>

    <div v-if="!canViewDispatch" class="role-tip">
      当前角色无调度数据查看权限，请从左侧菜单进入对应的业务界面。
    </div>

    <div class="stats-grid">
      <div v-for="card in statCards" :key="card.key" class="stat-card">
        <div class="stat-header">
          <span class="stat-symbol">{{ card.symbol }}</span>
          <span class="stat-label">{{ card.label }}</span>
        </div>
        <div 
          class="stat-value"
          :style="{ color: (card.highlightOnValue && stats[card.key] > 0) ? card.highlightColor : 'var(--text-primary)' }"
        >
          {{ stats[card.key] ?? 0 }}
        </div>
        <div class="stat-trend" :class="card.trendUp ? 'trend-up' : 'trend-down'">
          <span class="trend-prefix">{{ card.trendUp ? '↑' : '↓' }}</span>
          <span>{{ card.trend }} 较昨日</span>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <div class="main-panel">
        <div class="panel-header">
          <span class="panel-title">最新预警事件</span>
          <a href="#" class="view-all">全部 →</a>
        </div>
        <div class="alert-list">
          <div
            v-for="alert in alertList"
            :key="alert.id"
            class="alert-item"
          >
            <span class="level-bar" :style="{ backgroundColor: getLevelColor(alert.level) }" />
            <div class="alert-content">
              <span class="alert-title">{{ alert.title }}</span>
              <span class="alert-meta">{{ alert.station }} · {{ alert.line }}</span>
            </div>
            <div class="alert-right">
              <span class="alert-time">{{ new Date(alert.time).toLocaleTimeString('zh-CN', { hour12: false }) }}</span>
              <span class="status-tag" :style="getStatusStyle(alert.status)">
                {{ statusLabelMap[alert.status] }}
              </span>
              <a href="#" class="detail-link">详情</a>
            </div>
          </div>
        </div>
      </div>

      <div class="side-panel">
        <div class="panel-header">
          <span class="panel-title">线路运行状态</span>
        </div>
        <div class="line-list">
          <div
            v-for="line in lineStatusList"
            :key="line.line"
            class="line-item"
            :class="{ 'status-abnormal': line.status === 'abnormal' }"
          >
            <div class="line-dot" :style="{ backgroundColor: line.color }" />
            <span class="line-name">{{ line.line }}</span>
            <span class="line-status">
              <span v-if="line.status === 'normal'" class="status-dot" style="color: var(--green)">· </span>
              {{ line.label }}
            </span>
          </div>
        </div>
      </div>

      <div class="side-panel">
        <div class="panel-header">
          <span class="panel-title">系统通知</span>
        </div>
        <div class="notification-list">
          <div
            v-for="(item, index) in notifications"
            :key="index"
            class="notification-item"
          >
            <div class="timeline-dot" :class="{ latest: index === 0 }"></div>
            <div class="notification-content">
              <span class="notification-text">{{ item.content }}</span>
              <span class="notification-time">{{ item.time }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100%;
  padding: 24px;
}

.role-tip {
  padding: 14px 18px;
  margin-bottom: 24px;
  border-radius: var(--radius-md);
  background: rgba(10, 132, 255, 0.08);
  border: 1px solid rgba(10, 132, 255, 0.2);
  color: var(--accent);
  font-size: 13px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
}

.page-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title h1 {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
}

.current-time {
  font-size: 13px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  transition: all 0.2s ease;
}

.stat-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.2);
}

.stat-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.stat-symbol {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-right: 5px;
}

.stat-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.2px;
}

.stat-value {
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -1.5px;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
  margin-bottom: 12px;
}

.stat-trend {
  display: flex;
  align-items: center;
  font-size: 12px;
}

.trend-up {
  color: var(--green);
}

.trend-down {
  color: var(--red);
}

.trend-prefix {
  margin-right: 3px;
}

.content-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.main-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.side-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 20px;
}

.side-panel:last-child {
  margin-bottom: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.view-all {
  font-size: 13px;
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

.view-all:hover {
  color: var(--accent-hover);
}

.alert-list {
  padding: 0;
}

.alert-item {
  display: flex;
  align-items: center;
  height: 58px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  transition: background 0.15s;
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-item:hover {
  background: rgba(255,255,255,0.02);
}

.level-bar {
  width: 2px;
  height: 22px;
  flex-shrink: 0;
  border-radius: 1px;
  margin-right: 14px;
}

.alert-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.alert-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.alert-meta {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 3px;
}

.alert-right {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-end;
  gap: 6px;
  padding: 0 0 0 12px;
  border-left: 1px solid rgba(255,255,255,0.05);
}

.alert-time {
  font-size: 11px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.status-tag {
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
}

.detail-link {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

.detail-link:hover {
  color: var(--accent-hover);
}

.line-list {
  padding: 0;
}

.line-item {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 40px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.line-item:last-child {
  border-bottom: none;
}

.line-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.line-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.line-status {
  font-size: 12px;
  color: var(--text-tertiary);
}

.status-dot {
  font-size: 16px;
  line-height: 1;
  margin-right: 3px;
}

.line-item.status-abnormal {
  color: var(--red);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.notification-list {
  padding: 0 20px 20px 20px;
  max-height: 280px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  gap: 12px;
  padding: 16px 0 0 0;
}

.notification-item:first-child {
  padding-top: 16px;
}

.timeline-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  margin-top: 6px;
  flex-shrink: 0;
}

.timeline-dot.latest {
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent);
}

.notification-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.notification-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.notification-time {
  font-size: 11px;
  color: var(--text-tertiary);
}
</style>
