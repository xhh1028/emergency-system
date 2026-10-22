<script setup>
import { ref } from 'vue'

const alertList = ref([])
</script>

<template>
  <div class="dispatch-page">
    <div class="page-header">
      <div class="page-title">
        <h1>调度指挥中心</h1>
        <span class="page-subtitle">统一调度、快速响应、精准指挥</span>
      </div>
    </div>

    <div class="content-grid">
      <div class="side-panel">
        <div class="panel-header">
          <span class="panel-title">待处理预警 (5)</span>
        </div>
        <div
          v-for="i in 3"
          :key="i"
          class="alert-item"
        >
          <div class="alert-dot high" />
          <div class="alert-info">
            <span class="alert-title">模拟高危预警 #{{ i }}</span>
            <span class="alert-time">2026-05-24 0{{ i }}:30</span>
          </div>
        </div>
      </div>

      <div class="main-panel">
        <div class="panel-header">
          <span class="panel-title">全部预警列表</span>
        </div>
        <div class="table-wrapper">
          <table class="event-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>事件标题</th>
                <th>车站</th>
                <th>等级</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <!-- 这里可以添加模拟数据 -->
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dispatch-page {
  min-height: 100%;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
}

.page-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title h1 {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.2px;
  color: var(--text-primary);
  margin: 0;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
}

.main-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.side-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.alert-dot.high {
  background: var(--red);
}

.alert-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.alert-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.action-link {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
  margin-right: 16px;
  transition: color 0.2s;
  font-weight: 500;
}

.action-link:hover {
  color: var(--accent-hover);
}

.table-wrapper {
  padding: 0;
}

.event-table {
  width: 100%;
  border-collapse: collapse;
}

.event-table th {
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.3px;
  padding: 12px 20px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.event-table td {
  border-bottom: 1px solid var(--border);
  padding: 14px 20px;
  color: var(--text-primary);
  font-size: 13px;
}

.event-table tbody tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}
</style>
