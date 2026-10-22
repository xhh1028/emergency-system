<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTaskDetail, startTask, completeTask } from '@/api/task'
import { sendCommand } from '@/api/dispatch'

const route = useRoute()
const router = useRouter()
const taskId = ref(route.params.id || '')
const loading = ref(true)
const task = ref(null)
const feedbackText = ref('')
const submitting = ref(false)

// ===== 开始执行 =====
async function handleStart() {
  try {
    await startTask(taskId.value)
    ElMessage.success('任务已开始执行')
    loadTask()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

// ===== 上报完成 =====
async function handleReportComplete() {
  if (!feedbackText.value.trim()) {
    ElMessage.warning('请先填写执行反馈信息')
    return
  }
  submitting.value = true
  try {
    await completeTask(taskId.value, {
      result: 'completed',
      description: feedbackText.value.trim()
    })
    ElMessage.success('任务完成报告已提交')
    router.push({ path: '/field/tasks' })
  } catch (e) {
    ElMessage.error(e?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

// ===== 申请支援 =====
async function handleSupportRequest() {
  try {
    await sendCommand({
      content: `任务 #${taskId.value}「${task.value?.title || ''}」需要支援，请及时响应`,
      priority: 'high',
      targetStation: '后勤安保中心'
    })
    ElMessage.success('支援申请已发出')
  } catch (e) {
    ElMessage.error(e?.message || '申请失败')
  }
}

// ===== 暂停任务 =====
async function handlePause() {
  try {
    await completeTask(taskId.value, {
      result: 'failed',
      description: `任务暂停：${feedbackText.value.trim() || '暂无说明'}`
    })
    ElMessage.success('任务已暂停')
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

// ===== 提交反馈 =====
async function handleSubmitFeedback() {
  if (!feedbackText.value.trim()) {
    ElMessage.warning('请输入反馈内容')
    return
  }
  submitting.value = true
  try {
    await sendCommand({
      content: `任务 #${taskId.value} 执行反馈：${feedbackText.value.trim()}`,
      priority: 'normal',
      targetStation: '调度中心'
    })
    feedbackText.value = ''
    ElMessage.success('反馈已提交')
  } catch (e) {
    ElMessage.error(e?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function loadTask() {
  if (!taskId.value) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await getTaskDetail(taskId.value)
    task.value = res?.task || res
  } catch (e) {
    ElMessage.error(e?.message || '加载任务详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTask()
})
</script>

<template>
  <div class="detail-page" v-loading="loading">
    <el-page-header @back="$router.go(-1)">
      <template #content>
        <span class="page-title-text">任务详情 #{{ taskId }}</span>
      </template>
    </el-page-header>

    <el-descriptions :column="2" border class="detail-desc" size="small">
      <el-descriptions-item label="任务编号">TASK-2026-{{ String(taskId).padStart(4, '0') }}</el-descriptions-item>
      <el-descriptions-item label="优先级">
        <el-tag :type="{ urgent: 'danger', high: 'warning', normal: '' }[task?.priority]" size="small">
          {{ { urgent: '紧急', high: '高', normal: '普通' }[task?.priority] || '普通' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="任务类型">{{ task?.type || '-' }}</el-descriptions-item>
      <el-descriptions-item label="执行车站">{{ task?.stationName || task?.station || '-' }}</el-descriptions-item>
      <el-descriptions-item label="下发时间">{{ task?.createTime || '-' }}</el-descriptions-item>
      <el-descriptions-item label="截止时间">{{ task?.deadline || '-' }}</el-descriptions-item>
      <el-descriptions-item label="任务描述" :span="2">
        {{ task?.description || '暂无任务描述信息' }}
      </el-descriptions-item>
    </el-descriptions>

    <el-card shadow="hover" class="action-card">
      <template #header>
        <span class="panel-title">执行操作</span>
      </template>
      <el-space wrap>
        <el-button type="primary" @click="handleStart">开始执行</el-button>
        <el-button type="success" :loading="submitting" @click="handleReportComplete">上报完成</el-button>
        <el-button type="warning" @click="handleSupportRequest">申请支援</el-button>
        <el-button @click="handlePause">暂停任务</el-button>
      </el-space>
    </el-card>

    <el-card shadow="hover" class="action-card">
      <template #header>
        <span class="panel-title">执行反馈</span>
      </template>
      <el-input
        v-model="feedbackText"
        type="textarea"
        :rows="3"
        placeholder="请输入执行反馈信息..."
        style="margin-top: 12px"
      />
      <el-button type="primary" size="small" style="margin-top: 8px" :loading="submitting" @click="handleSubmitFeedback">
        提交反馈
      </el-button>
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