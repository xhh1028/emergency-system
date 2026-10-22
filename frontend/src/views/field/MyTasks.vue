<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Clock, OfficeBuilding, Search } from '@element-plus/icons-vue'
import { getTasks, startTask } from '@/api/task'
import { useUserStore } from '@/store/modules/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const tasks = ref([])
const total = ref(0)
const query = reactive({ status: 'ALL', keyword: '', page: 1, size: 9 })

const statusLabels = {
  PENDING: '待执行', IN_PROGRESS: '执行中', COMPLETED: '已完成', OVERDUE: '已逾期'
}
const statusTypes = {
  PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', OVERDUE: 'danger'
}
const sourceLabels = { STATION: '车站分派', DISPATCH: '调度指令' }

function formatTime(value) {
  if (!value) return '未设置'
  return String(value).replace('T', ' ').slice(0, 16)
}

async function loadTasks() {
  loading.value = true
  try {
    const response = await getTasks(query)
    tasks.value = response.data?.list || []
    total.value = response.data?.total || 0
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  loadTasks()
}

async function handleStart(task) {
  await startTask(task.id)
  ElMessage.success('任务已开始执行，处置进度已更新')
  await loadTasks()
}

function handleDetail(task) {
  router.push({
    name: userStore.role === 'support' ? 'SupportTaskDetail' : 'FieldTaskDetail',
    params: { id: task.id }
  })
}

onMounted(loadTasks)
</script>

<template>
  <div class="tasks-page">
    <div class="page-header">
      <div>
        <h2>我的待办</h2>
        <p>这里只展示分配给当前账号的真实处置任务</p>
      </div>
    </div>

    <el-card shadow="never" class="task-panel">
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          :prefix-icon="Search"
          clearable
          placeholder="搜索任务内容、事件编号或车站"
          @keyup.enter="search"
          @clear="search"
        />
        <el-select v-model="query.status" @change="search">
          <el-option label="全部任务" value="ALL" />
          <el-option label="待执行" value="PENDING" />
          <el-option label="执行中" value="IN_PROGRESS" />
          <el-option label="已完成" value="COMPLETED" />
          <el-option label="已逾期" value="OVERDUE" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
      </div>

      <el-skeleton v-if="loading" :rows="6" animated />
      <template v-else>
        <el-row v-if="tasks.length" :gutter="16" class="task-grid">
          <el-col v-for="task in tasks" :key="task.id" :xs="24" :sm="12" :xl="8">
            <el-card shadow="hover" class="task-card" @click="handleDetail(task)">
              <div class="task-top">
                <el-tag :type="statusTypes[task.status]">{{ statusLabels[task.status] }}</el-tag>
                <span>{{ sourceLabels[task.source] || task.source }}</span>
              </div>
              <h3>{{ task.content }}</h3>
              <div class="task-number">{{ task.taskNo }} · {{ task.eventNo }}</div>
              <div class="task-info">
                <span><el-icon><OfficeBuilding /></el-icon>{{ task.lineName }} {{ task.stationName }}</span>
                <span><el-icon><Clock /></el-icon>截止 {{ formatTime(task.deadline) }}</span>
              </div>
              <div class="task-actions" @click.stop>
                <el-button
                  v-if="task.rawStatus === 'PENDING'"
                  type="primary"
                  @click="handleStart(task)"
                >开始执行</el-button>
                <el-button @click="handleDetail(task)">查看详情</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-else description="当前没有符合条件的任务" />
        <el-pagination
          v-if="total > query.size"
          v-model:current-page="query.page"
          :page-size="query.size"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="loadTasks"
        />
      </template>
    </el-card>
  </div>
</template>

<style scoped>
.tasks-page { min-height: 100%; }
.page-header { display: flex; justify-content: space-between; margin-bottom: 18px; }
.page-header h2 { margin: 0; color: var(--metro-text-primary); font-size: 22px; }
.page-header p { margin: 6px 0 0; color: var(--metro-text-muted); font-size: 13px; }
.task-panel { border: 1px solid var(--metro-border); background: var(--metro-bg-card); }
.toolbar { display: flex; gap: 12px; margin-bottom: 18px; }
.toolbar .el-input { max-width: 360px; }
.toolbar .el-select { width: 150px; }
.task-grid { margin-bottom: 6px; }
.task-card { margin-bottom: 16px; cursor: pointer; border-left: 3px solid var(--metro-accent); }
.task-top { display: flex; justify-content: space-between; align-items: center; color: var(--metro-text-muted); font-size: 12px; }
.task-card h3 { min-height: 44px; margin: 14px 0 8px; color: var(--metro-text-primary); font-size: 16px; line-height: 1.45; }
.task-number { margin-bottom: 14px; color: var(--metro-text-muted); font-size: 12px; }
.task-info { display: grid; gap: 8px; margin-bottom: 14px; color: var(--metro-text-secondary); font-size: 13px; }
.task-info span { display: flex; align-items: center; gap: 6px; }
.task-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.el-pagination { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 640px) { .toolbar { flex-wrap: wrap; } .toolbar .el-input { max-width: none; } }
</style>
