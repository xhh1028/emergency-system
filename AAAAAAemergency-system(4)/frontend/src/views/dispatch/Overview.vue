<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDispatchOverview } from '@/api/dispatch'
import { useUserStore } from '@/store/modules/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const statistics = ref({ totalEvents: 0, activeEvents: 0, finishedEvents: 0, alertStations: 0 })
const stations = ref([])
const latestEvents = ref([])
const lastUpdated = ref('')

const statCards = [
  { key: 'totalEvents', label: '事件总数', unit: '件', color: '#0a84ff', bg: 'rgba(10,132,255,.12)' },
  { key: 'activeEvents', label: '处置中', unit: '件', color: '#ff9f0a', bg: 'rgba(255,159,10,.12)' },
  { key: 'finishedEvents', label: '已闭环', unit: '件', color: '#30d158', bg: 'rgba(48,209,88,.12)' },
  { key: 'alertStations', label: '告警车站', unit: '站', color: '#ff453a', bg: 'rgba(255,69,58,.12)' }
]
const levelLabels = { NONE: '正常', GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '非常严重' }
const levelTypes = { GENERAL: 'success', SERIOUS: 'warning', EXTREMELY_SERIOUS: 'danger' }
const statusLabels = {
  PENDING_ASSIGN: '车站待复核', STATION_HANDLE: '车站处置中',
  REPORTED_TO_DISPATCH: '已上报调度', FINISHED: '已闭环'
}
const eventTypeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}
const lineColors = ['#0a84ff', '#30d158', '#ff9f0a', '#bf5af2', '#64d2ff', '#ff375f']

const lineGroups = computed(() => {
  const groups = new Map()
  stations.value.forEach(station => {
    const key = String(station.line)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(station)
  })
  return [...groups.entries()].map(([line, items], index) => ({
    line,
    color: lineColors[index % lineColors.length],
    stations: items
  }))
})

async function loadOverview(silent = false) {
  if (!silent) loading.value = true
  try {
    const response = await getDispatchOverview()
    statistics.value = response.data?.statistics || statistics.value
    stations.value = response.data?.stations || []
    latestEvents.value = response.data?.latestEvents || []
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } finally {
    if (!silent) loading.value = false
  }
}

function stationClass(station) {
  return {
    normal: !station.activeEventCount,
    general: station.highestLevel === 'GENERAL',
    serious: station.highestLevel === 'SERIOUS',
    extreme: station.highestLevel === 'EXTREMELY_SERIOUS'
  }
}

function openEvent(eventId) {
  if (!eventId) return
  const path = userStore.role === 'admin' ? '/dispatch/events' : '/dispatch/event'
  router.push({ path, query: { eventId } })
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 19) : '—'
}

onMounted(async () => {
  await loadOverview()
  window.addEventListener('emergency-realtime', handleRealtimeUpdate)
})
function handleRealtimeUpdate() { loadOverview(true) }
onUnmounted(() => window.removeEventListener('emergency-realtime', handleRealtimeUpdate))
</script>

<template>
  <div class="overview-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>调度指挥总览大屏</h2>
        <span>真实监控全路网应急事件态势，业务变化由后端实时推送</span>
      </div>
      <div class="refresh-state"><i></i>数据已连接 · {{ lastUpdated || '连接中' }}</div>
    </div>

    <div class="stat-row">
      <div v-for="card in statCards" :key="card.key" class="stat-card">
        <div class="stat-icon" :style="{ background: card.bg }"><i :style="{ background: card.color }"></i></div>
        <div><strong>{{ statistics[card.key] }}</strong><span>{{ card.label }}（{{ card.unit }}）</span></div>
      </div>
    </div>

    <div class="content-grid">
      <section class="network-panel">
        <div class="panel-header">
          <strong>全路网车站态势</strong>
          <div class="legend"><span class="normal"></span>正常 <span class="general"></span>一般 <span class="serious"></span>严重 <span class="extreme"></span>非常严重</div>
        </div>
        <div class="network-map">
          <div v-for="group in lineGroups" :key="group.line" class="line-row">
            <div class="line-name" :style="{ background: group.color }">{{ group.line }}号线</div>
            <div class="station-track" :style="{ '--line-color': group.color }">
              <el-tooltip v-for="station in group.stations" :key="station.id" placement="top" effect="dark">
                <template #content>
                  <div class="station-tooltip">
                    <strong>{{ station.name }}</strong>
                    <span>事件数：{{ station.activeEventCount }}条</span>
                    <span>最高等级：{{ levelLabels[station.highestLevel] }}</span>
                    <span>简要事件：{{ station.brief }}</span>
                    <em v-if="station.primaryEventId">点击查看事件详情</em>
                  </div>
                </template>
                <button
                  class="station-node"
                  :class="stationClass(station)"
                  :disabled="!station.primaryEventId"
                  @click="openEvent(station.primaryEventId)"
                >
                  <i></i><span>{{ station.name }}</span>
                  <b v-if="station.activeEventCount">{{ station.activeEventCount }}</b>
                </button>
              </el-tooltip>
            </div>
          </div>
          <el-empty v-if="!lineGroups.length" description="暂无车站基础数据" />
        </div>
      </section>

      <section class="event-panel">
        <div class="panel-header"><strong>最新未闭环事件</strong><span>{{ latestEvents.length }} 条</span></div>
        <div class="event-list">
          <button v-for="event in latestEvents" :key="event.id" class="event-item" @click="openEvent(event.id)">
            <div class="event-top">
              <el-tag :type="levelTypes[event.level]" size="small">{{ levelLabels[event.level] }}</el-tag>
              <span>{{ formatTime(event.createTime) }}</span>
            </div>
            <strong>{{ eventTypeLabels[event.eventType] || event.eventType }}</strong>
            <p>{{ event.description || '暂无事件描述' }}</p>
            <div>{{ event.lineName }}号线 · {{ event.stationName }} · {{ statusLabels[event.status] || event.status }}</div>
          </button>
          <el-empty v-if="!latestEvents.length" description="当前全线无未闭环事件" :image-size="70" />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.overview-page{min-height:100%;padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.page-header h2{margin:0;color:var(--text-primary);font-size:22px}.page-header span{display:block;margin-top:5px;color:var(--text-tertiary);font-size:13px}.refresh-state{color:#30d158;font-size:12px}.refresh-state i{display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:#30d158;box-shadow:0 0 10px #30d158}.stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}.stat-card{display:flex;align-items:center;gap:13px;padding:18px;border:1px solid var(--border);border-radius:12px;background:var(--bg-elevated)}.stat-icon{display:grid;width:48px;height:48px;place-items:center;border-radius:11px}.stat-icon i{width:15px;height:15px;border-radius:50%}.stat-card strong{display:block;color:var(--text-primary);font-size:27px}.stat-card span{color:var(--text-tertiary);font-size:12px}.content-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:16px}.network-panel,.event-panel{overflow:hidden;border:1px solid var(--border);border-radius:12px;background:var(--bg-elevated)}.panel-header{display:flex;justify-content:space-between;align-items:center;min-height:52px;padding:0 18px;border-bottom:1px solid var(--border);color:var(--text-primary)}.panel-header>span{color:var(--text-tertiary);font-size:12px}.legend{display:flex;align-items:center;gap:6px;color:var(--text-tertiary);font-size:11px}.legend span{width:9px;height:9px;margin-left:7px;border-radius:50%}.legend .normal{background:#8e8e93}.legend .general{background:#ffd60a}.legend .serious{background:#ff9f0a}.legend .extreme{background:#ff453a}.network-map{min-height:420px;max-height:620px;padding:18px;overflow:auto;background:radial-gradient(circle at 50% 20%,rgba(10,132,255,.08),transparent 50%)}.line-row{display:flex;align-items:stretch;min-width:620px;margin-bottom:22px}.line-name{display:flex;align-items:center;justify-content:center;width:66px;min-height:64px;border-radius:8px;color:#fff;font-size:12px;font-weight:700}.station-track{position:relative;display:flex;flex:1;align-items:flex-start;justify-content:space-around;padding:5px 12px}.station-track:before{content:"";position:absolute;top:18px;right:0;left:0;height:4px;border-radius:4px;background:var(--line-color);opacity:.65}.station-node{position:relative;z-index:1;display:flex;width:76px;flex-direction:column;align-items:center;border:0;background:transparent;color:var(--text-secondary);cursor:pointer}.station-node:disabled{cursor:default}.station-node i{width:22px;height:22px;border:4px solid var(--bg-elevated);border-radius:50%;background:#8e8e93;box-shadow:0 0 0 2px #8e8e93}.station-node span{max-width:74px;margin-top:8px;overflow:hidden;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.station-node b{position:absolute;top:-6px;right:15px;display:grid;width:18px;height:18px;place-items:center;border-radius:50%;background:#ff453a;color:#fff;font-size:10px}.station-node.general i{background:#ffd60a;box-shadow:0 0 12px #ffd60a}.station-node.serious i{background:#ff9f0a;box-shadow:0 0 14px #ff9f0a}.station-node.extreme i{background:#ff453a;box-shadow:0 0 16px #ff453a;animation:pulse 1.4s infinite}.station-tooltip{display:grid;max-width:300px;gap:5px;line-height:1.45}.station-tooltip strong{font-size:14px}.station-tooltip span{white-space:normal}.station-tooltip em{margin-top:3px;color:#64d2ff;font-style:normal}.event-list{max-height:620px;overflow:auto;padding:8px}.event-item{display:block;width:100%;padding:12px;border:0;border-bottom:1px solid var(--border);border-radius:8px;background:transparent;color:inherit;text-align:left;cursor:pointer}.event-item:hover{background:rgba(255,255,255,.04)}.event-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.event-top span{color:var(--text-tertiary);font-size:10px}.event-item>strong{color:var(--text-primary);font-size:13px}.event-item p{display:-webkit-box;margin:6px 0;overflow:hidden;color:var(--text-secondary);font-size:12px;line-height:1.5;-webkit-box-orient:vertical;-webkit-line-clamp:2}.event-item>div:last-child{color:var(--text-tertiary);font-size:11px}@keyframes pulse{50%{transform:scale(1.25);opacity:.7}}@media(max-width:1100px){.content-grid{grid-template-columns:1fr}.stat-row{grid-template-columns:repeat(2,1fr)}}@media(max-width:640px){.page-header{align-items:flex-start;gap:12px}.stat-row{grid-template-columns:1fr}.legend{display:none}}
</style>
