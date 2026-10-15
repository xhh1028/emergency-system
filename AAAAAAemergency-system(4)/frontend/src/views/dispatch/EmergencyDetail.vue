<script setup>
import { ref } from 'vue'

const eventId = ref('')
const loading = ref(false)
</script>

<template>
  <div class="detail-page" v-loading="loading">
    <el-page-header @back="$router.go(-1)">
      <template #content>
        <span class="page-title-text">预警事件详情 #{{ eventId }}</span>
      </template>
    </el-page-header>

    <el-descriptions :column="2" border class="detail-desc" size="small">
      <el-descriptions-item label="事件编号">EVT-2026-{{ String(eventId).padStart(4, '0') }}</el-descriptions-item>
      <el-descriptions-item label="预警等级">
        <el-tag type="danger" size="small">高危</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="发生时间">2026-05-24 09:30:00</el-descriptions-item>
      <el-descriptions-item label="影响线路">{{ (eventId % 5) + 1 }}号线</el-descriptions-item>
      <el-descriptions-item label="涉及车站">车站-模拟</el-descriptions-item>
      <el-descriptions-item label="当前状态">
        <el-tag type="warning" size="small">处理中</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="事件描述" :span="2">
        这是一条模拟的应急事件描述信息，用于展示系统的事件详情页面功能。
        在实际项目中，此处将显示真实的预警事件详细信息。
      </el-descriptions-item>
    </el-descriptions>

    <el-card shadow="hover" class="action-card">
      <template #header>
        <span class="panel-title">调度处置操作</span>
      </template>
      <el-space wrap>
        <el-button type="primary">启动应急预案</el-button>
        <el-button type="success">派发一线任务</el-button>
        <el-button type="warning">通知车站管理</el-button>
        <el-button type="info">请求后勤支援</el-button>
      </el-space>
    </el-card>
  </div>
</template>

<style scoped>
.detail-page {
  min-height: 100%;
}

.page-title-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--metro-text-primary);
}

.detail-desc {
  margin-top: 20px;
  background: var(--metro-bg-card);
}

.action-card {
  margin-top: 20px;
  background: var(--metro-bg-card);
  border: 1px solid var(--metro-border);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--metro-text-primary);
}
</style>