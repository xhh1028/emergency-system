<script setup>
import { ref } from 'vue'

const stationList = ref([])
const searchKeyword = ref('')
</script>

<template>
  <div class="station-page">
    <div class="page-title">
      <h2>车站运行管理</h2>
      <span class="page-subtitle">实时监控各车站运行状态与客流动向</span>
    </div>

    <el-card shadow="hover" class="panel-card">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">车站列表 ({{ stationList.length }})</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索车站名称..."
            style="width: 240px"
            size="small"
            clearable
          />
        </div>
      </template>
      <el-table :data="stationList" size="small">
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column prop="name" label="车站名称" width="140" />
        <el-table-column prop="line" label="所属线路" width="100" />
        <el-table-column prop="status" label="运行状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'online' ? 'success' : 'danger'"
              size="small"
            >
              {{ row.status === 'online' ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="passengerFlow" label="实时客流" width="100" />
        <el-table-column prop="alertCount" label="预警数量" width="90">
          <template #default="{ row }">
            <el-badge :value="row.alertCount" :max="99" :hidden="!row.alertCount">
              <span>{{ row.alertCount }}</span>
            </el-badge>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="$router.push(`/station/monitor/${row.id}`)"
            >
              查看监控
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.station-page {
  min-height: 100%;
}

.page-title {
  margin-bottom: 24px;
}

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--metro-text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--metro-text-muted);
  margin-top: 4px;
  display: block;
}

.panel-card {
  background: var(--metro-bg-card);
  border: 1px solid var(--metro-border);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--metro-text-primary);
}
</style>