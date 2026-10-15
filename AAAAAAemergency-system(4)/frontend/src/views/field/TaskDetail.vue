<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { completeTask, getTaskDetail, startTask } from '@/api/task'

const route = useRoute()
const router = useRouter()
const task = ref(null)
const loading = ref(false)
const submitting = ref(false)
const uploadFiles = ref([])
const formRef = ref()
const form = reactive({ feedbackText: '' })

const statusLabels = {
  PENDING: '待执行', IN_PROGRESS: '执行中', COMPLETED: '已完成', OVERDUE: '已逾期'
}
const statusTypes = {
  PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', OVERDUE: 'danger'
}
const sourceLabels = { STATION: '车站分派', DISPATCH: '调度指令' }
const eventTypeLabels = {
  DEVICE_FAILURE: '设备故障', FIRE: '火灾烟情', PASSENGER: '乘客事件',
  TRACK_OPERATION: '轨道与行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}

const eventImages = computed(() => splitImages(task.value?.eventImageUrls))

function splitImages(value) {
  return value ? value.split(';').filter(Boolean) : []
}

function formatTime(value) {
  if (!value) return '未设置'
  return String(value).replace('T', ' ').slice(0, 19)
}

async function loadDetail() {
  loading.value = true
  try {
    const response = await getTaskDetail(route.params.id)
    task.value = response.data
  } finally {
    loading.value = false
  }
}

async function handleStart() {
  await startTask(task.value.id)
  ElMessage.success('任务已开始执行')
  await loadDetail()
}

function beforeUpload(file) {
  const validType = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
  const validSize = file.size <= 5 * 1024 * 1024
  if (!validType) ElMessage.error('仅支持 JPG、PNG、WEBP 图片')
  if (!validSize) ElMessage.error('单张图片不能超过5MB')
  return validType && validSize
}

function onUploadChange(file, files) {
  if (!beforeUpload(file.raw)) {
    uploadFiles.value = files.filter(item => item.uid !== file.uid)
    return
  }
  uploadFiles.value = files.slice(0, 5)
}

function onUploadExceed() {
  ElMessage.warning('现场图片最多上传5张')
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    await completeTask(task.value.id, {
      feedbackText: form.feedbackText,
      images: uploadFiles.value.map(item => item.raw).filter(Boolean)
    })
    ElMessage.success('完成反馈已提交，任务进度已更新为100%')
    form.feedbackText = ''
    uploadFiles.value = []
    await loadDetail()
  } finally {
    submitting.value = false
  }
}

onMounted(loadDetail)
</script>

<template>
  <div class="detail-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>任务详情</h2>
        <p v-if="task">{{ task.taskNo }} · {{ task.eventNo }}</p>
      </div>
      <el-button @click="router.back()">返回</el-button>
    </div>

    <template v-if="task">
      <el-card shadow="never" class="detail-card">
        <template #header>
          <div class="card-header">
            <strong>{{ task.content }}</strong>
            <el-tag :type="statusTypes[task.status]">{{ statusLabels[task.status] }}</el-tag>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务来源">{{ sourceLabels[task.source] || task.source }}</el-descriptions-item>
          <el-descriptions-item label="执行岗位">{{ task.postName || '未设置' }}</el-descriptions-item>
          <el-descriptions-item label="所属车站">{{ task.lineName }} {{ task.stationName }}</el-descriptions-item>
          <el-descriptions-item label="截止时间">{{ formatTime(task.deadline) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(task.createTime) }}</el-descriptions-item>
          <el-descriptions-item label="任务状态">
            <el-tag :type="statusTypes[task.status]">{{ statusLabels[task.status] }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="task.rawStatus === 'PENDING'" class="primary-action">
          <el-button type="primary" @click="handleStart">开始执行任务</el-button>
        </div>
      </el-card>

      <el-card shadow="never" class="detail-card">
        <template #header><strong>关联事件</strong></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="事件类型">{{ eventTypeLabels[task.eventType] || task.eventType }}</el-descriptions-item>
          <el-descriptions-item label="事件等级">{{ task.eventLevel || '待确认' }}</el-descriptions-item>
          <el-descriptions-item label="事件描述" :span="2">{{ task.eventDescription || '暂无描述' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="eventImages.length" class="image-list">
          <el-image v-for="url in eventImages" :key="url" :src="url" :preview-src-list="eventImages" fit="cover" />
        </div>
      </el-card>

      <el-card v-if="task.rawStatus === 'IN_PROGRESS'" shadow="never" class="detail-card">
        <template #header><strong>提交现场完成反馈</strong></template>
        <el-form ref="formRef" :model="form" label-width="90px">
          <el-form-item
            label="完成说明"
            prop="feedbackText"
            :rules="[{ required: true, message: '请填写现场处置情况', trigger: 'blur' }]"
          >
            <el-input v-model="form.feedbackText" type="textarea" :rows="5" maxlength="2000" show-word-limit placeholder="说明处置过程、结果和现场状态" />
          </el-form-item>
          <el-form-item label="现场图片">
            <el-upload
              v-model:file-list="uploadFiles"
              action="#"
              accept="image/jpeg,image/png,image/webp"
              list-type="picture-card"
              :auto-upload="false"
              :limit="5"
              :on-change="onUploadChange"
              :on-exceed="onUploadExceed"
            >
              <span class="upload-plus">+</span>
            </el-upload>
            <div class="upload-tip">最多5张，单张不超过5MB</div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="submitting" @click="handleSubmit">提交并完成任务</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="detail-card">
        <template #header><strong>现场反馈记录</strong></template>
        <el-timeline v-if="task.feedback?.length">
          <el-timeline-item v-for="item in task.feedback" :key="item.id" :timestamp="formatTime(item.createTime)" placement="top">
            <div class="feedback-title">{{ item.operatorName }}</div>
            <p>{{ item.text }}</p>
            <div v-if="splitImages(item.imageUrls).length" class="image-list">
              <el-image
                v-for="url in splitImages(item.imageUrls)"
                :key="url"
                :src="url"
                :preview-src-list="splitImages(item.imageUrls)"
                fit="cover"
              />
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="尚未提交现场反馈" :image-size="70" />
      </el-card>
    </template>
    <el-empty v-else-if="!loading" description="未找到任务信息" />
  </div>
</template>

<style scoped>
.detail-page { min-height: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
.page-header h2 { margin: 0; color: var(--metro-text-primary); font-size: 22px; }
.page-header p { margin: 5px 0 0; color: var(--metro-text-muted); font-size: 13px; }
.detail-card { margin-bottom: 16px; border: 1px solid var(--metro-border); background: var(--metro-bg-card); }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 20px; }
.primary-action { display: flex; justify-content: flex-end; margin-top: 18px; }
.image-list { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
.image-list :deep(.el-image) { width: 108px; height: 82px; border-radius: 6px; }
.upload-tip { width: 100%; margin-top: 6px; color: var(--metro-text-muted); font-size: 12px; }
.upload-plus { font-size: 28px; color: var(--metro-text-muted); }
.feedback-title { font-weight: 600; color: var(--metro-text-primary); }
.el-timeline p { color: var(--metro-text-secondary); line-height: 1.6; }
@media (max-width: 760px) { :deep(.el-descriptions__body .el-descriptions__table) { display: block; } }
</style>
