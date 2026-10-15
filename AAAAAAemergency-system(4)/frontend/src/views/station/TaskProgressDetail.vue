<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getStationTaskDetail } from '@/api/station'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const task = ref(null)

const statusLabels = { PENDING: '待签收', IN_PROGRESS: '处置中', COMPLETED: '已完成', OVERDUE: '已逾期' }
const statusTypes = { PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', OVERDUE: 'danger' }
const sourceLabels = { STATION: '车站指派', DISPATCH: '调度指令' }

async function loadDetail() {
  loading.value = true
  try {
    task.value = (await getStationTaskDetail(route.params.id)).data
  } finally {
    loading.value = false
  }
}

function feedbackImages(value) {
  return String(value || '').split(';').map(item => item.trim()).filter(Boolean)
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 19) : '—'
}

onMounted(loadDetail)
</script>

<template>
  <div class="task-detail-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>子任务处置详情</h2>
        <span class="page-desc">第三层：查看该子任务的执行人与一线执行人员提交的完成说明、现场图片。</span>
      </div>
      <el-button @click="router.back()">返回</el-button>
    </div>

    <template v-if="task">
      <el-card shadow="hover" class="info-card">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务编号">{{ task.taskNo }}</el-descriptions-item>
          <el-descriptions-item label="任务状态">
            <el-tag :type="statusTypes[task.status]">{{ statusLabels[task.status] || task.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联事件">{{ task.eventNo }}</el-descriptions-item>
          <el-descriptions-item label="任务来源">{{ sourceLabels[task.source] || task.source }}</el-descriptions-item>
          <el-descriptions-item label="执行人员">{{ task.executorName }}（{{ task.postName || '一线人员' }}）</el-descriptions-item>
          <el-descriptions-item label="截止时间">{{ formatTime(task.deadline) }}</el-descriptions-item>
          <el-descriptions-item label="任务内容" :span="2"><div class="task-content">{{ task.content }}</div></el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="hover" class="info-card">
        <template #header><strong>一线执行反馈</strong></template>
        <el-empty v-if="!task.feedback?.length" description="该子任务暂无现场反馈" />
        <el-timeline v-else>
          <el-timeline-item
            v-for="item in task.feedback"
            :key="item.id"
            :timestamp="formatTime(item.createTime)"
            placement="top"
          >
            <div class="feedback-card">
              <div class="feedback-meta">反馈人员：{{ item.operatorName }}</div>
              <div class="feedback-text">{{ item.text || '未填写文字说明' }}</div>
              <div v-if="feedbackImages(item.imageUrls).length" class="image-list">
                <el-image
                  v-for="url in feedbackImages(item.imageUrls)"
                  :key="url"
                  :src="url"
                  :preview-src-list="feedbackImages(item.imageUrls)"
                  fit="cover"
                  class="feedback-image"
                  preview-teleported
                />
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </template>
    <el-empty v-else-if="!loading" description="未找到子任务信息" />
  </div>
</template>

<style scoped>
.task-detail-page{min-height:100%}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.page-header h2{margin:0;font-size:22px;color:var(--metro-text-primary)}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.info-card{margin-bottom:16px}.task-content,.feedback-text{white-space:pre-wrap;line-height:1.8}.feedback-meta{margin-bottom:8px;color:var(--metro-text-muted);font-size:13px}.image-list{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.feedback-image{width:120px;height:88px;border-radius:6px}
</style>
