<script setup>
import { ref, computed, onMounted } from 'vue'

// 车站管理员 - 事件归档（前端 mock：查看本站已结案历史事故记录）
const archiveList = ref([])
const keyword = ref('')
const yearFilter = ref('')

// mock：本站已结案历史记录
const MOCK_ARCHIVE = [
  { id: 1, title: 'B端扶梯骤停事故', station: '人民广场站', level: 'medium', type: '设备故障', happenedTime: '2024-03-15', closedTime: '2024-03-15', summary: '扶梯骤停导致乘客擦伤，维修后恢复', status: 'closed' },
  { id: 2, title: 'A口大客流拥堵事件', station: '人民广场站', level: 'high', type: '客流异常', happenedTime: '2024-05-01', closedTime: '2024-05-01', summary: '晚高峰客流激增，限流后恢复', status: 'closed' },
  { id: 3, title: '乘客站台摔倒受伤', station: '人民广场站', level: 'medium', type: '人员受伤', happenedTime: '2025-04-10', closedTime: '2025-04-10', summary: '乘客在站台摔倒擦伤，送医后恢复', status: 'closed' },
  { id: 4, title: '设备区信号异常事件', station: '人民广场站', level: 'low', type: '设备故障', happenedTime: '2025-08-22', closedTime: '2025-08-22', summary: '信号短暂异常，重启后恢复运行', status: 'closed' }
]

const levelLabelMap = { high: '高危', medium: '中危', low: '低危' }
const levelTagMap = { high: 'danger', medium: 'warning', low: 'info' }

const yearOptions = computed(() => {
  const years = [...new Set(archiveList.value.map(i => i.happenedTime.slice(0, 4)))]
  return years.map(y => ({ label: `${y}年`, value: y }))
})

const filteredList = computed(() => {
  return archiveList.value.filter(item => {
    const matchKw = !keyword.value || item.title.includes(keyword.value)
    const matchYear = !yearFilter.value || item.happenedTime.startsWith(yearFilter.value)
    return matchKw && matchYear
  })
})

function loadData() {
  archiveList.value = MOCK_ARCHIVE.map(item => ({ ...item }))
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="archive-page">
    <div class="page-header">
      <h2>事件归档</h2>
      <span class="page-desc">查看本站已结案的历史事故记录</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索事件名称" clearable style="width: 240px" />
        <el-select v-model="yearFilter" placeholder="选择年份" clearable style="width: 140px">
          <el-option v-for="opt in yearOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>

      <el-table :data="filteredList" stripe border style="width: 100%">
        <el-table-column prop="title" label="事件名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="等级" width="90">
          <template #default="{ row }">
            <el-tag :type="levelTagMap[row.level]" size="small">{{ levelLabelMap[row.level] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="110" />
        <el-table-column prop="happenedTime" label="发生时间" width="140" />
        <el-table-column prop="closedTime" label="结案时间" width="140" />
        <el-table-column prop="summary" label="处置摘要" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default>
            <el-tag type="success" size="small">已结案</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.archive-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.table-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>