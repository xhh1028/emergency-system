<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPlans, getPlanDetail } from '@/api/dispatch'

const planList = ref([])
const loading = ref(false)
const typeFilter = ref('')
const keywordFilter = ref('')
const planDialogVisible = ref(false)
const currentPlan = ref(null)
const planSteps = ref([])

const typeOptions = [
  '轨道异物及行车险情', '乘客人员事件', '火灾火情事件', '大客流与治安事件',
  '设备类故障', '灾害与环境事件', '其他突发事件'
]

function getLevelStyle(level) {
  if (level === '一级') return { background: 'rgba(255,69,58,0.12)', color: '#ff453a' }
  if (level === '二级') return { background: 'rgba(255,159,10,0.12)', color: '#ff9f0a' }
  return { background: 'rgba(10,132,255,0.12)', color: '#0a84ff' }
}

// 预案内容为带①②③…的文本，拆分为处置步骤数组
function parseSteps(content) {
  if (!content) return []
  return content
    .split(/[①-⑩]/)
    .map(s => s.trim())
    .filter(Boolean)
    .map((text, index) => ({
      stepTitle: `处置步骤 ${index + 1}`,
      description: text
    }))
}

async function loadPlans() {
  loading.value = true
  try {
    const response = await getPlans({ keyword: keywordFilter.value, type: typeFilter.value })
    planList.value = response.data || []
  } catch (e) {
    planList.value = []
    ElMessage.error(e?.message || '预案加载失败')
  } finally {
    loading.value = false
  }
}

async function handleView(row) {
  currentPlan.value = row
  planSteps.value = parseSteps(row.content)
  planDialogVisible.value = true
  try {
    const response = await getPlanDetail(row.id)
    const detail = response.data
    if (detail) {
      currentPlan.value = detail
      planSteps.value = parseSteps(detail.content)
    }
  } catch {
    // 详情接口异常时沿用列表数据
  }
}

onMounted(() => {
  loadPlans()
})
</script>

<template>
  <div class="plan-page">
    <div class="page-header">
      <div class="page-title">
        <h2>预案管理</h2>
        <span class="page-desc">管理应急处置预案，快速启动标准化响应流程</span>
      </div>
    </div>

    <div class="main-panel">
      <div class="table-wrapper">
        <table class="plan-table">
          <thead>
            <tr>
              <th>编号</th>
              <th>预案名称</th>
              <th>事件等级</th>
              <th>适用范围</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="plan in planList" :key="plan.id">
              <td class="plan-id">{{ plan.id }}</td>
              <td class="plan-name">
                <div class="plan-name-main">{{ plan.name }}</div>
                <div class="plan-type">{{ plan.matchEventType }}</div>
              </td>
              <td>
                <span class="status-tag" :style="getLevelStyle(plan.eventLevel)">
                  {{ plan.eventLevel }}
                </span>
              </td>
              <td>{{ plan.matchEventType }}</td>
              <td>{{ plan.updateTime }}</td>
              <td>
                <button class="action-btn primary" @click="handleView(plan)">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="planDialogVisible" class="modal-overlay" @click.self="planDialogVisible = false">
      <div class="modal plan-modal">
        <div class="modal-header">
          <span class="modal-title">{{ currentPlan?.name }}</span>
          <span class="modal-close" @click="planDialogVisible = false">×</span>
        </div>
        <div v-if="currentPlan" class="modal-body">
          <div class="plan-meta">
            <span class="status-tag" :style="getLevelStyle(currentPlan.eventLevel)">
              {{ currentPlan.eventLevel }}
            </span>
            <span class="plan-apply">适用事件：{{ currentPlan.matchEventType }}</span>
          </div>

          <div class="steps-section">
            <div class="steps-header">
              <span class="steps-title">处置步骤</span>
            </div>
            
            <div class="steps-progress">
              <div 
                v-for="(step, index) in planSteps" 
                :key="index" 
                class="step-item"
              >
                <div class="step-dot" :class="{ 'step-active': index === 0 }"></div>
                <div v-if="index < planSteps.length - 1" class="step-line"></div>
              </div>
            </div>

            <div class="steps-cards">
              <div
                v-for="(step, index) in planSteps"
                :key="index"
                class="step-card"
              >
                <div class="step-header">
                  <span class="step-number">{{ index + 1 }}</span>
                  <span class="step-title">{{ step.stepTitle }}</span>
                </div>
                <div class="step-description">{{ step.description }}</div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn primary" @click="planDialogVisible = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plan-page {
  min-height: 100%;
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.page-desc {
  font-size: 13px;
  color: var(--text-tertiary);
}

.main-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.table-wrapper {
  padding: 0;
}

.plan-table {
  width: 100%;
  border-collapse: collapse;
}

.plan-table th {
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.3px;
  padding: 12px 20px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.plan-table td {
  border-bottom: 1px solid var(--border);
  padding: 14px 20px;
  color: var(--text-secondary);
  font-size: 13px;
}

.plan-table tbody tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.plan-id {
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.plan-name-main {
  color: var(--text-primary);
  font-weight: 500;
  margin-bottom: 2px;
}

.plan-type {
  font-size: 12px;
  color: var(--text-tertiary);
}

.action-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  margin-right: 8px;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}

.action-btn.primary {
  background: var(--accent);
  color: white;
}

.action-btn.primary:hover {
  background: var(--accent-hover);
}

.status-tag {
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  width: 700px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.plan-modal {
  width: 700px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-close {
  font-size: 24px;
  color: var(--text-tertiary);
  cursor: pointer;
  line-height: 1;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.plan-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.plan-apply {
  font-size: 13px;
  color: var(--text-secondary);
}

.steps-section {
  margin-bottom: 8px;
}

.steps-header {
  margin-bottom: 16px;
}

.steps-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.steps-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  padding: 0 20px;
}

.step-item {
  display: flex;
  align-items: center;
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  flex-shrink: 0;
}

.step-dot.step-active {
  background: var(--accent);
  box-shadow: 0 0 8px rgba(10, 132, 255, 0.4);
}

.step-line {
  width: 40px;
  height: 2px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}

.steps-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-card {
  padding: 16px;
  background: var(--bg-overlay);
  border-radius: 8px;
  border-left: 4px solid var(--accent);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.step-title {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  font-size: 14px;
}

.step-role {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
}

.step-time {
  font-size: 12px;
  color: var(--text-tertiary);
}

.step-description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding-left: 36px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.btn.primary {
  background: var(--accent);
  color: white;
  border: none;
}

.btn.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}
</style>
