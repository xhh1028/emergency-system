<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const stationId = ref(route.params.id)
const loading = ref(false)
</script>

<template>
  <div class="monitor-page" v-loading="loading">
    <el-page-header @back="$router.go(-1)">
      <template #content>
        <span class="page-title-text">车站监控详情 #{{ stationId }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="16" style="margin-top: 20px">
      <el-col :span="8">
        <el-card shadow="hover" class="panel-card">
          <template #header><span class="panel-title">实时客流</span></template>
          <div class="stat-highlight">{{ Math.floor(Math.random() * 5000) + 500 }}</div>
          <span class="stat-unit">人次/小时</span>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="panel-card">
          <template #header><span class="panel-title">设备状态</span></template>
          <div class="stat-highlight success">98.5%</div>
          <span class="stat-unit">正常运行率</span>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="panel-card">
          <template #header><span class="panel-title">在岗人员</span></template>
          <div class="stat-highlight info">{{ Math.floor(Math.random() * 20) + 10 }}</div>
          <span class="stat-unit">人</span>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="panel-card" style="margin-top: 16px">
      <template #header><span class="panel-title">监控画面预览区</span></template>
      <el-empty description="监控视频流接入中（演示占位）">
        <template #image>
          <el-icon :size="80" color="var(--metro-text-muted)"><VideoCamera /></el-icon>
        </template>
      </el-empty>
    </el-card>
  </div>
</template>

<style scoped>
.monitor-page {
  min-height: 100%;
}

.page-title-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--metro-text-primary);
}

.panel-card {
  background: var(--metro-bg-card);
  border: 1px solid var(--metro-border);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--metro-text-primary);
}

.stat-highlight {
  font-size: 36px;
  font-weight: 700;
  color: var(--metro-accent);
  text-align: center;
}

.stat-highlight.success {
  color: var(--metro-success);
}

.stat-highlight.info {
  color: var(--metro-info);
}

.stat-unit {
  display: block;
  text-align: center;
  font-size: 13px;
  color: var(--metro-text-muted);
  margin-top: 4px;
}
</style>