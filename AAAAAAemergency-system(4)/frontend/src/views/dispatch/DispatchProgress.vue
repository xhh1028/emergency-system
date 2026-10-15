<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { evaluateDispatchTask, getDispatchProgress, getDispatchStations } from '@/api/dispatch'

const loading = ref(false)
const rows = ref([])
const stations = ref([])
const total = ref(0)
const evaluationVisible = ref(false)
const evaluationSubmitting = ref(false)
const evaluationTask = ref(null)
const evaluationText = ref('')
const filter = reactive({ stationId: null, status: 'ALL', keyword: '', page: 1, size: 10 })
const statusLabels = { PENDING: '待执行', IN_PROGRESS: '进行中', COMPLETED: '已完成', OVERDUE: '已逾期' }
const statusTypes = { PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', OVERDUE: 'danger' }
const sourceLabels = { STATION: '车站安排', DISPATCH: '调度指令' }
const counts = computed(() => ({
  total: total.value,
  pending: rows.value.filter(item => item.status === 'PENDING').length,
  running: rows.value.filter(item => item.status === 'IN_PROGRESS').length,
  completed: rows.value.filter(item => item.status === 'COMPLETED').length
}))
async function load() { loading.value = true; try { const response = await getDispatchProgress(filter); rows.value = response.data?.list || []; total.value = response.data?.total || 0 } finally { loading.value = false } }
async function init() { stations.value = (await getDispatchStations()).data || []; await load() }
function search() { filter.page = 1; load() }
function formatTime(value) { return value ? String(value).replace('T',' ') : '—' }
function openEvaluation(row) {
  evaluationTask.value = row
  evaluationText.value = row.evaluation || ''
  evaluationVisible.value = true
}
async function submitEvaluation() {
  const value = evaluationText.value.trim()
  if (!value) return ElMessage.warning('请填写任务评价')
  evaluationSubmitting.value = true
  try {
    await evaluateDispatchTask(evaluationTask.value.id, value)
    ElMessage.success('任务评价已保存')
    evaluationVisible.value = false
    await load()
  } finally { evaluationSubmitting.value = false }
}
onMounted(init)
</script>

<template>
  <div class="progress-page">
    <div class="page-header"><h2>全线处置进度</h2><span class="page-desc">汇总各车站产生的全部真实 task 工单，监督全网应急处置进展。</span></div>
    <div class="stat-row"><el-card shadow="hover"><strong>{{counts.total}}</strong><span>任务总数</span></el-card><el-card shadow="hover"><strong>{{counts.pending}}</strong><span>本页待执行</span></el-card><el-card shadow="hover"><strong>{{counts.running}}</strong><span>本页进行中</span></el-card><el-card shadow="hover"><strong>{{counts.completed}}</strong><span>本页已完成</span></el-card></div>
    <el-card shadow="hover">
      <div class="toolbar"><el-select v-model="filter.stationId" placeholder="全部车站" clearable style="width:180px" @change="search"><el-option v-for="item in stations" :key="item.id" :label="`${item.line}号线 ${item.name}`" :value="item.id"/></el-select><el-select v-model="filter.status" style="width:140px" @change="search"><el-option label="全部状态" value="ALL"/><el-option label="待执行" value="PENDING"/><el-option label="进行中" value="IN_PROGRESS"/><el-option label="已完成" value="COMPLETED"/><el-option label="已逾期" value="OVERDUE"/></el-select><el-input v-model="filter.keyword" placeholder="搜索车站、事件、任务或执行人" clearable class="keyword" @keyup.enter="search" @clear="search"/><el-button type="primary" @click="search">查询</el-button></div>
      <el-table :data="rows" v-loading="loading" empty-text="暂无全线任务" style="width: 100%"><el-table-column prop="stationName" label="车站" width="135"/><el-table-column prop="eventNo" label="所属事件" width="195"/><el-table-column prop="content" label="执行任务" min-width="240" show-overflow-tooltip/><el-table-column label="来源" width="110"><template #default="{row}">{{sourceLabels[row.source]||row.source}}</template></el-table-column><el-table-column prop="executorName" label="执行人员" width="110"/><el-table-column prop="postName" label="岗位" width="140"/><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusTypes[row.status]">{{statusLabels[row.status]||row.status}}</el-tag></template></el-table-column><el-table-column label="最新反馈" width="180"><template #default="{row}">{{formatTime(row.latestFeedbackTime)}}</template></el-table-column><el-table-column label="任务评价" min-width="150" show-overflow-tooltip><template #default="{row}">{{row.evaluation||'待评价'}}</template></el-table-column><el-table-column label="操作" min-width="120" fixed="right"><template #default="{row}"><el-button v-if="row.rawStatus==='COMPLETED'" type="primary" link @click="openEvaluation(row)">{{row.evaluation?'修改评价':'评价'}}</el-button><span v-else>—</span></template></el-table-column></el-table>
      <div class="pagination"><el-pagination v-model:current-page="filter.page" v-model:page-size="filter.size" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="search"/></div>
    </el-card>
    <el-dialog v-model="evaluationVisible" title="任务评价" width="520px">
      <el-descriptions v-if="evaluationTask" :column="1" border class="evaluation-info">
        <el-descriptions-item label="任务编号">TK-{{ String(evaluationTask.id).padStart(8, '0') }}</el-descriptions-item>
        <el-descriptions-item label="执行人员">{{ evaluationTask.executorName }}</el-descriptions-item>
        <el-descriptions-item label="任务内容">{{ evaluationTask.content }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="evaluationText" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="请填写完成质量、响应速度和改进建议" />
      <template #footer><el-button @click="evaluationVisible=false">取消</el-button><el-button type="primary" :loading="evaluationSubmitting" @click="submitEvaluation">保存评价</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>.progress-page{min-height:100%}.page-header{margin-bottom:24px}.page-header h2{margin:0;font-size:22px}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}.stat-row :deep(.el-card__body){display:flex;flex-direction:column;align-items:center}.stat-row strong{font-size:28px}.stat-row span{font-size:12px;color:var(--metro-text-muted)}.toolbar{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}.keyword{width:330px}.pagination{display:flex;justify-content:flex-end;margin-top:16px}.evaluation-info{margin-bottom:16px}</style>
