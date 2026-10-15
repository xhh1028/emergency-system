<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDispatchEventDetail, sendDispatchEventCommand } from '@/api/dispatch'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const sending = ref(false)
const event = ref(null)
const form = reactive({ finalLevel: 'III_MAJOR', content: '' })
const eventId = computed(() => Number(route.query.eventId || 0))
const finalLevels = [
  { label: 'Ⅳ级（一般）', value: 'IV_GENERAL' }, { label: 'Ⅲ级（较大）', value: 'III_MAJOR' },
  { label: 'Ⅱ级（重大）', value: 'II_SERIOUS' }, { label: 'Ⅰ级（特别重大）', value: 'I_EXTREMELY_SERIOUS' }
]
const typeLabels = { DEVICE_FAILURE: '设备类故障', FIRE: '火灾火情事件', PASSENGER: '乘客人员事件', TRACK_OPERATION: '轨道异物及行车险情', CROWD_SECURITY: '大客流与治安事件', DISASTER_ENVIRONMENT: '灾害与环境事件', OTHER: '其他突发事件' }

async function loadEvent() {
  if (!eventId.value) { ElMessage.warning('请从事件管理中选择已确认的严重事件'); router.replace('/dispatch/event'); return }
  loading.value = true
  try {
    event.value = (await getDispatchEventDetail(eventId.value)).data
    if (!event.value.dispatchConfirmed) { ElMessage.warning('该事件尚未确认，请先确认已阅'); router.replace('/dispatch/event'); return }
    if (event.value.status !== 'REPORTED_TO_DISPATCH') { ElMessage.warning('该事件当前不能下发指令'); router.replace('/dispatch/event'); return }
    form.content = `请${event.value.stationName}立即依据应急预案开展${typeLabels[event.value.eventType] || '突发事件'}处置，做好现场隔离、人员疏散和进度反馈，并及时报告处置结果。`
  } finally { loading.value = false }
}
async function send() {
  if (!form.content.trim()) return ElMessage.warning('请输入正式处置指令')
  sending.value = true
  try { await sendDispatchEventCommand(eventId.value, { finalLevel: form.finalLevel, content: form.content.trim() }); ElMessage.success('指令已下发至事件所属车站'); router.push('/dispatch/event') }
  finally { sending.value = false }
}
onMounted(loadEvent)
</script>

<template>
  <div class="command-page" v-loading="loading">
    <div class="page-header"><h2>指令下发</h2><span class="page-desc">为已确认的严重事件填写法定等级，并向事件所属车站下发正式处置指令。</span></div>
    <el-card v-if="event" shadow="hover">
      <el-descriptions :column="2" border><el-descriptions-item label="事件编号">{{event.eventNo}}</el-descriptions-item><el-descriptions-item label="接收车站">{{event.lineName}}号线 {{event.stationName}}</el-descriptions-item><el-descriptions-item label="事件类型">{{typeLabels[event.eventType]||event.eventType}}</el-descriptions-item><el-descriptions-item label="AI研判等级">{{event.aiLevel}}</el-descriptions-item><el-descriptions-item label="事件描述" :span="2">{{event.description}}</el-descriptions-item></el-descriptions>
      <el-divider/>
      <el-form label-width="120px" class="command-form">
        <el-form-item label="法定事件等级"><el-select v-model="form.finalLevel" style="width:280px"><el-option v-for="item in finalLevels" :key="item.value" :label="item.label" :value="item.value"/></el-select></el-form-item>
        <el-form-item label="处置指令"><el-input v-model="form.content" type="textarea" :rows="8" maxlength="2000" show-word-limit placeholder="填写具体、可执行的处置要求"/></el-form-item>
        <el-form-item><el-button @click="router.back()">返回</el-button><el-button type="primary" :loading="sending" @click="send">确认下发</el-button></el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>.command-page{min-height:100%}.page-header{margin-bottom:24px}.page-header h2{margin:0;font-size:22px}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.command-form{margin-top:8px;max-width:900px}</style>
