<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { reportEvent } from '@/api/event'

const formRef = ref()
const submitting = ref(false)
const fileList = ref([])
const form = reactive({
  eventTitle: '',
  eventType: '',
  faultyDevice: '',
  description: '',
  isEmergency: false
})

const eventTypes = [
  { value: 'DEVICE_FAILURE', label: '设备故障' },
  { value: 'FIRE', label: '火灾险情' },
  { value: 'PASSENGER', label: '乘客事件' },
  { value: 'TRACK_OPERATION', label: '轨道及行车险情' },
  { value: 'CROWD_SECURITY', label: '客流及治安事件' },
  { value: 'DISASTER_ENVIRONMENT', label: '灾害及环境事件' },
  { value: 'OTHER', label: '其他事件' }
]

const rules = {
  eventTitle: [
    { required: true, message: '请填写事件标题', trigger: 'blur' },
    { max: 200, message: '事件标题不能超过 200 个字符', trigger: 'blur' }
  ],
  eventType: [{ required: true, message: '请选择突发状况类型', trigger: 'change' }],
  description: [
    { required: true, message: '请填写事件描述', trigger: 'blur' },
    { min: 5, max: 1000, message: '事件描述应为 5—1000 个字符', trigger: 'blur' }
  ]
}

function handleFileChange(file, files) {
  fileList.value = files
}

function handleFileRemove(file, files) {
  fileList.value = files
}

function handleExceed() {
  ElMessage.warning('现场图片最多上传 5 张')
}

function beforeUpload(file) {
  const allowed = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
  if (!allowed) {
    ElMessage.error('仅支持 JPG、PNG、WEBP 图片')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('单张图片不能超过 5MB')
    return false
  }
  return false
}

function resetForm() {
  form.eventType = ''
  form.eventTitle = ''
  form.faultyDevice = ''
  form.description = ''
  form.isEmergency = false
  fileList.value = []
  formRef.value?.clearValidate()
}

async function submitReport() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const invalidFile = fileList.value.find(item => {
    const raw = item.raw
    return !raw || !['image/jpeg', 'image/png', 'image/webp'].includes(raw.type) || raw.size > 5 * 1024 * 1024
  })
  if (invalidFile) {
    ElMessage.error('图片格式或大小不符合要求')
    return
  }

  submitting.value = true
  try {
    const data = new FormData()
    data.append('eventTitle', form.eventTitle.trim())
    data.append('eventType', form.eventType)
    // 定级权限仅调度指挥中心，一线上报不提交等级；仅标记是否为紧急险情
    data.append('isEmergency', form.isEmergency ? 'true' : 'false')
    data.append('faultyDevice', form.faultyDevice.trim())
    data.append('description', form.description.trim())
    fileList.value.forEach(item => data.append('images', item.raw))
    const response = await reportEvent(data)
    ElMessage.success(`上报成功，事件编号：${response.data.eventNo}`)
    resetForm()
  } catch (error) {
    // 公共请求层会展示后端返回的具体原因。
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="report-page">
    <div class="page-header">
      <h2>险情上报</h2>
      <span class="page-desc">如实填写现场情况；提交后将进入所属车站的事件待办。</span>
    </div>

    <el-card shadow="hover" class="report-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="24">
          <el-col :span="24">
            <el-form-item label="事件标题" prop="eventTitle">
              <el-input v-model="form.eventTitle" maxlength="200" show-word-limit placeholder="简要概括本次险情" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="突发状况类型" prop="eventType">
              <el-select v-model="form.eventType" placeholder="请选择类型" class="full-width">
                <el-option
                  v-for="item in eventTypes"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.eventType === 'DEVICE_FAILURE'" :span="24">
            <el-form-item
              label="故障设备"
              prop="faultyDevice"
              :rules="[{ required: true, message: '请填写故障设备', trigger: 'blur' }]"
            >
              <el-input v-model="form.faultyDevice" maxlength="200" show-word-limit placeholder="例如：站台门 3-2、AFC 闸机 08" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="是否紧急" prop="isEmergency">
              <el-checkbox v-model="form.isEmergency">
                是否为紧急险情（紧急险情跳过驳回、直接定级并分派处置任务）
              </el-checkbox>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="事件描述" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="6"
                maxlength="1000"
                show-word-limit
                placeholder="请描述发生时间、具体位置、现场现象、影响范围及已采取的措施"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="现场图片">
              <el-upload
                v-model:file-list="fileList"
                action="#"
                list-type="picture-card"
                accept="image/jpeg,image/png,image/webp"
                :auto-upload="false"
                :limit="5"
                :before-upload="beforeUpload"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
                :on-exceed="handleExceed"
              >
                <el-icon><Plus /></el-icon>
              </el-upload>
              <div class="upload-tip">最多 5 张；支持 JPG、PNG、WEBP；单张不超过 5MB。</div>
            </el-form-item>
          </el-col>
        </el-row>
        <div class="actions">
          <el-button @click="resetForm">重置</el-button>
          <el-button type="primary" :loading="submitting" @click="submitReport">提交上报</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.report-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0; color: var(--metro-text-primary); font-size: 22px; font-weight: 600; }
.page-desc { display: block; margin-top: 4px; color: var(--metro-text-muted); font-size: 13px; }
.report-card { border: 1px solid var(--metro-border); background: var(--metro-bg-card); }
.full-width { width: 100%; }
.upload-tip { width: 100%; margin-top: 8px; color: var(--metro-text-muted); font-size: 12px; }
.actions { display: flex; justify-content: flex-end; gap: 10px; padding-top: 8px; }
</style>
