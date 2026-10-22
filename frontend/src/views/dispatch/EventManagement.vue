<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import { closeDispatchEvent, confirmDispatchEvent, getDispatchEventDetail, getDispatchEvents } from '@/api/dispatch'
import { withdrawEvent } from '@/api/event'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const actionLoading = ref(false)
const rows = ref([])
const total = ref(0)
const detail = ref(null)
const detailVisible = ref(false)
const filter = reactive({ status: 'ALL', keyword: '', page: 1, size: 10 })
const statusLabels = { PENDING: '待处理', PENDING_ASSIGN: '车站待复核', STATION_HANDLE: '车站自主处置中', REPORTED_TO_DISPATCH: '已上报调度', FINISHED: '已关闭' }
const statusTypes = { PENDING: 'warning', PENDING_ASSIGN: 'info', STATION_HANDLE: 'primary', REPORTED_TO_DISPATCH: 'warning', FINISHED: 'success' }
const levelLabels = { GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '非常严重', UNCONFIRMED: '未确认', DISPATCH_CONFIRMED: '调度已阅' }
const typeLabels = { DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件', TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件', DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件' }

async function loadEvents() {
  loading.value = true
  try { const response = await getDispatchEvents(filter); rows.value = response.data?.list || []; total.value = response.data?.total || 0 }
  finally { loading.value = false }
}
async function openDetail(row) { detail.value = (await getDispatchEventDetail(row.id)).data; detailVisible.value = true }
async function confirm(row) {
  actionLoading.value = true
  try { await confirmDispatchEvent(row.id); ElMessage.success('已确认知悉该险情，现可下发指令'); await loadEvents(); if (detailVisible.value) await openDetail(row) }
  finally { actionLoading.value = false }
}
function issue(row) { router.push({ path: '/dispatch/command', query: { eventId: row.id } }) }
async function closeEvent(row) {
  try { await ElMessageBox.confirm('确认所有处置工作已闭环并关闭该事件吗？', '关闭事件', { type: 'warning' }) }
  catch { return }
  actionLoading.value = true
  try { await closeDispatchEvent(row.id); ElMessage.success('事件已关闭并进入归档状态'); detailVisible.value = false; await loadEvents() }
  finally { actionLoading.value = false }
}
function search() { filter.page = 1; loadEvents() }
function formatTime(value) { return value ? String(value).replace('T', ' ') : '—' }
function images(value) { return String(value || '').split(';').map(v => v.trim()).filter(Boolean) }
function canClose(row) { return row.status !== 'FINISHED' && row.taskCount > 0 && row.completedCount === row.taskCount }
// 当前登录用户ID：仅本人发起的事件可撤回
const currentUserId = computed(() => userStore.userInfo?.id)

// 撤回自己发起、待处理状态的事件（逻辑删除，写日志留痕）
async function handleWithdraw(row) {
  try {
    await ElMessageBox.confirm(
      `确认撤回事件 ${row.eventNo} 吗？撤回后该事件将从待办中隐藏，不可恢复。`,
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
async function openQueryEvent() {
  const eventId = Number(route.query.eventId || 0)
  if (eventId) await openDetail({ id: eventId })
}
onMounted(async () => { await loadEvents(); await openQueryEvent() })
watch(() => route.query.eventId, openQueryEvent)
</script>

<template>
  <div class="event-page">
    <div class="page-header"><h2>事件管理</h2><span class="page-desc">统一监督车站自主处置事件，并确认、下发严重事件处置指令。</span></div>
    <el-card shadow="hover">
      <div class="toolbar">
        <el-select v-model="filter.status" style="width:190px" @change="search"><el-option label="全部事件" value="ALL"/><el-option label="待处理" value="PENDING"/><el-option label="车站待复核" value="PENDING_ASSIGN"/><el-option label="车站自主处置中" value="STATION_HANDLE"/><el-option label="已上报调度" value="REPORTED_TO_DISPATCH"/><el-option label="已关闭" value="FINISHED"/></el-select>
        <el-input v-model="filter.keyword" placeholder="搜索事件编号、车站、上报人或描述" clearable class="keyword" @keyup.enter="search" @clear="search"/><el-button type="primary" @click="search">查询</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" empty-text="暂无进入调度范围的事件" style="width: 100%">
        <el-table-column prop="eventNo" label="事件编号" width="195"/><el-table-column prop="stationName" label="事发车站" width="135"/><el-table-column label="事件类型" width="165"><template #default="{row}">{{ typeLabels[row.eventType] || row.eventType }}</template></el-table-column>
        <el-table-column label="AI等级" width="110"><template #default="{row}"><el-tag :type="row.aiLevel==='GENERAL'?'success':'danger'">{{ levelLabels[row.aiLevel] || row.aiLevel }}</el-tag></template></el-table-column>
        <el-table-column label="调度确认" width="110"><template #default="{row}"><el-tag v-if="row.status==='REPORTED_TO_DISPATCH'" :type="row.dispatchConfirmed?'success':'warning'">{{ row.dispatchConfirmed?'已阅':'待确认' }}</el-tag><span v-else>—</span></template></el-table-column>
        <el-table-column label="状态" width="145"><template #default="{row}"><el-tag :type="statusTypes[row.status]">{{ statusLabels[row.status] }}</el-tag></template></el-table-column>
        <el-table-column label="任务闭环" width="105"><template #default="{row}">{{ row.completedCount }}/{{ row.taskCount }}</template></el-table-column>
        <el-table-column label="上报时间" min-width="180"><template #default="{row}">{{ formatTime(row.createTime) }}</template></el-table-column>
        <el-table-column label="操作" min-width="260" fixed="right"><template #default="{row}"><el-button type="primary" link @click="openDetail(row)">详情</el-button><el-button v-if="row.status === 'PENDING' && row.reporterId === currentUserId" type="danger" link @click="handleWithdraw(row)">撤回</el-button><el-button v-if="row.status==='REPORTED_TO_DISPATCH'&&!row.dispatchConfirmed" type="success" link :loading="actionLoading" @click="confirm(row)">确认</el-button><el-button v-if="row.status==='REPORTED_TO_DISPATCH'&&row.dispatchConfirmed" type="warning" link @click="issue(row)">指令下发</el-button><el-button v-if="canClose(row)" type="danger" link @click="closeEvent(row)">关闭</el-button></template></el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="filter.page" v-model:page-size="filter.size" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @current-change="loadEvents" @size-change="search"/></div>
    </el-card>
    <el-dialog v-model="detailVisible" title="调度事件详情" width="780px">
      <el-descriptions v-if="detail" :column="2" border><el-descriptions-item label="事件编号">{{detail.eventNo}}</el-descriptions-item><el-descriptions-item label="事件标题">{{detail.title}}</el-descriptions-item><el-descriptions-item label="事发车站">{{detail.lineName}}号线 {{detail.stationName}}</el-descriptions-item><el-descriptions-item label="故障设备">{{detail.faultyDevice||'—'}}</el-descriptions-item><el-descriptions-item label="上报人员">{{detail.reporterName}}</el-descriptions-item><el-descriptions-item label="上报时间">{{formatTime(detail.createTime)}}</el-descriptions-item><el-descriptions-item label="AI研判">{{levelLabels[detail.aiLevel]||detail.aiLevel}}（{{detail.aiSource==='LLM'?'大模型':'安全规则降级'}}）</el-descriptions-item><el-descriptions-item label="法定等级">{{levelLabels[detail.finalLevel]||detail.finalLevel}}</el-descriptions-item><el-descriptions-item label="调度确认时间">{{formatTime(detail.dispatchConfirmTime)}}</el-descriptions-item><el-descriptions-item label="任务闭环">{{detail.completedCount}} / {{detail.taskCount}}</el-descriptions-item><el-descriptions-item label="AI研判依据">{{detail.aiReason||'—'}}</el-descriptions-item><el-descriptions-item label="事件描述" :span="2"><div class="description">{{detail.description}}</div></el-descriptions-item><el-descriptions-item label="AI生成处置预案" :span="2"><div class="description">{{detail.aiPlan||'—'}}</div></el-descriptions-item><el-descriptions-item v-if="images(detail.imageUrls).length" label="现场图片" :span="2"><el-image v-for="url in images(detail.imageUrls)" :key="url" :src="url" :preview-src-list="images(detail.imageUrls)" class="event-image" fit="cover" preview-teleported/></el-descriptions-item></el-descriptions>
      <div v-if="detail?.commands?.length" class="commands"><h3>历史处置指令</h3><el-timeline><el-timeline-item v-for="item in detail.commands" :key="item.id" :timestamp="formatTime(item.sendTime)"><strong>{{item.sender}}</strong>：{{item.content}} <el-tag size="small" :type="item.read?'success':'warning'">{{item.read?'车站已签收':'待签收'}}</el-tag></el-timeline-item></el-timeline></div>
      <div v-if="detail?.plans?.length" class="commands"><h3>AI匹配处置预案</h3><el-collapse><el-collapse-item v-for="plan in detail.plans" :key="plan.id" :title="`${plan.name}（${plan.level}）`"><div class="description">{{plan.content}}</div></el-collapse-item></el-collapse></div>
      <template #footer><el-button @click="detailVisible=false">关闭</el-button><el-button v-if="detail?.status==='REPORTED_TO_DISPATCH'&&!detail.dispatchConfirmed" type="success" :loading="actionLoading" @click="confirm(detail)">确认已阅</el-button><el-button v-if="detail?.status==='REPORTED_TO_DISPATCH'&&detail.dispatchConfirmed" type="warning" @click="issue(detail)">指令下发</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>.event-page{min-height:100%}.page-header{margin-bottom:24px}.page-header h2{margin:0;font-size:22px}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.toolbar{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}.keyword{width:360px}.pagination{display:flex;justify-content:flex-end;margin-top:16px}.description{white-space:pre-wrap;line-height:1.8}.event-image{width:120px;height:90px;margin-right:10px;border-radius:6px}.commands{margin-top:22px}.commands h3{font-size:15px}</style>
