<script setup>
import { ref, onMounted } from 'vue'
import { getTasks } from '@/api/task'

const taskList = ref([])
const taskFilter = ref('all')
const loading = ref(false)

const eventTypeLabels = {
  DEVICE_FAILURE: '设备故障', FIRE: '火灾火情', PASSENGER: '乘客事件',
  TRACK_OPERATION: '行车险情', CROWD_SECURITY: '客流治安', DISASTER_ENVIRONMENT: '灾害环境', OTHER: '其他'
}

async function loadTasks() {
  loading.value = true
  try {
    const status = taskFilter.value === 'all' ? 'ALL' : taskFilter.value.toUpperCase()
    const response = await getTasks({ status, page: 1, size: 50 })
    taskList.value = (response.data?.list || []).map(t => ({
      id: t.id,
      title: t.content,
      type: eventTypeLabels[t.eventType] || t.eventType || '其他',
      priority: 'normal',
      station: t.stationName,
      status: t.status === 'OVERDUE' ? 'overdue' : (t.status || '').toLowerCase()
    }))
  } catch {
    taskList.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadTasks)
</script>

<template>
  <div class="execution-page">
    <div class="page-title">
      <h2>一线任务执行</h2>
      <span class="page-subtitle">接收指令、执行任务、上报结果</span>
    </div>

    <el-card shadow="hover" class="panel-card">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">任务列表 ({{ taskList.length }})</span>
          <el-radio-group v-model="taskFilter" size="small" @change="loadTasks">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="pending">待执行</el-radio-button>
            <el-radio-button value="in_progress">执行中</el-radio-button>
            <el-radio-button value="completed">已完成</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="taskList" size="small">
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column prop="title" label="任务名称" min-width="160" />
        <el-table-column prop="type" label="任务类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag
              :type="{ urgent: 'danger', high: 'warning', normal: '' }[row.priority]"
              size="small"
            >
              {{ { urgent: '紧急', high: '高', normal: '普通' }[row.priority] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="station" label="执行车站" width="100" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag
              :type="{
                pending: 'warning',
                in_progress: 'primary',
                completed: 'success',
                overdue: 'danger'
              }[row.status]"
              size="small"
            >
              {{ { pending: '待执行', in_progress: '进行中', completed: '已完成', overdue: '已逾期' }[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="$router.push(`/execution/${row.id}`)"
            >
              任务详情
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="success"
              link
              size="small"
            >
              开始执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.execution-page {
  min-height: 100%;
}

.page-title {
  margin-bottom: 24px;
}

.page-title h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--metro-text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--metro-text-muted);
  margin-top: 4px;
  display: block;
}

.panel-card {
  background: var(--metro-bg-card);
  border: 1px solid var(--metro-border);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--metro-text-primary);
}
</style>