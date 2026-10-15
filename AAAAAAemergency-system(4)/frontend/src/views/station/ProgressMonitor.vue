<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getStationEventProgress } from '@/api/station'

const router = useRouter()
const loading = ref(false)
const rows = ref([])

const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}
const levelLabels = { GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '特别严重' }
const levelTypes = { GENERAL: 'success', SERIOUS: 'warning', EXTREMELY_SERIOUS: 'danger' }

async function loadEvents() {
  loading.value = true
  try {
    rows.value = (await getStationEventProgress()).data || []
  } finally {
    loading.value = false
  }
}

// 第二层钻取：查看该事件全部子任务
function openEventDetail(row) {
  router.push(`/station/progress/event/${row.id}`)
}

onMounted(loadEvents)
</script>

<template>
  <div class="progress-page">
    <div class="page-header">
      <h2>进度监控</h2>
      <span class="page-desc">第一层：按事件总览本站处置总进度，点击【查看处置详情】钻取该事件全部子任务。</span>
    </div>

    <el-card shadow="hover">
      <el-table :data="rows" v-loading="loading" empty-text="暂无已分派子任务的险情事件" style="width: 100%">
        <el-table-column label="事件编号" min-width="220">
          <template #default="{ row }">
            <div class="event-cell">
              <div class="event-no">{{ row.eventNo }}</div>
              <div v-if="row.eventTitle" class="event-title" :title="row.eventTitle">{{ row.eventTitle }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="事件类型" min-width="150">
          <template #default="{ row }">{{ typeLabels[row.eventType] || row.eventType }}</template>
        </el-table-column>
        <el-table-column label="事件等级" width="120">
          <template #default="{ row }">
            <el-tag :type="levelTypes[row.eventLevel]">{{ levelLabels[row.eventLevel] || '待确认' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="事件总进度" min-width="220">
          <template #default="{ row }">
            <div class="progress-cell">
              <el-progress
                :percentage="row.progress"
                :status="row.progress === 100 ? 'success' : undefined"
                :stroke-width="8"
              />
              <span class="progress-count">{{ row.finishedTasks }}/{{ row.totalTasks }} 条子任务已完成</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEventDetail(row)">查看处置详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.progress-page{min-height:100%}.page-header{margin-bottom:24px}.page-header h2{margin:0;font-size:22px;color:var(--metro-text-primary)}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.event-cell{line-height:1.5}.event-no{font-weight:500;color:var(--metro-text-primary);font-size:13px}.event-title{font-size:12px;color:var(--metro-text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:230px}.progress-cell{display:flex;flex-direction:column;gap:6px}.progress-count{font-size:12px;color:var(--metro-text-muted)}
</style>
