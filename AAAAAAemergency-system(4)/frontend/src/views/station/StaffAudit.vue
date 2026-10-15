<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 车站管理员 - 人员状态审核（前端 mock：审核本站人员状态变更申请）
const applicationList = ref([])
const statusFilter = ref('')
const detailDialogVisible = ref(false)
const selectedRecord = ref(null)

// mock：本站人员状态变更申请
const MOCK_APPLICATIONS = [
  { id: 1, name: '张执行', username: 'zhangx', position: '站务员', applyTime: '2026-08-04 09:30', targetStatus: 'rest', targetStatusLabel: '轮休', reason: '家中临时有事，申请调休', attachments: ['调休申请单.jpg'], result: 'pending' },
  { id: 2, name: '周安保', username: 's_security', position: '安保人员', applyTime: '2026-08-04 10:15', targetStatus: 'out', targetStatusLabel: '临时外出', reason: '领取应急物资，外出审批', attachments: ['外出审批单.pdf'], result: 'pending' },
  { id: 3, name: '吴医护', username: 's_medical', position: '医护人员', applyTime: '2026-08-03 16:40', targetStatus: 'leave', targetStatusLabel: '请假', reason: '身体不适，请假一天', attachments: ['请假条.jpg', '医院证明.pdf'], result: 'approved' },
  { id: 4, name: '郑仓管', username: 's_warehouse', position: '物资库房管理员', applyTime: '2026-08-02 14:20', targetStatus: 'rest', targetStatusLabel: '轮休', reason: '周末值班调休', attachments: [], result: 'rejected' }
]

const statusLabelMap = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
const statusTagMap = { pending: 'warning', approved: 'success', rejected: 'danger' }

const filteredList = computed(() => {
  return applicationList.value.filter(item => {
    return !statusFilter.value || item.result === statusFilter.value
  })
})

function showDetail(record) {
  selectedRecord.value = record
  detailDialogVisible.value = true
}

function handleAudit(record, pass) {
  record.result = pass ? 'approved' : 'rejected'
  ElMessage.success(pass ? `已通过 ${record.name} 的状态变更申请` : `已驳回 ${record.name} 的状态变更申请`)
}

function loadData() {
  applicationList.value = MOCK_APPLICATIONS.map(item => ({ ...item }))
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="audit-page">
    <div class="page-header">
      <h2>人员状态审核</h2>
      <span class="page-desc">审核本站人员（一线执行与后勤安保）的状态变更申请</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <div class="toolbar">
        <el-select v-model="statusFilter" placeholder="审核状态" clearable style="width: 140px">
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
      </div>

      <el-table :data="filteredList" stripe border style="width: 100%">
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="position" label="岗位" width="140" />
        <el-table-column prop="applyTime" label="申请时间" width="170" />
        <el-table-column prop="targetStatusLabel" label="目标状态" width="100" />
        <el-table-column prop="reason" label="申请原因" min-width="200" show-overflow-tooltip />
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.result]" size="small">{{ statusLabelMap[row.result] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <template v-if="row.result === 'pending'">
              <el-button type="success" size="small" @click="handleAudit(row, true)">通过</el-button>
              <el-button type="danger" size="small" @click="handleAudit(row, false)">驳回</el-button>
            </template>
            <el-button v-else type="primary" link size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog title="申请详情" v-model="detailDialogVisible" width="520px">
      <div v-if="selectedRecord">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="姓名">{{ selectedRecord.name }}</el-descriptions-item>
          <el-descriptions-item label="岗位">{{ selectedRecord.position }}</el-descriptions-item>
          <el-descriptions-item label="申请时间">{{ selectedRecord.applyTime }}</el-descriptions-item>
          <el-descriptions-item label="目标状态">{{ selectedRecord.targetStatusLabel }}</el-descriptions-item>
          <el-descriptions-item label="申请原因" :span="2">{{ selectedRecord.reason }}</el-descriptions-item>
          <el-descriptions-item label="申请材料" :span="2">
            <el-tag v-for="file in selectedRecord.attachments" :key="file" size="small" style="margin-right: 6px">
              {{ file }}
            </el-tag>
            <span v-if="!selectedRecord.attachments.length">未上传材料</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.audit-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.table-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>