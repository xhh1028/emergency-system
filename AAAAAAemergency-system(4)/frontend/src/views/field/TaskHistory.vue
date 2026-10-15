<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getMyCompletedTasks, getMyReportedEvents, resubmitEvent, withdrawEvent } from '@/api/event'

const activeTab = ref('reports')
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const detailVisible = ref(false)
const detailKind = ref('event')
const detail = ref({})
const filters = reactive({
  reports: { keyword: '', range: [], page: 1, size: 10 },
  tasks: { keyword: '', range: [], page: 1, size: 10 }
})
const currentFilter = computed(() => filters[activeTab.value])

const eventTypeLabels = {
  DEVICE_FAILURE: '设备故障',
  FIRE: '火灾险情',
  PASSENGER: '乘客事件',
  TRACK_OPERATION: '轨道及行车险情',
  CROWD_SECURITY: '客流及治安事件',
  DISASTER_ENVIRONMENT: '灾害及环境事件',
  OTHER: '其他事件'
}

const levelLabels = {
  GENERAL: '一般',
  SERIOUS: '严重',
  EXTREMELY_SERIOUS: '特别严重',
  UNCONFIRMED: '待确认'
}

const statusLabels = {
  PENDING_ASSIGN: '待分派',
  PENDING: '待处理',
  CONFIRMED: '已确认',
  REJECTED: '已驳回',
  PROCESSING: '处置中',
  HANDLING: '处置中',
  COMPLETED: '已完成',
  CLOSED: '已闭环',
  FINISHED: '已闭环'
}

const current = () => filters[activeTab.value]

function buildParams() {
  const state = current()
  const params = {
    page: state.page,
    size: state.size,
    keyword: state.keyword.trim() || undefined
  }
  if (state.range?.length === 2) {
    params.start = state.range[0]
    params.end = state.range[1]
  }
  return params
}

async function loadHistory() {
  loading.value = true
  try {
    const request = activeTab.value === 'reports' ? getMyReportedEvents : getMyCompletedTasks
    const response = await request(buildParams())
    rows.value = response.data?.list || []
    total.value = response.data?.total || 0
  } catch (error) {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  current().page = 1
  loadHistory()
}

function resetFilters() {
  current().keyword = ''
  current().range = []
  current().page = 1
  loadHistory()
}

function handleTabChange() {
  rows.value = []
  loadHistory()
}

function handlePageChange(page) {
  current().page = page
  loadHistory()
}

function handleSizeChange(size) {
  current().size = size
  current().page = 1
  loadHistory()
}

function showDetail(row, kind) {
  detail.value = row
  detailKind.value = kind
  detailVisible.value = true
}

// ===== 被驳回事件补充完善并重新提交 =====
const resubmitVisible = ref(false)
const resubmitSubmitting = ref(false)
const resubmitForm = reactive({ eventId: null, eventTitle: '', faultyDevice: '', description: '' })
const resubmitFiles = ref([])

function openResubmit(row) {
  resubmitForm.eventId = row.id
  resubmitForm.eventTitle = row.title || ''
  resubmitForm.faultyDevice = row.faultyDevice || ''
  resubmitForm.description = row.description || ''
  resubmitFiles.value = []
  resubmitVisible.value = true
}

function onResubmitFileChange(file, files) {
  const raw = file.raw
  const validType = raw && ['image/jpeg', 'image/png', 'image/webp'].includes(raw.type)
  const validSize = raw && raw.size <= 5 * 1024 * 1024
  if (!validType) ElMessage.error('仅支持 JPG、PNG、WEBP 图片')
  if (!validSize) ElMessage.error('单张图片不能超过5MB')
  if (validType && validSize) resubmitFiles.value = files.slice(0, 5)
  else resubmitFiles.value = files.filter(item => item.uid !== file.uid)
}

function onResubmitFileExceed() {
  ElMessage.warning('现场图片最多上传5张')
}

async function submitResubmit() {
  if (!resubmitForm.description.trim()) {
    ElMessage.warning('请补充事件描述')
    return
  }
  resubmitSubmitting.value = true
  try {
    const data = new FormData()
    data.append('eventTitle', resubmitForm.eventTitle.trim())
    data.append('faultyDevice', resubmitForm.faultyDevice.trim())
    data.append('description', resubmitForm.description.trim())
    resubmitFiles.value.forEach(item => data.append('images', item.raw))
    await resubmitEvent(resubmitForm.eventId, data)
    ElMessage.success('补充完成，已重新提交，等待车站管理员复核')
    resubmitVisible.value = false
    await loadHistory()
  } finally {
    resubmitSubmitting.value = false
  }
}

// 撤回上报：仅状态 PENDING 且未撤回的事件可撤回（逻辑删除，写日志留痕）
async function handleWithdraw(row) {
  try {
    await ElMessageBox.confirm(
      `确认撤回事件 ${row.eventNo} 吗？撤回后该事件将从事件待办中隐藏，不可恢复。`,
      '撤回上报',
      { type: 'warning', confirmButtonText: '确认撤回', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await withdrawEvent(row.id)
    ElMessage.success('事件已撤回')
    await loadHistory()
  } catch {
    // 业务错误（如"事件已经被处理，不允许撤回"）由公共请求层提示
  }
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ') : '—'
}

function formatDuration(minutes) {
  const value = Number(minutes || 0)
  if (value < 60) return `${value} 分钟`
  const hours = Math.floor(value / 60)
  const rest = value % 60
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`
}

function statusType(status) {
  if (['COMPLETED', 'CLOSED', 'FINISHED', 'CONFIRMED'].includes(status)) return 'success'
  if (['PROCESSING', 'HANDLING', 'PENDING'].includes(status)) return 'warning'
  if (status === 'REJECTED') return 'danger'
  return 'info'
}

function imageList(urls) {
  return urls ? String(urls).split(';').filter(Boolean) : []
}

onMounted(loadHistory)
</script>

<template>
  <div class="history-page">
    <div class="page-header">
      <h2>历史记录</h2>
      <span class="page-desc">查询本人上报的事件和本人已完成的任务。</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="我上报的事件" name="reports" />
        <el-tab-pane label="已完成任务" name="tasks" />
      </el-tabs>

      <div class="toolbar">
        <el-input
          v-model="currentFilter.keyword"
          :placeholder="activeTab === 'reports' ? '事件编号、类型或描述' : '任务内容或类型'"
          clearable
          :prefix-icon="Search"
          class="keyword"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-date-picker
          v-model="currentFilter.range"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm:ss"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          class="date-range"
        />
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table
        v-if="activeTab === 'reports'"
        :data="rows"
        v-loading="loading"
        empty-text="暂无本人上报的事件"
        style="width: 100%"
      >
        <el-table-column prop="eventNo" label="事件编号" min-width="190" />
        <el-table-column prop="title" label="事件标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="faultyDevice" label="故障设备" min-width="140">
          <template #default="{ row }">{{ row.faultyDevice || '—' }}</template>
        </el-table-column>
        <el-table-column prop="eventType" label="事件类型" min-width="150">
          <template #default="{ row }">{{ eventTypeLabels[row.eventType] || row.eventType }}</template>
        </el-table-column>
        <el-table-column prop="stationName" label="所属车站" min-width="130" />
        <el-table-column prop="createTime" label="上报时间" min-width="180">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="处理状态" min-width="120">
          <template #default="{ row }">
            <el-tag v-if="row.isWithdraw" type="info">已撤回</el-tag>
            <el-tag v-else :type="statusType(row.status)">{{ statusLabels[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="190" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="showDetail(row, 'event')">查看详情</el-button>
            <el-button v-if="row.status === 'PENDING' && !row.isWithdraw" type="danger" link @click="handleWithdraw(row)">撤回上报</el-button>
            <el-button v-if="row.status === 'REJECTED'" type="warning" link @click="openResubmit(row)">补充完善</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-table v-else :data="rows" v-loading="loading" empty-text="暂无已完成任务" style="width: 100%">
        <el-table-column prop="taskNo" label="任务编号" min-width="150" />
        <el-table-column prop="taskName" label="任务名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="source" label="任务来源" min-width="120" />
        <el-table-column prop="type" label="任务类型" min-width="150">
          <template #default="{ row }">{{ eventTypeLabels[row.type] || row.type }}</template>
        </el-table-column>
        <el-table-column prop="stationName" label="所属车站" min-width="130" />
        <el-table-column prop="completedTime" label="完成时间" min-width="180">
          <template #default="{ row }">{{ formatTime(row.completedTime) }}</template>
        </el-table-column>
        <el-table-column prop="durationMinutes" label="处置耗时" min-width="140">
          <template #default="{ row }">{{ formatDuration(row.durationMinutes) }}</template>
        </el-table-column>
        <el-table-column prop="evaluation" label="评价" min-width="140">
          <template #default="{ row }">{{ row.evaluation || '待评价' }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="showDetail(row, 'task')">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          :current-page="currentFilter.page"
          :page-size="currentFilter.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="detailVisible"
      :title="detailKind === 'event' ? '事件详情' : '任务详情'"
      width="640px"
    >
      <el-descriptions :column="2" border>
        <template v-if="detailKind === 'event'">
          <el-descriptions-item label="事件编号">{{ detail.eventNo }}</el-descriptions-item>
          <el-descriptions-item label="事件标题">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="事件类型">{{ eventTypeLabels[detail.eventType] || detail.eventType }}</el-descriptions-item>
          <el-descriptions-item label="所属车站">{{ detail.stationName }}</el-descriptions-item>
          <el-descriptions-item label="故障设备">{{ detail.faultyDevice || '—' }}</el-descriptions-item>
          <el-descriptions-item label="处理状态">{{ statusLabels[detail.status] || detail.status }}</el-descriptions-item>
          <el-descriptions-item label="上报时间">{{ formatTime(detail.createTime) }}</el-descriptions-item>
          <el-descriptions-item label="事件描述" :span="2">{{ detail.description || '—' }}</el-descriptions-item>
          <el-descriptions-item label="AI研判依据" :span="2">{{ detail.aiReason || '—' }}</el-descriptions-item>
          <el-descriptions-item label="AI处置预案" :span="2"><div class="pre-line">{{ detail.aiPlan || '—' }}</div></el-descriptions-item>
          <el-descriptions-item v-if="imageList(detail.imageUrls).length" label="现场图片" :span="2">
            <el-image
              v-for="url in imageList(detail.imageUrls)"
              :key="url"
              :src="url"
              :preview-src-list="imageList(detail.imageUrls)"
              fit="cover"
              class="detail-image"
            />
          </el-descriptions-item>
        </template>
        <template v-else>
          <el-descriptions-item label="任务编号">{{ detail.taskNo }}</el-descriptions-item>
          <el-descriptions-item label="任务来源">{{ detail.source || '—' }}</el-descriptions-item>
          <el-descriptions-item label="任务类型">{{ eventTypeLabels[detail.type] || detail.type }}</el-descriptions-item>
          <el-descriptions-item label="所属车站">{{ detail.stationName }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatTime(detail.completedTime) }}</el-descriptions-item>
          <el-descriptions-item label="处置耗时">{{ formatDuration(detail.durationMinutes) }}</el-descriptions-item>
          <el-descriptions-item label="任务内容" :span="2">{{ detail.taskName }}</el-descriptions-item>
          <el-descriptions-item label="评价" :span="2">{{ detail.evaluation || '待评价' }}</el-descriptions-item>
        </template>
      </el-descriptions>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="resubmitVisible" title="补充完善被驳回的险情" width="580px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="您的险情上报已被车站管理员驳回，请补充完善描述与现场图片后重新提交。"
      />
      <el-form class="resubmit-form" label-width="100px">
        <el-form-item label="事件标题">
          <el-input v-model="resubmitForm.eventTitle" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="故障设备">
          <el-input v-model="resubmitForm.faultyDevice" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="事件描述" required>
          <el-input
            v-model="resubmitForm.description"
            type="textarea"
            :rows="5"
            maxlength="1000"
            show-word-limit
            placeholder="请补充更详细的事件描述"
          />
        </el-form-item>
        <el-form-item label="现场图片">
          <el-upload
            v-model:file-list="resubmitFiles"
            action="#"
            list-type="picture-card"
            accept="image/jpeg,image/png,image/webp"
            :auto-upload="false"
            :limit="5"
            :on-change="onResubmitFileChange"
            :on-exceed="onResubmitFileExceed"
          >
            <span class="upload-plus">+</span>
          </el-upload>
          <div class="upload-tip">最多5张，单张不超过5MB</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resubmitVisible = false">取消</el-button>
        <el-button type="primary" :loading="resubmitSubmitting" @click="submitResubmit">补充并重新提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.history-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0; color: var(--metro-text-primary); font-size: 22px; font-weight: 600; }
.page-desc { display: block; margin-top: 4px; color: var(--metro-text-muted); font-size: 13px; }
.table-card { border: 1px solid var(--metro-border); background: var(--metro-bg-card); }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }
.keyword { width: 250px; }
.date-range { width: 380px; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.detail-image { width: 96px; height: 96px; margin: 0 8px 8px 0; border-radius: 4px; }
.pre-line { white-space: pre-line; }
.resubmit-form { margin-top: 14px; }
.resubmit-form .el-upload__tip { line-height: 1.4; }
/* 表格主体允许横向滚动：容器宽度不足时不再压缩各列，避免内容被固定操作列遮挡 */
.table-card :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}
@media (max-width: 768px) {
  .keyword, .date-range { width: 100%; }
}
</style>
