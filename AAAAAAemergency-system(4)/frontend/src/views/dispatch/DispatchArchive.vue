<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getDispatchArchive, getDispatchArchiveYears, getDispatchEventDetail } from '@/api/dispatch'

const loading = ref(false)
const detailLoading = ref(false)
const rows = ref([])
const total = ref(0)
const years = ref([])
const detailVisible = ref(false)
const detail = ref(null)
const filter = reactive({ keyword: '', level: 'ALL', year: undefined, page: 1, size: 10 })

const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}
const levelLabels = {
  IV_GENERAL: 'Ⅳ级（一般）', III_MAJOR: 'Ⅲ级（重大）',
  II_SERIOUS: 'Ⅱ级（严重）', I_EXTREMELY_SERIOUS: 'Ⅰ级（特别严重）',
  GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '非常严重'
}
const levelTypes = {
  IV_GENERAL: 'info', III_MAJOR: 'warning', II_SERIOUS: 'danger', I_EXTREMELY_SERIOUS: 'danger',
  GENERAL: 'info', SERIOUS: 'warning', EXTREMELY_SERIOUS: 'danger'
}
const sourceLabels = { STATION: '车站分派', DISPATCH: '调度指令' }

async function loadArchive() {
  loading.value = true
  try {
    const response = await getDispatchArchive(filter)
    rows.value = response.data?.list || []
    total.value = response.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function loadYears() {
  const response = await getDispatchArchiveYears()
  years.value = response.data || []
}

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  try { detail.value = (await getDispatchEventDetail(row.id)).data }
  finally { detailLoading.value = false }
}

function search() { filter.page = 1; loadArchive() }
function reset() { Object.assign(filter, { keyword: '', level: 'ALL', year: undefined, page: 1 }); loadArchive() }
function formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '—' }
function images(value) { return String(value || '').split(';').map(item => item.trim()).filter(Boolean) }

onMounted(async () => { await Promise.all([loadArchive(), loadYears()]) })
</script>

<template>
  <div class="archive-page">
    <div class="page-header">
      <h2>事件归档</h2>
      <span>只读查阅调度已关闭的真实事件、指令、任务和现场反馈</span>
    </div>

    <el-card shadow="never" class="table-card">
      <div class="summary"><strong>{{ total }}</strong><span>条已归档事件</span></div>
      <div class="toolbar">
        <el-input v-model="filter.keyword" placeholder="搜索事件编号、车站、上报人或描述" clearable @keyup.enter="search" @clear="search" />
        <el-select v-model="filter.level" @change="search">
          <el-option label="全部等级" value="ALL" />
          <el-option label="Ⅳ级（一般）" value="IV_GENERAL" />
          <el-option label="Ⅲ级（重大）" value="III_MAJOR" />
          <el-option label="Ⅱ级（严重）" value="II_SERIOUS" />
          <el-option label="Ⅰ级（特别严重）" value="I_EXTREMELY_SERIOUS" />
        </el-select>
        <el-select v-model="filter.year" placeholder="全部年份" clearable @change="search">
          <el-option v-for="year in years" :key="year" :label="`${year}年`" :value="year" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" empty-text="暂无已归档事件" style="width: 100%">
        <el-table-column prop="eventNo" label="事件编号" width="195" />
        <el-table-column prop="stationName" label="车站" min-width="120" />
        <el-table-column label="类型" min-width="150"><template #default="{ row }">{{ typeLabels[row.eventType] || row.eventType }}</template></el-table-column>
        <el-table-column label="法定等级" width="145"><template #default="{ row }"><el-tag :type="levelTypes[row.finalLevel]">{{ levelLabels[row.finalLevel] || row.finalLevel }}</el-tag></template></el-table-column>
        <el-table-column label="任务闭环" width="105"><template #default="{ row }">{{ row.completedCount }}/{{ row.taskCount }}</template></el-table-column>
        <el-table-column prop="commandCount" label="历史指令" width="90" />
        <el-table-column label="发生时间" min-width="175"><template #default="{ row }">{{ formatTime(row.createTime) }}</template></el-table-column>
        <el-table-column label="最后反馈" min-width="175"><template #default="{ row }">{{ formatTime(row.closedTime) }}</template></el-table-column>
        <el-table-column label="操作" min-width="120" fixed="right"><template #default="{ row }"><el-button type="primary" link @click="openDetail(row)">查看详情</el-button></template></el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="filter.page" v-model:page-size="filter.size" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @current-change="loadArchive" @size-change="search" /></div>
    </el-card>

    <el-dialog v-model="detailVisible" title="归档事件完整记录" width="860px">
      <div v-loading="detailLoading">
        <el-descriptions v-if="detail" :column="2" border>
          <el-descriptions-item label="事件编号">{{ detail.eventNo }}</el-descriptions-item>
          <el-descriptions-item label="所属车站">{{ detail.lineName }}号线 {{ detail.stationName }}</el-descriptions-item>
          <el-descriptions-item label="事件类型">{{ typeLabels[detail.eventType] || detail.eventType }}</el-descriptions-item>
          <el-descriptions-item label="法定等级">{{ levelLabels[detail.finalLevel] || detail.finalLevel }}</el-descriptions-item>
          <el-descriptions-item label="上报人员">{{ detail.reporterName }}</el-descriptions-item>
          <el-descriptions-item label="发生时间">{{ formatTime(detail.createTime) }}</el-descriptions-item>
          <el-descriptions-item label="事件描述" :span="2"><div class="description">{{ detail.description }}</div></el-descriptions-item>
          <el-descriptions-item v-if="images(detail.imageUrls).length" label="原始现场图片" :span="2"><el-image v-for="url in images(detail.imageUrls)" :key="url" :src="url" :preview-src-list="images(detail.imageUrls)" class="image" fit="cover" preview-teleported /></el-descriptions-item>
        </el-descriptions>

        <section v-if="detail?.commands?.length" class="detail-section">
          <h3>调度指令记录</h3>
          <el-timeline><el-timeline-item v-for="command in detail.commands" :key="command.id" :timestamp="formatTime(command.sendTime)"><strong>{{ command.sender }}</strong>：{{ command.content }} <el-tag size="small" :type="command.read ? 'success' : 'warning'">{{ command.read ? '已签收' : '未签收' }}</el-tag></el-timeline-item></el-timeline>
        </section>

        <section class="detail-section">
          <h3>任务及现场反馈（{{ detail?.tasks?.length || 0 }}）</h3>
          <el-collapse v-if="detail?.tasks?.length">
            <el-collapse-item v-for="task in detail.tasks" :key="task.id" :title="`${task.taskNo} · ${task.content}`">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="来源">{{ sourceLabels[task.source] || task.source }}</el-descriptions-item>
                <el-descriptions-item label="执行人">{{ task.executorName }} · {{ task.postName }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ task.status }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ formatTime(task.createTime) }}</el-descriptions-item>
              </el-descriptions>
              <el-timeline v-if="task.feedback?.length" class="feedback-list">
                <el-timeline-item v-for="feedback in task.feedback" :key="feedback.id" :timestamp="formatTime(feedback.createTime)">
                  <strong>{{ feedback.operatorName }}</strong>：{{ feedback.text }}
                  <div v-if="images(feedback.imageUrls).length" class="feedback-images"><el-image v-for="url in images(feedback.imageUrls)" :key="url" :src="url" :preview-src-list="images(feedback.imageUrls)" class="image" fit="cover" preview-teleported /></div>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else description="该任务没有现场反馈" :image-size="55" />
            </el-collapse-item>
          </el-collapse>
          <el-empty v-else description="该事件没有任务记录" />
        </section>
      </div>
      <template #footer><el-button @click="detailVisible=false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.archive-page{min-height:100%}.page-header{margin-bottom:20px}.page-header h2{margin:0;color:var(--metro-text-primary);font-size:22px}.page-header span{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.table-card{border:1px solid var(--metro-border);background:var(--metro-bg-card)}.summary{display:flex;align-items:baseline;gap:8px;margin-bottom:14px}.summary strong{color:var(--metro-accent);font-size:28px}.summary span{color:var(--metro-text-muted);font-size:13px}.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}.toolbar .el-input{width:340px}.toolbar .el-select{width:170px}.pagination{display:flex;justify-content:flex-end;margin-top:16px}.description{white-space:pre-wrap;line-height:1.7}.detail-section{margin-top:22px}.detail-section h3{margin:0 0 14px;color:var(--metro-text-primary);font-size:15px}.image{width:110px;height:82px;margin:4px 8px 4px 0;border-radius:6px}.feedback-list{margin-top:18px}.feedback-images{margin-top:8px}.archive-page :deep(.el-table__body-wrapper){overflow-x:auto}@media(max-width:700px){.toolbar .el-input,.toolbar .el-select{width:100%}}
</style>
