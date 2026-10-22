<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, ChatLineSquare } from '@element-plus/icons-vue'
import { getMyTasks, submitFeedback } from '@/api/field'
import { uploadFile } from '@/api/upload'

const submitting = ref(false)

const feedbackForm = reactive({
  taskId: '',
  content: ''
})

const fileList = ref([])

// 进行中的任务列表，用于下拉选择关联任务
const activeTaskList = ref([])

async function loadTasks() {
  try {
    const res = await getMyTasks({ status: 'in_progress' })
    activeTaskList.value = res?.list || res || []
  } catch (e) {
    ElMessage.error(e?.message || '加载任务列表失败')
  }
}

// 提交反馈（含图片上传）
async function handleSubmit() {
  if (!feedbackForm.content.trim()) {
    ElMessage.warning('请填写反馈内容')
    return
  }
  submitting.value = true
  try {
    // 1. 先上传现场图片，获取 url 列表
    const imageUrls = []
    for (const file of fileList.value) {
      if (file.raw) {
        const formData = new FormData()
        formData.append('file', file.raw)
        const uploadRes = await uploadFile(formData)
        imageUrls.push(uploadRes?.url || '')
      }
    }

    // 2. 提交反馈内容
    await submitFeedback({
      taskId: feedbackForm.taskId || undefined,
      content: feedbackForm.content.trim(),
      images: imageUrls.filter(Boolean)
    })

    ElMessage.success('反馈提交成功')
    feedbackForm.taskId = ''
    feedbackForm.content = ''
    fileList.value = []
  } catch (e) {
    ElMessage.error(e?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<template>
  <div class="feedback-page">
    <div class="page-header">
      <h2>现场反馈</h2>
      <span class="page-desc">上报任务执行进度及现场情况</span>
    </div>

    <el-card shadow="hover" class="form-card">
      <template #header>
        <span class="panel-title">提交反馈</span>
      </template>

      <div class="feedback-form">
        <el-form label-width="100px">
          <el-form-item label="关联任务">
            <el-select
              v-model="feedbackForm.taskId"
              placeholder="请选择关联任务（可选）"
              clearable
              style="width: 100%"
            >
              <!-- ==================== 后端对接区 ==================== -->
              <el-option
                v-for="t in activeTaskList"
                :key="t.id"
                :label="t.title"
                :value="t.id"
              />
              <!-- ==================== 后端对接区 ==================== -->
            </el-select>
          </el-form-item>

          <el-form-item label="反馈内容">
            <el-input
              v-model="feedbackForm.content"
              type="textarea"
              :rows="5"
              placeholder="请详细描述当前任务执行进度、现场情况、遇到的问题等..."
              resize="none"
            />
          </el-form-item>

          <!-- ==================== 后端对接区 ==================== -->
          <el-form-item label="现场图片">
            <el-upload
              v-model:file-list="fileList"
              :auto-upload="false"
              list-type="picture-card"
              accept="image/*"
            >
              <el-icon><Plus /></el-icon>
            </el-upload>
            <template #extra>
              <span class="upload-hint">支持 jpg/png，单张不超过 10MB</span>
            </template>
          </el-form-item>
          <!-- ==================== 后端对接区 ==================== -->

          <el-form-item>
            <el-button
              type="primary"
              :loading="submitting"
              :icon="ChatLineSquare"
              size="large"
              @click="handleSubmit"
            >
              提交反馈
            </el-button>
            <el-button size="large" @click="feedbackForm.content = ''; feedbackForm.taskId = ''">
              清空
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.feedback-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.form-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.panel-title { font-size: 15px; font-weight: 600; color: var(--metro-text-primary); }
.feedback-form { max-width: 680px; }
.upload-hint { font-size: 12px; color: var(--metro-text-muted); }
</style>