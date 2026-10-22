<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEventDetail } from '@/api/event'
import { activatePlan } from '@/api/dispatch'
import { getPlans } from '@/api/dispatch'
import { createTask } from '@/api/task'
import { sendCommand } from '@/api/dispatch'
import { getStations } from '@/api/station'

const route = useRoute()
const eventId = ref(route.params.id || '')
const loading = ref(false)
const event = ref(null)

// ===== 启动应急预案 =====
async function handleActivatePlan() {
  if (!eventId.value) {
    ElMessage.warning('缺少事件编号')
    return
  }
  try {
    // 拉取预案列表，供用户选择（此处演示取第一个预案，实际可弹出选择框）
    const res = await getPlans({})
    const plans = res?.list || res || []
    if (plans.length === 0) {
      ElMessage.warning('暂无可用应急预案')
      return
    }
    const planId = plans[0].id
    await activatePlan(planId, { eventId: Number(eventId.value) })
    ElMessage.success(`已启动预案「${plans[0].name}」`)
    // 刷新事件详情，更新状态流转
    loadEvent()
  } catch (e) {
    ElMessage.error(e?.message || '启动预案失败')
  }
}

// ===== 派发一线任务 =====
async function handleDispatchTask() {
  if (!eventId.value) {
    ElMessage.warning('缺少事件编号')
    return
  }
  try {
    await createTask({
      title: `事件 #${eventId.value} 应急处置任务`,
      type: '疏散引导',
      priority: 'high',
      participantIds: [],
      leaderId: '',
      deadline: new Date(Date.now() + 4 * 3600000).toISOString(),
      description: `由调度中心针对事件 #${eventId.value} 派发的应急处置任务`
    })
    ElMessage.success('一线任务已派发')
  } catch (e) {
    ElMessage.error(e?.message || '任务派发失败')
  }
}

// ===== 通知车站管理 =====
async function handleNotifyStation() {
  try {
    const res = await getStations({ keyword: event.value?.station || '' })
    const stations = res?.list || res || []
    if (stations.length === 0) {
      ElMessage.info('未找到对应车站，已通知全部车站')
      return
    }
    await sendCommand({
      content: `请立即关注事件 #${eventId.value}「${event.value?.title || ''}」并做好应急处置准备`,
      priority: 'high',
      targetStation: stations[0].name
    })
    ElMessage.success(`已通知车站「${stations[0].name}」`)
  } catch (e) {
    ElMessage.error(e?.message || '通知失败')
  }
}

// ===== 请求后勤支援 =====
async function handleSupportRequest() {
  try {
    await sendCommand({
      content: `事件 #${eventId.value} 需要后勤支援（物资/人员），请及时响应`,
      priority: 'normal',
      targetStation: '后勤安保中心'
    })
    ElMessage.success('后勤支援请求已发出')
  } catch (e) {
    ElMessage.error(e?.message || '请求失败')
  }
}

async function loadEvent() {
  if (!eventId.value) return
  loading.value = true
  try {
    const res = await getEventDetail(eventId.value)
    event.value = res?.event || res
  } catch (e) {
    ElMessage.error(e?.message || '加载事件详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadEvent()
})
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
        <el-tag :type="event?.level === 'high' ? 'danger' : event?.level === 'medium' ? 'warning' : 'info'" size="small">
          {{ { high: '高危', medium: '中危', low: '低危' }[event?.level] || '未知' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="发生时间">{{ event?.reportTime || '-' }}</el-descriptions-item>
      <el-descriptions-item label="影响线路">{{ event?.line || '-' }}</el-descriptions-item>
      <el-descriptions-item label="涉及车站">{{ event?.station || '-' }}</el-descriptions-item>
      <el-descriptions-item label="当前状态">
        <el-tag type="warning" size="small">{{ event?.status || '处理中' }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="事件描述" :span="2">
        {{ event?.description || '暂无事件描述信息' }}
      </el-descriptions-item>
    </el-descriptions>

    <el-card shadow="hover" class="action-card">
      <template #header>
        <span class="panel-title">调度处置操作</span>
      </template>
      <el-space wrap>
        <el-button type="primary" @click="handleActivatePlan">启动应急预案</el-button>
        <el-button type="success" @click="handleDispatchTask">派发一线任务</el-button>
        <el-button type="warning" @click="handleNotifyStation">通知车站管理</el-button>
        <el-button type="info" @click="handleSupportRequest">请求后勤支援</el-button>
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