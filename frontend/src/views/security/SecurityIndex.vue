<script setup>
import { ref, onMounted } from 'vue'
import { getResources, getSecurityPersonnel } from '@/api/security'

const resourceList = ref([])
const personnelList = ref([])

onMounted(async () => {
  try {
    const res = await getResources({})
    const list = res?.list || res?.data || []
    resourceList.value = Array.isArray(list) ? list : []
  } catch {
    resourceList.value = []
  }
  try {
    const res = await getSecurityPersonnel({})
    const list = res?.list || res?.data || []
    personnelList.value = (Array.isArray(list) ? list : []).map(p => ({
      ...p,
      status: p.status === 'ON_DUTY' ? 'on_duty' : 'off_duty'
    }))
  } catch {
    personnelList.value = []
  }
})
</script>

<template>
  <div class="security-page">
    <div class="page-title">
      <h2>后勤安保管理</h2>
      <span class="page-subtitle">资源调度、人员管理、安全保障</span>
    </div>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">应急资源清单</span>
              <el-button
                type="primary"
                size="small"
                @click="$router.push('/security/resources')"
              >
                资源调度
              </el-button>
            </div>
          </template>
          <el-table :data="resourceList" size="small">
            <el-table-column prop="name" label="资源名称" width="120" />
            <el-table-column prop="total" label="总量" width="80" />
            <el-table-column prop="available" label="可用" width="80">
              <template #default="{ row }">
                <span :style="{ color: row.available < 20 ? 'var(--metro-danger)' : 'var(--metro-success)' }">
                  {{ row.available }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="location" label="存放位置" width="120" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default>
                <el-tag type="success" size="small">正常</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <span class="panel-title">安保人员状态</span>
          </template>
          <div
            v-for="person in personnelList"
            :key="person.id"
            class="person-item"
          >
            <div class="person-info">
              <el-avatar :size="32" icon="UserFilled" />
              <div>
                <span class="person-name">{{ person.name }}</span>
                <span class="person-pos">{{ person.position }}</span>
              </div>
            </div>
            <el-tag
              :type="person.status === 'on_duty' ? 'success' : 'info'"
              size="small"
            >
              {{ person.status === 'on_duty' ? '在岗' : '离岗' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.security-page {
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
  margin-bottom: 16px;
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

.person-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--metro-border-light);
}

.person-item:last-child {
  border-bottom: none;
}

.person-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.person-name {
  display: block;
  font-size: 14px;
  color: var(--metro-text-primary);
}

.person-pos {
  display: block;
  font-size: 12px;
  color: var(--metro-text-muted);
  margin-top: 2px;
}
</style>