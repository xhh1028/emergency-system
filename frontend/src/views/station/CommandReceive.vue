<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStationCommandDetail, getStationCommands, signCommand } from '@/api/station'

const router = useRouter()
const loading = ref(false)
const signing = ref(false)
const rows = ref([])
const total = ref(0)
const detailVisible = ref(false)
const command = ref(null)
const filter = reactive({ status: 'ALL', keyword: '', page: 1, size: 10 })
const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}

async function loadCommands() {
  loading.value = true
  try {
    const response = await getStationCommands(filter)
    rows.value = response.data?.list || []
    total.value = response.data?.total || 0
  } finally { loading.value = false }
}

async function openDetail(row) {
  command.value = (await getStationCommandDetail(row.id)).data
  detailVisible.value = true
}

async function handleSign(row = command.value) {
  if (!row) return
  signing.value = true
  try {
    command.value = (await signCommand(row.id)).data
    ElMessage.success('调度指令已签收')
    await loadCommands()
  } finally { signing.value = false }
}

function assignTasks() {
  if (!command.value?.read) return ElMessage.warning('请先签收指令')
  if (!command.value.eventId) return ElMessage.warning('该指令未关联事件，暂不能创建处置任务')
  detailVisible.value = false
  router.push({ path: '/station/assign', query: { eventId: command.value.eventId, commandId: command.value.id } })
}

function search() { filter.page = 1; loadCommands() }
function formatTime(value) { return value ? String(value).replace('T', ' ') : '—' }
onMounted(loadCommands)
</script>

<template>
  <div class="receive-page">
    <div class="page-header"><h2>指令接收</h2><span class="page-desc">接收调度指挥中心下发的处置指令，签收后进入本站任务分配。</span></div>
    <el-card shadow="hover">
      <div class="toolbar">
        <el-select v-model="filter.status" style="width:150px" @change="search"><el-option label="全部指令" value="ALL"/><el-option label="待签收" value="UNREAD"/><el-option label="已签收" value="READ"/></el-select>
        <el-input v-model="filter.keyword" placeholder="搜索指令内容、事件编号或下发人" clearable class="keyword" @keyup.enter="search" @clear="search"/>
        <el-button type="primary" @click="search">查询</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" empty-text="暂无调度指令" style="width: 100%">
        <el-table-column prop="sendTime" label="下发时间" width="180"><template #default="{row}">{{ formatTime(row.sendTime) }}</template></el-table-column>
        <el-table-column prop="sender" label="下发人" width="120"/><el-table-column prop="eventNo" label="关联事件" width="190"><template #default="{row}">{{ row.eventNo || '未关联事件' }}</template></el-table-column>
        <el-table-column prop="eventType" label="事件类型" width="160"><template #default="{row}">{{ typeLabels[row.eventType] || '—' }}</template></el-table-column>
        <el-table-column prop="content" label="指令内容" min-width="260" show-overflow-tooltip/>
        <el-table-column prop="read" label="签收状态" width="100"><template #default="{row}"><el-tag :type="row.read?'success':'warning'">{{ row.read?'已签收':'待签收' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" min-width="190" fixed="right"><template #default="{row}"><el-button type="primary" link @click="openDetail(row)">查看详情</el-button><el-button v-if="!row.read" type="success" link :loading="signing" @click="handleSign(row)">确认签收</el-button></template></el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="filter.page" v-model:page-size="filter.size" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @current-change="loadCommands" @size-change="search"/></div>
    </el-card>
    <el-dialog v-model="detailVisible" title="调度指令详情" width="650px">
      <el-descriptions v-if="command" :column="2" border><el-descriptions-item label="下发人">{{ command.sender }}</el-descriptions-item><el-descriptions-item label="下发时间">{{ formatTime(command.sendTime) }}</el-descriptions-item><el-descriptions-item label="事件编号">{{ command.eventNo||'未关联' }}</el-descriptions-item><el-descriptions-item label="事件类型">{{ typeLabels[command.eventType]||'—' }}</el-descriptions-item><el-descriptions-item label="签收状态">{{ command.read?'已签收':'待签收' }}</el-descriptions-item><el-descriptions-item label="指令内容" :span="2"><div class="command-content">{{ command.content }}</div></el-descriptions-item></el-descriptions>
      <template #footer><el-button @click="detailVisible=false">关闭</el-button><el-button v-if="command&&!command.read" type="success" :loading="signing" @click="handleSign()">确认签收</el-button><el-button v-if="command?.read" type="primary" @click="assignTasks">任务分配</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.receive-page{min-height:100%}.page-header{margin-bottom:24px}.page-header h2{margin:0;font-size:22px;color:var(--metro-text-primary)}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.toolbar{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px}.keyword{width:340px}.pagination{display:flex;justify-content:flex-end;margin-top:16px}.command-content{white-space:pre-wrap;line-height:1.8}
</style>
