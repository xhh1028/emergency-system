<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEventStore } from '@/store'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const eventStore = useEventStore()
const eventId = Number(route.params.id)
const loading = ref(false)
const newFiles = ref([]) // 临时文件列表（模拟）
const uploadType = ref('事故总结')

const event = computed(() => eventStore.getEventById(eventId))

function handleFileInput(e) {
  const files = Array.from(e.target.files || [])
  files.forEach(f => {
    newFiles.value.push({ name: f.name, size: f.size, uid: Date.now() + Math.random() })
  })
}

function removeNewFile(file) {
  const idx = newFiles.value.findIndex(f => f.uid === file.uid)
  if (idx !== -1) newFiles.value.splice(idx, 1)
}

// 上传事后复盘材料（前端演示存储到 pinia）
function submitPostmortem() {
  if (!event.value) return ElMessage.error('未找到事件')
  if (newFiles.value.length === 0) return ElMessage.warning('请选择要上传的附件')

  const pm = eventStore.addPostmortem(eventId, {
    type: uploadType.value,
    files: newFiles.value.map(f => ({ name: f.name, uid: f.uid })),
    uploader: '本站'
  })
  if (pm) {
    newFiles.value = []
    ElMessage.success('上传成功，等待站内确认接收')
  } else {
    ElMessage.error('上传失败')
  }
}

function onConfirm(pm) {
  // 站内管理人员确认接收
  const res = eventStore.confirmPostmortem(eventId, pm.id, '站管理')
  if (res) ElMessage.success('已确认接收')
}

function onSync(pm) {
  // 同步到调度中心（演示为前端标记）
  if (pm.status !== 'received') return ElMessage.warning('请先确认接收后再同步')
  const res = eventStore.syncPostmortem(eventId, pm.id, '站管理')
  if (res) ElMessage.success('已同步到调度中心（演示）')
}

onMounted(() => {
  if (!event.value) {
    ElMessage.error('事件不存在或已被删除')
    router.back()
  }
})
</script>

<template>
  <div class="event-detail-page">
    <el-page-header @back="$router.go(-1)">
      <template #content>
        <span class="page-title-text">事件详情 #{{ eventId }}</span>
      </template>
    </el-page-header>

    <div v-if="event" class="detail-container">
      <el-descriptions :column="2" border class="detail-desc" size="small">
        <el-descriptions-item label="事件编号">EVT-{{ event.id }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag :type="eventStore.statusTagMap[event.status]">{{ eventStore.statusLabelMap[event.status] }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="发生时间">{{ event.reportTime }}</el-descriptions-item>
        <el-descriptions-item label="所属车站">{{ event.station }}</el-descriptions-item>
        <el-descriptions-item label="事件描述" :span="2">{{ event.description }}</el-descriptions-item>
      </el-descriptions>

      <el-card shadow="hover" class="materials-card">
        <template #header>
          <span class="panel-title">事件材料</span>
        </template>

        <el-tabs type="card">
          <!-- 处置过程：使用现有 timeline 字段展示实时上报记录 -->
          <el-tab-pane label="处置过程" name="process">
            <div class="timeline-wrap">
              <el-timeline>
                <el-timeline-item
                  v-for="item in event.timeline"
                  :key="item.time + item.status"
                  :timestamp="item.time"
                >
                  <strong>{{ item.label }}</strong>
                  <div class="timeline-detail">{{ item.operator }}：{{ item.description }}</div>
                </el-timeline-item>
              </el-timeline>
            </div>
          </el-tab-pane>

          <!-- 事后复盘：事故总结报告、处置台账 -->
          <el-tab-pane label="事后复盘" name="postmortem">
            <div class="postmortem-panel">
              <div class="upload-section">
                <div class="upload-controls">
                  <el-select v-model="uploadType" placeholder="请选择材料类型" style="width:200px">
                    <el-option label="事故总结报告" value="事故总结" />
                    <el-option label="处置台账" value="处置台账" />
                  </el-select>
                  <label class="file-input">
                    <input type="file" multiple @change="handleFileInput" />
                    <el-button type="info" size="small">选择附件</el-button>
                  </label>
                  <el-button type="primary" size="small" @click="submitPostmortem">上传</el-button>
                </div>

                <div class="selected-files" v-if="newFiles.length">
                  <div v-for="f in newFiles" :key="f.uid" class="file-item">
                    <span>{{ f.name }}</span>
                    <el-button type="text" icon="Close" @click="removeNewFile(f)">移除</el-button>
                  </div>
                </div>
              </div>

              <div class="existing-postmortems" style="margin-top:20px">
                <div v-if="!(event.postmortems && event.postmortems.length)">尚未上传事后复盘材料</div>
                <el-table v-else :data="event.postmortems" style="width:100%">
                  <el-table-column prop="type" label="材料类型" width="140" />
                  <el-table-column label="文件列表">
                    <template #default="{ row }">
                      <div v-for="f in row.files" :key="f.uid">{{ f.name }}</div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" label="状态" width="120">
                    <template #default="{ row }">
                      <el-tag v-if="row.status==='uploaded'" type="warning">待接收</el-tag>
                      <el-tag v-else-if="row.status==='received'" type="success">已接收</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="260">
                    <template #default="{ row }">
                      <el-button size="small" @click="onConfirm(row)" :disabled="row.status==='received'">确认接收</el-button>
                      <el-button size="small" type="primary" @click="onSync(row)" :disabled="row.status!=='received' || row.synced">同步上报调度中心</el-button>
                      <el-button size="small" type="text" @click="">查看</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.event-detail-page { padding: 16px }
.page-title-text { font-size: 18px; font-weight: 600 }
.detail-desc { margin-top: 12px }
.materials-card { margin-top: 16px }
.timeline-detail { margin-top: 6px; color: var(--text-tertiary) }
.upload-controls { display:flex; align-items:center; gap:12px }
.selected-files { margin-top: 8px }
.file-item { display:flex; align-items:center; gap:8px; padding:6px 8px; background: rgba(0,0,0,0.03); border-radius:6px }
</style>