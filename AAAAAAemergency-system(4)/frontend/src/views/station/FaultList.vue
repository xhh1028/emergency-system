<script setup>
import { computed } from 'vue'
import { useFaultStore } from '@/store'

const faultStore = useFaultStore()
const faultReports = computed(() => faultStore.openFaultReports)

function formatLocation(report) {
  return `${report.deviceLine} · ${report.deviceLocation}`
}
</script>

<template>
  <div class="fault-list-page">
    <div class="page-header">
      <h2>故障上报清单</h2>
      <span class="page-desc">查看当前设备故障上报记录，供调度人员判断任务分配与维修方案。</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <el-table
        :data="faultReports"
        stripe
        size="default"
        empty-text="当前暂无未处理故障上报"
      >
        <el-table-column prop="reportTime" label="上报时间" width="180" />
        <el-table-column label="故障设备" min-width="180">
          <template #default="{ row }">
            <div>{{ row.deviceName }}</div>
            <div class="device-meta">{{ formatLocation(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="故障描述" min-width="320" show-overflow-tooltip />
        <el-table-column prop="reporter" label="上报人" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag type="danger" size="small">未处理</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.fault-list-page {
  min-height: 100%;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--metro-text-primary);
  margin: 0;
}

.page-desc {
  font-size: 13px;
  color: var(--metro-text-muted);
  margin-top: 4px;
  display: block;
}

.table-card {
  background: var(--metro-bg-card);
  border: 1px solid var(--metro-border);
}

.device-meta {
  font-size: 12px;
  color: var(--metro-text-muted);
  margin-top: 4px;
}
</style>
