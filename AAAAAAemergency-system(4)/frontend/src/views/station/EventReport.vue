<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStationEventDetail } from '@/api/station'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const event = ref(null)
const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}
const levelLabels = { GENERAL: '一般', SERIOUS: '严重', EXTREMELY_SERIOUS: '非常严重' }

async function loadEvent() {
  const eventId = Number(route.query.eventId || 0)
  if (!eventId) {
    ElMessage.error('缺少关联事件，请从事件待办进入')
    router.replace('/station/event-todo')
    return
  }
  loading.value = true
  try {
    event.value = (await getStationEventDetail(eventId)).data
  } finally {
    loading.value = false
  }
}

function images(urls) {
  return urls ? String(urls).split(';').filter(Boolean) : []
}

onMounted(loadEvent)
</script>

<template>
  <div class="report-page" v-loading="loading">
    <div class="page-header">
      <h2>事件上报调度</h2>
      <span class="page-desc">事件原始信息、AI 研判和匹配预案已完整同步至调度指挥中心。</span>
    </div>

    <el-alert
      title="上报成功：调度中心已可在事件管理中查看并确认该险情。"
      type="success"
      :closable="false"
      show-icon
      class="success-alert"
    />

    <el-card v-if="event" shadow="hover">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="事件编号">{{ event.eventNo }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">已上报调度</el-descriptions-item>
        <el-descriptions-item label="事件类型">{{ typeLabels[event.eventType] }}</el-descriptions-item>
        <el-descriptions-item label="事发车站">{{ event.stationName }}</el-descriptions-item>
        <el-descriptions-item label="车站复核等级">{{ levelLabels[event.finalLevel] }}</el-descriptions-item>
        <el-descriptions-item label="事件描述" :span="2">{{ event.description }}</el-descriptions-item>
        <el-descriptions-item v-if="images(event.imageUrls).length" label="现场图片" :span="2">
          <el-image
            v-for="url in images(event.imageUrls)"
            :key="url"
            :src="url"
            :preview-src-list="images(event.imageUrls)"
            class="event-image"
            fit="cover"
          />
        </el-descriptions-item>
      </el-descriptions>

      <div class="plans" v-if="event.plans?.length">
        <h3>同步的 AI 匹配预案</h3>
        <el-collapse>
          <el-collapse-item v-for="plan in event.plans" :key="plan.id" :title="`${plan.name}（${plan.level}）`">
            <div class="plan-content">{{ plan.content }}</div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="actions">
        <el-button type="primary" @click="router.push('/station/event-todo')">返回事件待办</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.report-page { min-height: 100%; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; color: var(--metro-text-primary); }
.page-desc { display: block; margin-top: 5px; color: var(--metro-text-muted); font-size: 13px; }
.success-alert { margin-bottom: 16px; }
.event-image { width: 100px; height: 100px; margin-right: 8px; border-radius: 4px; }
.plans { margin-top: 24px; }
.plans h3 { font-size: 16px; }
.plan-content { white-space: pre-wrap; line-height: 1.8; }
.actions { display: flex; justify-content: flex-end; margin-top: 24px; }
</style>
