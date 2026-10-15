<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import { decideStationEvent, getStationEventDetail, getStationEvents, rejectStationEvent } from '@/api/station'
import { withdrawEvent } from '@/api/event'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const deciding = ref(false)
const rejecting = ref(false)
const rejectVisible = ref(false)
const rejectReason = ref('')
const rejectTarget = ref(null)
const rows = ref([])
const total = ref(0)
const detailVisible = ref(false)
const selectedEvent = ref(null)
const filter = reactive({ status: 'ALL', keyword: '', page: 1, size: 10 })
const decision = reactive({ level: '', route: '' })

const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}
const levelLabels = {
  GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '非常严重', UNCONFIRMED: '待确认'
}
const statusLabels = {
  PENDING: '待处理', CONFIRMED: '已确认', REJECTED: '已驳回',
  PENDING_ASSIGN: '待复核', STATION_HANDLE: '站内处置中',
  REPORTED_TO_DISPATCH: '已上报调度', FINISHED: '已闭环'
}
const canDecide = computed(() => ['PENDING', 'CONFIRMED'].includes(selectedEvent.value?.status))
// 当前登录用户ID：仅本人发起的事件可撤回
const currentUserId = computed(() => userStore.userInfo?.id)

// 撤回自己发起、待处理状态的事件（逻辑删除，写日志留痕）
async function handleWithdraw(row) {
  try {
    await ElMessageBox.confirm(
      `确认撤回事件 ${row.eventNo} 吗？撤回后该事件将从事件待办中隐藏，不可恢复。`,
      '撤回事件',
      { type: 'warning', confirmButtonText: '确认撤回', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await withdrawEvent(row.id)
    ElMessage.success('事件已撤回')
    await loadEvents()
  } catch {
    // 业务错误（如"事件已经被处理，不允许撤回"）由公共请求层提示
  }
}

// 普通险情驳回：写明理由退回一线补全信息（紧急险情禁止驳回）
function openReject(row) {
  rejectTarget.value = row
  rejectReason.value = ''
  rejectVisible.value = true
}

async function submitReject() {
  if (!rejectReason.value.trim()) {
    ElMessage.warning('请填写驳回理由')
    return
  }
  rejecting.value = true
  try {
    await rejectStationEvent(rejectTarget.value.id, { reason: rejectReason.value.trim() })
    ElMessage.success('已驳回，事件退回一线补全信息')
    rejectVisible.value = false
    detailVisible.value = false
    await loadEvents()
  } finally {
    rejecting.value = false
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const response = await getStationEvents(filter)
    rows.value = response.data?.list || []
    total.value = response.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  const response = await getStationEventDetail(row.id)
  selectedEvent.value = response.data
  decision.level = response.data.aiLevel || 'GENERAL'
  decision.route = decision.level === 'GENERAL' ? 'TASK_ASSIGN' : 'DISPATCH'
  detailVisible.value = true
}

async function confirmAi(row) {
  const level = row.aiLevel || 'GENERAL'
  await submitDecision(row.id, level, level === 'GENERAL' ? 'TASK_ASSIGN' : 'DISPATCH')
}

async function submitManualDecision() {
  if (!decision.level || !decision.route) {
    ElMessage.warning('请选择人工复核等级和后续处置路径')
    return
  }
  await submitDecision(selectedEvent.value.id, decision.level, decision.route)
}

async function submitDecision(id, level, route) {
  deciding.value = true
  try {
    const response = await decideStationEvent(id, { level, route })
    ElMessage.success(route === 'TASK_ASSIGN' ? '已确认，进入站内任务分配' : '已确认，事件已同步上报调度')
    detailVisible.value = false
    await loadEvents()
    router.push(response.data.nextPath)
  } finally {
    deciding.value = false
  }
}

function search() {
  filter.page = 1
  loadEvents()
}

function reset() {
  filter.status = 'ALL'
  filter.keyword = ''
  filter.page = 1
  loadEvents()
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ') : '—'
}

function images(urls) {
  return urls ? String(urls).split(';').filter(Boolean) : []
}

function levelTag(level) {
  if (level === 'EXTREMELY_SERIOUS') return 'danger'
  if (level === 'SERIOUS') return 'warning'
  return 'success'
}

onMounted(loadEvents)
</script>

<template>
  <div class="todo-page">
    <div class="page-header">
      <h2>事件待办</h2>
      <span class="page-desc">一线上报后系统立即完成 AI 初判，车站管理员在此人工复核处置路径。</span>
    </div>

    <el-card shadow="hover">
      <div class="toolbar">
        <el-select v-model="filter.status" style="width: 160px" @change="search">
          <el-option label="全部状态" value="ALL" />
          <el-option label="待处理" value="PENDING" />
          <el-option label="已确认" value="CONFIRMED" />
          <el-option label="已驳回" value="REJECTED" />
          <el-option label="站内处置中" value="STATION_HANDLE" />
          <el-option label="已上报调度" value="REPORTED_TO_DISPATCH" />
          <el-option label="已闭环" value="FINISHED" />
        </el-select>
        <el-input
          v-model="filter.keyword"
          placeholder="搜索事件编号、类型、描述或上报人"
          clearable
          class="keyword"
          @keyup.enter="search"
          @clear="search"
        />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" empty-text="当前暂无事件待办" style="width: 100%">
        <el-table-column label="事件编号" width="210">
          <template #default="{ row }">
            <div class="event-no-cell">
              <span>{{ row.eventNo }}</span>
              <el-tag v-if="row.isEmergency" type="danger" size="small">紧急</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="eventType" label="事件类型" width="170">
          <template #default="{ row }">{{ typeLabels[row.eventType] || row.eventType }}</template>
        </el-table-column>
        <el-table-column prop="reporterName" label="上报人" width="110" />
        <el-table-column prop="createTime" label="上报时间" min-width="180">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column prop="aiLevel" label="AI预判事件等级" width="150">
          <template #default="{ row }">
            <el-tag :type="levelTag(row.aiLevel)">{{ levelLabels[row.aiLevel] || '待研判' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }">{{ statusLabels[row.status] || row.status }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
            <el-button
              v-if="row.status === 'PENDING' && row.reporterId === currentUserId"
              link
              type="danger"
              @click="handleWithdraw(row)"
            >撤回</el-button>
            <el-button
              v-if="!row.isEmergency && row.status === 'PENDING'"
              link
              type="warning"
              @click="openReject(row)"
            >驳回</el-button>
            <el-button
              v-if="['PENDING', 'CONFIRMED'].includes(row.status)"
              link
              type="success"
              :loading="deciding"
              @click="confirmAi(row)"
            >确认AI判定</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="filter.page"
          v-model:page-size="filter.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadEvents"
          @size-change="search"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="事件详情与人工复核" width="760px">
      <template v-if="selectedEvent">
        <el-alert
          v-if="selectedEvent.status === 'REJECTED'"
          type="warning"
          :closable="false"
          show-icon
          :title="`该事件已被驳回：${selectedEvent.rejectReason || '未填写理由'}`"
          class="reject-alert"
        />
        <el-descriptions :column="2" border>
          <el-descriptions-item label="事件编号">{{ selectedEvent.eventNo }}</el-descriptions-item>
          <el-descriptions-item label="紧急标记">
            <el-tag v-if="selectedEvent.isEmergency" type="danger" size="small">紧急险情</el-tag>
            <el-tag v-else type="info" size="small">普通险情</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="事件标题">{{ selectedEvent.title }}</el-descriptions-item>
          <el-descriptions-item label="事发车站">{{ selectedEvent.stationName }}</el-descriptions-item>
          <el-descriptions-item label="事件类型">{{ typeLabels[selectedEvent.eventType] }}</el-descriptions-item>
          <el-descriptions-item label="上报人员">{{ selectedEvent.reporterName }}</el-descriptions-item>
          <el-descriptions-item label="AI预判">
            <el-tag :type="levelTag(selectedEvent.aiLevel)">{{ levelLabels[selectedEvent.aiLevel] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="事件描述" :span="2">{{ selectedEvent.description }}</el-descriptions-item>
          <el-descriptions-item label="故障设备" :span="2">{{ selectedEvent.faultyDevice || '—' }}</el-descriptions-item>
          <el-descriptions-item label="AI研判来源">{{ selectedEvent.aiSource === 'LLM' ? '大模型' : '本地安全规则降级' }}</el-descriptions-item>
          <el-descriptions-item label="AI研判依据">{{ selectedEvent.aiReason || '—' }}</el-descriptions-item>
          <el-descriptions-item label="AI生成处置预案" :span="2"><div class="plan-content">{{ selectedEvent.aiPlan || '—' }}</div></el-descriptions-item>
          <el-descriptions-item v-if="images(selectedEvent.imageUrls).length" label="现场图片" :span="2">
            <el-image
              v-for="url in images(selectedEvent.imageUrls)"
              :key="url"
              :src="url"
              :preview-src-list="images(selectedEvent.imageUrls)"
              class="event-image"
              fit="cover"
            />
          </el-descriptions-item>
        </el-descriptions>

        <div class="plan-panel">
          <h3>AI匹配应急预案</h3>
          <el-collapse v-if="selectedEvent.plans?.length">
            <el-collapse-item v-for="plan in selectedEvent.plans" :key="plan.id" :title="`${plan.name}（${plan.level}）`">
              <div class="plan-content">{{ plan.content }}</div>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-else description="暂无匹配预案" :image-size="60" />
        </div>

        <el-alert
          v-if="canDecide"
          title="如不采纳 AI 判断，可在下方手动修改等级和处置路径。"
          type="info"
          :closable="false"
          show-icon
        />
        <el-form v-if="canDecide" class="decision-form" label-width="120px">
          <el-form-item label="人工复核等级">
            <el-select v-model="decision.level" style="width: 240px">
              <el-option label="一般" value="GENERAL" />
              <el-option label="严重" value="SERIOUS" />
              <el-option label="非常严重" value="EXTREMELY_SERIOUS" />
            </el-select>
          </el-form-item>
          <el-form-item label="后续处置路径">
            <el-radio-group v-model="decision.route">
              <el-radio value="TASK_ASSIGN">站内任务分配</el-radio>
              <el-radio value="DISPATCH">上报调度中心</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="canDecide" type="primary" :loading="deciding" @click="submitManualDecision">提交人工复核</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="驳回事件" width="500px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="普通险情可驳回退回一线补全信息；紧急险情禁止驳回，避免延误应急处置。"
      />
      <div class="reject-form">
        <el-input
          v-model="rejectReason"
          type="textarea"
          :rows="4"
          maxlength="500"
          show-word-limit
          placeholder="请写明驳回理由，例如：事件描述过于简略、现场图片模糊，请补充后重新提交"
        />
      </div>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="warning" :loading="rejecting" @click="submitReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.todo-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0; font-size: 22px; color: var(--metro-text-primary); }
.page-desc { display: block; margin-top: 5px; color: var(--metro-text-muted); font-size: 13px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.keyword { width: 320px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.event-image { width: 96px; height: 96px; margin-right: 8px; border-radius: 4px; }
.plan-panel { margin: 20px 0; }
.plan-panel h3 { margin: 0 0 12px; font-size: 16px; }
.plan-content { white-space: pre-wrap; line-height: 1.8; }
.decision-form { margin-top: 18px; }
.event-no-cell { display: flex; align-items: center; gap: 8px; }
.reject-alert { margin-bottom: 14px; }
.reject-form { margin-top: 14px; }
</style>
