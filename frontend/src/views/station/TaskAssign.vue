<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createStationEventTasks,
  getStationEventDetail,
  getStationPersonnelOptions
} from '@/api/station'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const event = ref(null)
const personnel = ref([])
const tasks = reactive([])

const eventId = computed(() => Number(route.query.eventId || route.query.sourceEventId || 0))
const typeLabels = {
  DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件',
  TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件',
  DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件'
}

function addTask(content = '') {
  tasks.push({ content, executorId: null, deadline: null })
}

function removeTask(index) {
  if (tasks.length === 1) {
    ElMessage.warning('至少保留一条处置任务')
    return
  }
  tasks.splice(index, 1)
}

function usePlan(plan) {
  const steps = String(plan.content || '')
    .split(/[①②③④⑤⑥⑦⑧⑨⑩]/)
    .map(item => item.trim().replace(/[；;]$/, ''))
    .filter(Boolean)
  steps.slice(0, 10).forEach(step => addTask(step))
  ElMessage.success(`已从“${plan.name}”提取 ${Math.min(steps.length, 10)} 条任务建议`)
}

async function loadData() {
  if (!eventId.value) {
    ElMessage.error('缺少关联事件，请从事件待办进入任务分配')
    router.replace('/station/event-todo')
    return
  }
  loading.value = true
  try {
    const [eventResponse, peopleResponse] = await Promise.all([
      getStationEventDetail(eventId.value),
      getStationPersonnelOptions()
    ])
    event.value = eventResponse.data
    personnel.value = peopleResponse.data || []
    if (tasks.length === 0) addTask(`现场核查并处置：${event.value.description}`)
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (tasks.some(task => !task.content?.trim() || !task.executorId)) {
    ElMessage.warning('请为每条任务填写任务内容并选择执行人员')
    return
  }
  submitting.value = true
  try {
    // 子任务由车站拆分派发，来源固定为“车站指派”（STATION），禁止标记为调度指令
    const response = await createStationEventTasks(eventId.value, {
      source: 'STATION',
      tasks: tasks.map(task => ({
        content: task.content.trim(),
        executorId: task.executorId,
        deadline: task.deadline || null
      }))
    })
    ElMessage.success(`已成功分派 ${response.data.created} 条任务`)
    router.push('/station/progress')
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="assign-page" v-loading="loading">
    <div class="page-header">
      <h2>任务分配</h2>
      <span class="page-desc">根据事件和匹配预案拆分子任务，分派给本站在岗的一线或后勤人员。</span>
    </div>

    <el-card v-if="event" shadow="hover" class="event-card">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="事件编号">{{ event.eventNo }}</el-descriptions-item>
        <el-descriptions-item label="事件类型">{{ typeLabels[event.eventType] }}</el-descriptions-item>
        <el-descriptions-item label="事发车站">{{ event.stationName }}</el-descriptions-item>
        <el-descriptions-item label="事件描述" :span="3">{{ event.description }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="event?.plans?.length" shadow="hover" class="plan-card">
      <template #header><span>AI 匹配预案（可一键提取任务建议）</span></template>
      <div v-for="plan in event.plans" :key="plan.id" class="plan-item">
        <div>
          <strong>{{ plan.name }}</strong>
          <el-tag size="small" class="plan-level">{{ plan.level }}</el-tag>
          <p>{{ plan.content }}</p>
        </div>
        <el-button type="primary" plain @click="usePlan(plan)">提取为任务</el-button>
      </div>
    </el-card>

    <el-card shadow="hover" class="task-card">
      <template #header>
        <div class="card-header">
          <span>站内处置子任务</span>
          <el-button type="primary" plain @click="addTask()">新增任务</el-button>
        </div>
      </template>

      <div v-for="(task, index) in tasks" :key="index" class="task-row">
        <div class="task-index">{{ index + 1 }}</div>
        <el-input
          v-model="task.content"
          type="textarea"
          :rows="2"
          maxlength="1000"
          show-word-limit
          placeholder="填写具体、可执行的处置任务"
          class="task-content"
        />
        <el-select
          v-model="task.executorId"
          filterable
          placeholder="选择本站在岗执行人员"
          class="executor-select"
        >
          <el-option-group label="一线执行人员">
            <el-option
              v-for="person in personnel.filter(item => item.role === 'FRONT')"
              :key="person.id"
              :label="`${person.name} · ${person.postName}`"
              :value="person.id"
              :disabled="person.status !== 'ON_DUTY'"
            />
          </el-option-group>
          <el-option-group label="后勤安保人员">
            <el-option
              v-for="person in personnel.filter(item => item.role === 'SECURITY')"
              :key="person.id"
              :label="`${person.name} · ${person.postName}`"
              :value="person.id"
              :disabled="person.status !== 'ON_DUTY'"
            />
          </el-option-group>
        </el-select>
        <el-date-picker
          v-model="task.deadline"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="完成时限（可选）"
          class="deadline"
        />
        <el-button type="danger" link @click="removeTask(index)">删除</el-button>
      </div>

      <div class="actions">
        <el-button @click="router.push('/station/event-todo')">返回待办</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">确认并批量分派</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.assign-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0; font-size: 22px; color: var(--metro-text-primary); }
.page-desc { display: block; margin-top: 5px; color: var(--metro-text-muted); font-size: 13px; }
.event-card, .plan-card, .task-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.plan-item { display: flex; justify-content: space-between; gap: 20px; padding: 14px 0; border-bottom: 1px solid var(--metro-border); }
.plan-item:last-child { border-bottom: 0; }
.plan-item p { margin: 8px 0 0; color: var(--metro-text-muted); line-height: 1.7; white-space: pre-wrap; }
.plan-level { margin-left: 8px; }
.task-row { display: grid; grid-template-columns: 34px minmax(260px, 1fr) 230px 200px 50px; align-items: center; gap: 12px; margin-bottom: 16px; }
.task-index { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: var(--el-color-primary-light-8); color: var(--el-color-primary); }
.executor-select, .deadline { width: 100%; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
@media (max-width: 1100px) {
  .task-row { grid-template-columns: 34px 1fr; }
  .executor-select, .deadline { grid-column: 2; }
}
</style>
