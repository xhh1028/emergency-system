<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 车站管理员 - 本站物资管理（前端 mock：可查看/新增/编辑本站物资）
const materialList = ref([])
const keyword = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const materialForm = reactive({
  id: null,
  material: '',
  category: '',
  total: 0,
  available: 0,
  location: '',
  status: 'normal'
})

const MOCK_MATERIALS = [
  { id: 1, material: '应急发电车', category: '电力设备', total: 3, available: 2, location: '设备库房A', status: 'normal' },
  { id: 2, material: '消防器材', category: '消防应急', total: 56, available: 50, location: '设备库房A', status: 'normal' },
  { id: 3, material: '医疗急救包', category: '医疗救援', total: 24, available: 20, location: '医务室', status: 'normal' },
  { id: 4, material: '应急照明', category: '电力设备', total: 36, available: 21, location: '设备库房B', status: 'warning' },
  { id: 5, material: '防护装备', category: '防护物资', total: 40, available: 35, location: '设备库房B', status: 'normal' }
]

const categoryOptions = ['电力设备', '消防应急', '医疗救援', '防护物资', '通讯设备']

const filteredList = computed(() => {
  return materialList.value.filter(item => {
    return !keyword.value || item.material.includes(keyword.value) || item.category.includes(keyword.value)
  })
})

function getStatusInfo(status) {
  if (status === 'normal') return { label: '充足', type: 'success' }
  if (status === 'warning') return { label: '库存偏低', type: 'warning' }
  return { label: '紧缺', type: 'danger' }
}

function openAdd() {
  isEdit.value = false
  Object.assign(materialForm, { id: null, material: '', category: '', total: 0, available: 0, location: '', status: 'normal' })
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  Object.assign(materialForm, { ...row })
  dialogVisible.value = true
}

function save() {
  if (!materialForm.material || !materialForm.category || materialForm.total <= 0) {
    ElMessage.warning('请填写物资名称、类别与库存总量')
    return
  }
  if (isEdit.value) {
    const index = materialList.value.findIndex(item => item.id === materialForm.id)
    if (index !== -1) materialList.value[index] = { ...materialForm }
    ElMessage.success('物资信息已更新')
  } else {
    materialList.value.unshift({ ...materialForm, id: Date.now() })
    ElMessage.success('物资已新增')
  }
  dialogVisible.value = false
}

function loadData() {
  materialList.value = MOCK_MATERIALS.map(item => ({ ...item }))
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="material-page">
    <div class="page-header">
      <h2>本站物资管理</h2>
      <span class="page-desc">管理本站应急物资库存，支持新增与编辑</span>
    </div>

    <el-card shadow="hover" class="table-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索物资名称或类别" clearable style="width: 220px" />
        <el-button type="primary" @click="openAdd">新增物资</el-button>
      </div>

      <el-table :data="filteredList" stripe border style="width: 100%">
        <el-table-column prop="material" label="物资名称" min-width="140" />
        <el-table-column prop="category" label="物资类别" width="120" />
        <el-table-column prop="total" label="库存总量" width="100" />
        <el-table-column prop="available" label="可用数量" width="100" />
        <el-table-column prop="location" label="存放位置" min-width="130" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusInfo(row.status).type" size="small">{{ getStatusInfo(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog :title="isEdit ? '编辑物资' : '新增物资'" v-model="dialogVisible" width="520px">
      <el-form label-width="100px">
        <el-form-item label="物资名称">
          <el-input v-model="materialForm.material" placeholder="请输入物资名称" />
        </el-form-item>
        <el-form-item label="物资类别">
          <el-select v-model="materialForm.category" placeholder="请选择类别" style="width: 100%">
            <el-option v-for="cat in categoryOptions" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="库存总量">
          <el-input-number v-model="materialForm.total" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="可用数量">
          <el-input-number v-model="materialForm.available" :min="0" :max="materialForm.total" style="width: 100%" />
        </el-form-item>
        <el-form-item label="存放位置">
          <el-input v-model="materialForm.location" placeholder="请输入存放位置" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.material-page { min-height: 100%; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; font-weight: 600; color: var(--metro-text-primary); margin: 0; }
.page-desc { font-size: 13px; color: var(--metro-text-muted); margin-top: 4px; display: block; }
.table-card { background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
</style>