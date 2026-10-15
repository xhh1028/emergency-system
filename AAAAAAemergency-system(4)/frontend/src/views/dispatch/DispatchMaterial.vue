<script setup>
import { ref, computed, onMounted } from 'vue'

// 全线物资总览（只读，不可修改数据）
const stationMaterialList = ref([])
const keyword = ref('')
const searchStation = ref('')

// mock：各车站物资库存数据
const MOCK_STATION_MATERIALS = [
  { id: 1, station: '人民广场站', line: '1号线', material: '应急发电车', total: 3, available: 2, status: 'normal' },
  { id: 2, station: '人民广场站', line: '1号线', material: '消防器材', total: 56, available: 50, status: 'normal' },
  { id: 3, station: '人民广场站', line: '1号线', material: '医疗急救包', total: 24, available: 20, status: 'normal' },
  { id: 4, station: '南京东路站', line: '2号线', material: '通讯设备', total: 18, available: 15, status: 'normal' },
  { id: 5, station: '南京东路站', line: '2号线', material: '应急照明', total: 42, available: 30, status: 'warning' },
  { id: 6, station: '南京东路站', line: '2号线', material: '防护装备', total: 80, available: 76, status: 'normal' },
  { id: 7, station: '世纪大道站', line: '2号线', material: '应急发电车', total: 2, available: 0, status: 'danger' },
  { id: 8, station: '世纪大道站', line: '2号线', material: '消防器材', total: 40, available: 38, status: 'normal' },
  { id: 9, station: '徐家汇站', line: '1号线', material: '医疗急救包', total: 30, available: 28, status: 'normal' },
  { id: 10, station: '徐家汇站', line: '1号线', material: '应急照明', total: 36, available: 20, status: 'warning' },
  { id: 11, station: '虹桥火车站', line: '10号线', material: '应急发电车', total: 5, available: 5, status: 'normal' },
  { id: 12, station: '虹桥火车站', line: '10号线', material: '防护装备', total: 120, available: 100, status: 'normal' },
  { id: 13, station: '虹桥火车站', line: '10号线', material: '通讯设备', total: 26, available: 22, status: 'normal' },
  { id: 14, station: '龙阳路站', line: '2号线', material: '消防器材', total: 48, available: 46, status: 'normal' },
  { id: 15, station: '龙阳路站', line: '2号线', material: '医疗急救包', total: 20, available: 12, status: 'warning' }
]

const stationOptions = computed(() => {
  const set = new Set(stationMaterialList.value.map(item => item.station))
  return [...set].map(s => ({ label: s, value: s }))
})

const filteredList = computed(() => {
  return stationMaterialList.value.filter(item => {
    const matchStation = !searchStation.value || item.station === searchStation.value
    const matchKeyword = !keyword.value || item.material.toLowerCase().includes(keyword.value.toLowerCase())
    return matchStation && matchKeyword
  })
})

const totalStations = computed(() => new Set(stationMaterialList.value.map(i => i.station)).size)
const totalMaterials = computed(() => stationMaterialList.value.length)
const warningCount = computed(() => stationMaterialList.value.filter(i => i.status === 'warning').length)
const dangerCount = computed(() => stationMaterialList.value.filter(i => i.status === 'danger').length)

function getStatusInfo(status) {
  if (status === 'normal') return { label: '充足', type: 'success' }
  if (status === 'warning') return { label: '库存偏低', type: 'warning' }
  return { label: '紧缺', type: 'danger' }
}

function loadData() {
  stationMaterialList.value = [...MOCK_STATION_MATERIALS]
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="material-page">
    <div class="page-header">
      <h2>全线物资总览</h2>
      <span class="page-desc">查看全路网各车站应急物资库存情况（只读）</span>
    </div>

    <div class="stat-row">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-value">{{ totalStations }}</div>
        <div class="stat-label">覆盖车站</div>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <div class="stat-value">{{ totalMaterials }}</div>
        <div class="stat-label">物资记录</div>
      </el-card>
      <el-card shadow="hover" class="stat-card warning">
        <div class="stat-value">{{ warningCount }}</div>
        <div class="stat-label">库存偏低</div>
      </el-card>
      <el-card shadow="hover" class="stat-card danger">
        <div class="stat-value">{{ dangerCount }}</div>
        <div class="stat-label">库存紧缺</div>
      </el-card>
    </div>

    <el-card shadow="hover" class="table-card">
      <div class="toolbar">
        <el-select v-model="searchStation" placeholder="选择车站" clearable style="width: 180px">
          <el-option v-for="opt in stationOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索物资名称" clearable style="width: 200px" />
      </div>

      <el-table :data="filteredList" stripe border style="width: 100%">
        <el-table-column prop="station" label="车站" width="130" />
        <el-table-column prop="line" label="线路" width="100" />
        <el-table-column prop="material" label="物资名称" min-width="140" />
        <el-table-column prop="total" label="库存总量" width="100" />
        <el-table-column prop="available" label="可用数量" width="100" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusInfo(row.status).type" size="small">
              {{ getStatusInfo(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.material-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-card .stat-value { font-size: 28px; font-weight: 700; color: var(--metro-text-primary); }
.stat-card.warning .stat-value { color: #f59e0b; }
.stat-card.danger .stat-value { color: #ef4444; }
.stat-card .stat-label { font-size: 12px; color: var(--metro-text-muted); margin-top: 4px; }
.table-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>