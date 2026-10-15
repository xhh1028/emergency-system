<script setup>
import { ref, computed, onMounted } from 'vue'

// 车站管理员 - 本站事件管理（前端 mock，只展示本站上报事件）
const eventList = ref([])
const keyword = ref('')
const statusFilter = ref('')
const detailDialogVisible = ref(false)
const selectedEvent = ref(null)

// mock：本站上报事件
const MOCK_EVENTS = [
  { id: 1, title: 'B端扶梯骤停事件', station: '人民广场站', level: 'high', type: '设备故障', status: 'processing', reportTime: '2026-08-04 13:20', handler: '王队长', description: 'B端扶梯运行中骤停，乘客轻微擦伤，已安排检修并现场值守' },
  { id: 2, title: 'A口大客流预警', station: '人民广场站', level: 'medium', type: '客流异常', status: 'reported', reportTime: '2026-08-04 14:05', handler: '', description: '晚高峰临近，A口客流密度上升，建议启动限流措施' },
  { id: 3, title: '站台B端闸机故障', station: '人民广场站', level: 'low', type: '设备故障', status: 'closed', reportTime: '2026-08-03 09:00', handler: '李执行', description: '闸机无法刷卡，已维修恢复' },
  { id: 4, title: '乘客在站台摔倒受伤', station: '人民广场站', level: 'medium', type: '人员受伤', status: 'processing', reportTime: '2026-08-02 10:30', handler: '吴医护', description: '乘客在站台摔倒擦伤，医护人员现场处理后送医观察' }
]

const statusLabelMap = { reported: '事件上报', processing: '处置中', closed: '已关闭' }
const statusTagMap = { reported: 'warning', processing: 'primary', closed: 'success' }
const levelLabelMap = { high: '高危', medium: '中危', low: '低危' }
const levelTagMap = { high: 'danger', medium: 'warning', low: 'info' }

const filteredList = computed(() => {
  return eventList.value.filter(item => {
    const matchKw = !keyword.value || item.title.includes(keyword.value) || item.station.includes(keyword.value)
    const matchStatus = !statusFilter.value || item.status === statusFilter.value
    return matchKw && matchStatus
  })
})

function showDetail(row) {
  selectedEvent.value = row
  detailDialogVisible.value = true
}

function loadData() {
  eventList.value = [...MOCK_EVENTS]
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="event-page">
    <div class="page-header">
      <h2>事件管理</h2>
      <span class="page-desc">查看本站上报的重大事件及处置进度</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索事件标题或站点" clearable style="width: 220px" />
        <el-select v-model="statusFilter" placeholder="事件状态" clearable style="width: 140px">
          <el-option label="事件上报" value="reported" />
          <el-option label="处置中" value="processing" />
          <el-option label="已关闭" value="closed" />
        </el-select>
      </div>

      <el-table :data="filteredList" stripe border style="width: 100%">
        <el-table-column prop="title" label="事件名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="station" label="站点" width="120" />
        <el-table-column label="等级" width="90">
          <template #default="{ row }">
            <el-tag :type="levelTagMap[row.level]" size="small">{{ levelLabelMap[row.level] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="110" />
        <el-table-column prop="reportTime" label="上报时间" width="170" />
        <el-table-column prop="handler" label="处理人员" width="110">
          <template #default="{ row }">{{ row.handler || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status]" size="small">{{ statusLabelMap[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog title="事件详情" v-model="detailDialogVisible" width="560px">
      <div v-if="selectedEvent">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="事件名称" :span="2">{{ selectedEvent.title }}</el-descriptions-item>
          <el-descriptions-item label="站点">{{ selectedEvent.station }}</el-descriptions-item>
          <el-descriptions-item label="等级">
            <el-tag :type="levelTagMap[selectedEvent.level]" size="small">{{ levelLabelMap[selectedEvent.level] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类型">{{ selectedEvent.type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagMap[selectedEvent.status]" size="small">{{ statusLabelMap[selectedEvent.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="上报时间">{{ selectedEvent.reportTime }}</el-descriptions-item>
          <el-descriptions-item label="处理人员">{{ selectedEvent.handler || '-' }}</el-descriptions-item>
          <el-descriptions-item label="事件描述" :span="2">{{ selectedEvent.description }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.event-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.table-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>