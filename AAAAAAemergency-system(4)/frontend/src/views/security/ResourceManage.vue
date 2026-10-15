<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getResources, transferResource, replenishResource, inventoryResource } from '@/api/security'

const resourceList = ref([])
const loading = ref(false)

// ===== 调拨 =====
async function handleTransfer(row) {
  try {
    await transferResource(row.id, { toStation: '目标车站', qty: 1 })
    ElMessage.success(`已发起「${row.name}」调拨申请`)
  } catch (e) {
    ElMessage.error(e?.message || '调拨失败')
  }
}

// ===== 补充 =====
async function handleReplenish(row) {
  try {
    await replenishResource(row.id, { qty: 10 })
    ElMessage.success(`已发起「${row.name}」补充申请`)
  } catch (e) {
    ElMessage.error(e?.message || '补充失败')
  }
}

// ===== 盘点 =====
async function handleInventory(row) {
  try {
    await inventoryResource(row.id, { actualQty: row.available })
    ElMessage.success(`「${row.name}」盘点完成`)
  } catch (e) {
    ElMessage.error(e?.message || '盘点失败')
  }
}

async function loadResources() {
  loading.value = true
  try {
    const res = await getResources({})
    const list = res?.list || res?.data || []
    resourceList.value = Array.isArray(list) ? list : []
  } catch (e) {
    resourceList.value = []
    ElMessage.error(e?.message || '资源列表加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadResources()
})
</script>

<template>
  <div class="resource-page">
    <el-page-header @back="$router.go(-1)">
      <template #content>
        <span class="page-title-text">资源调度管理</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" class="panel-card" style="margin-top: 20px">
      <template #header>
        <span class="panel-title">全部应急资源</span>
      </template>
      <el-table :data="resourceList" v-loading="loading" size="small">
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column prop="name" label="资源名称" width="140" />
        <el-table-column prop="total" label="总量" width="80" />
        <el-table-column prop="available" label="可用数量" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.available < row.total * 0.3 ? 'var(--metro-danger)' : 'var(--metro-success)' }">
              {{ row.available }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="存放位置" width="140" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleTransfer(row)">调拨</el-button>
            <el-button type="warning" link size="small" @click="handleReplenish(row)">补充</el-button>
            <el-button type="info" link size="small" @click="handleInventory(row)">盘点</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.resource-page {
  min-height: 100%;
}

.page-title-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--metro-text-primary);
}

.panel-card {
  background: var(--metro-bg-card);
  border: 1px solid var(--metro-border);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--metro-text-primary);
}
</style>