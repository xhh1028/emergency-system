<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 车站管理员 - 安保值守（前端 mock：查看本站安保点位值守情况，支持签到确认）
const watchList = ref([])
const keyword = ref('')

// mock：本站安保值守点位
const MOCK_WATCH = [
  { id: 1, post: 'A口安检处', personnel: '周安保', shift: '早班', startTime: '08:00', endTime: '16:00', status: 'on_duty', checkedIn: true },
  { id: 2, post: 'B口安检处', personnel: '赵安保', shift: '早班', startTime: '08:00', endTime: '16:00', status: 'on_duty', checkedIn: true },
  { id: 3, post: '站台B端巡逻区', personnel: '李执行', shift: '中班', startTime: '16:00', endTime: '00:00', status: 'on_duty', checkedIn: false },
  { id: 4, post: '站厅C区巡逻点', personnel: '陈执行', shift: '中班', startTime: '16:00', endTime: '00:00', status: 'pending', checkedIn: false },
  { id: 5, post: '站台北端岗亭', personnel: '周安保', shift: '夜班', startTime: '00:00', endTime: '08:00', status: 'rest', checkedIn: false }
]

const statusLabelMap = { on_duty: '值守中', pending: '待上岗', rest: '轮休' }
const statusTagMap = { on_duty: 'success', pending: 'warning', rest: 'info' }

const filteredList = computed(() => {
  return watchList.value.filter(item => {
    const matchKw = !keyword.value || item.post.includes(keyword.value) || item.personnel.includes(keyword.value)
    return matchKw
  })
})

function handleCheckIn(row) {
  row.checkedIn = true
  row.status = 'on_duty'
  ElMessage.success(`${row.personnel} 已在 ${row.post} 签到确认`)
}

function loadData() {
  watchList.value = MOCK_WATCH.map(item => ({ ...item }))
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="watch-page">
    <div class="page-header">
      <h2>安保值守</h2>
      <span class="page-desc">查看本站安保点位值守情况，确认签到</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索值守点或人员" clearable style="width: 220px" />
      </div>

      <el-table :data="filteredList" stripe border style="width: 100%">
        <el-table-column prop="post" label="值守点位" min-width="160" />
        <el-table-column prop="personnel" label="值守人员" width="120" />
        <el-table-column prop="shift" label="班次" width="90" />
        <el-table-column prop="startTime" label="开始时间" width="110" />
        <el-table-column prop="endTime" label="结束时间" width="110" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status]" size="small">{{ statusLabelMap[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="签到" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.checkedIn" type="success" size="small">已签到</el-tag>
            <el-tag v-else type="info" size="small">未签到</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button
              v-if="!row.checkedIn && row.status !== 'rest'"
              type="primary" size="small" @click="handleCheckIn(row)"
            >确认签到</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.watch-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.table-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>