<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getStationEventDetail, getStationEventProgress, getStationTaskProgress } from '@/api/station'

const route = useRoute()
const router = useRouter()
const eventId = Number(route.params.id)
const loading = ref(false)
const event = ref(null)
const progressInfo = ref(null)
const tasks = ref([])
const total = ref(0)

const statusLabels = { PENDING: '待签收', IN_PROGRESS: '处置中', COMPLETED: '已完成', OVERDUE: '已逾期' }
const statusTypes = { PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', OVERDUE: 'danger' }
const sourceLabels = { STATION: '车站指派', DISPATCH: '调度指令' }
const eventStatusLabels = {
  PENDING_ASSIGN: '车站待复核', STATION_HANDLE: '车站处置中',
  REPORTED_TO_DISPATCH: '已上报调度', FINISHED: '已闭环'
}
const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}
const levelLabels = { GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '特别严重' }
const levelTypes = { GENERAL: 'success', SERIOUS: 'warning', EXTREMELY_SERIOUS: 'danger' }

async function loadData() {
  loading.value = true
  try {
    const [eventRes, progressRes, taskRes] = await Promise.all([
      getStationEventDetail(eventId),
      getStationEventProgress(),
      getStationTaskProgress({ eventId, page: 1, size: 100 })
    ])
    event.value = eventRes.data
    progressInfo.value = (progressRes.data || []).find(item => item.id === eventId) || null
    tasks.value = taskRes.data?.list || []
    total.value = taskRes.data?.total || 0
  } finally {
    loading.value = false
  }
}

// 第三层钻取：查看单条子任务详情与一线执行反馈
function openTaskDetail(row) {
  router.push(`/station/progress/task/${row.id}`)
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 19) : '—'
}

onMounted(loadData)
</script>

<template>
  <div class="event-progress-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>事件处置详情</h2>
        <span class="page-desc">第二层：查看该事件全部子任务，点击【查看详情】钻取单条子任务的执行反馈。</span>
      </div>
      <el-button @click="router.push('/station/progress')">返回进度监控</el-button>
    </div>

    <template v-if="event">
      <el-card shadow="hover" class="info-card">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="事件编号">{{ event.eventNo }}</el-descriptions-item>
          <el-descriptions-item label="事件标题">{{ event.title }}</el-descriptions-item>
          <el-descriptions-item label="事件类型">{{ typeLabels[event.eventType] || event.eventType }}</el-descriptions-item>
          <el-descriptions-item label="事件等级">
            <el-tag :type="levelTypes[event.finalLevel] || levelTypes[event.aiLevel]">
              {{ levelLabels[event.finalLevel] || levelLabels[event.aiLevel] || '待确认' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="事发车站">{{ event.stationName }}</el-descriptions-item>
          <el-descriptions-item label="事件状态">{{ eventStatusLabels[event.status] || event.status }}</el-descriptions-item>
          <el-descriptions-item label="事件描述" :span="3">{{ event.description || '—' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="progressInfo" shadow="hover" class="info-card">
        <template #header><strong>事件处置总进度</strong></template>
        <div class="total-progress">
          <el-progress
            :percentage="progressInfo.progress"
            :status="progressInfo.progress === 100 ? 'success' : undefined"
            :stroke-width="12"
          />
          <span class="progress-count">
            {{ progressInfo.finishedTasks }}/{{ progressInfo.totalTasks }} 条子任务已完成（finished ÷ 全部子任务 ×100%）
          </span>
        </div>
      </el-card>

      <el-card shadow="hover">
        <template #header><strong>子任务列表（{{ total }} 条）</strong></template>
        <el-table :data="tasks" empty-text="该事件暂无子任务" style="width: 100%">
          <el-table-column prop="taskNo" label="任务编号" width="150" />
          <el-table-column prop="content" label="任务内容" min-width="240" show-overflow-tooltip />
          <el-table-column label="来源" width="120">
            <template #default="{ row }">{{ sourceLabels[row.source] || row.source }}</template>
          </el-table-column>
          <el-table-column prop="executorName" label="执行人员" width="140" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }"><el-tag :type="statusTypes[row.status]">{{ statusLabels[row.status] || row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="截止时间" width="180">
            <template #default="{ row }">{{ formatTime(row.deadline) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="openTaskDetail(row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.event-progress-page{min-height:100%}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.page-header h2{margin:0;font-size:22px;color:var(--metro-text-primary)}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.info-card{margin-bottom:16px}.total-progress{display:flex;flex-direction:column;gap:8px}.progress-count{font-size:13px;color:var(--metro-text-muted)}
</style>
