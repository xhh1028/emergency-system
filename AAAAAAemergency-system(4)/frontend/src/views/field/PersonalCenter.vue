<script setup>
import { computed, onMounted, ref } from 'vue'
import { getProfileApi } from '@/api/auth'
import ChangePasswordCard from '@/components/ChangePasswordCard.vue'

const loading = ref(false)
const profile = ref(null)

const statusInfo = computed(() => ({
  ON_DUTY: { label: '在岗', type: 'success' },
  REST: { label: '轮休', type: 'warning' },
  LEAVE: { label: '请假', type: 'danger' },
  OUT: { label: '临时外出', type: 'info' },
  DISABLED: { label: '账号停用', type: 'danger' }
}[profile.value?.status] || { label: profile.value?.status || '未知', type: 'info' }))

async function loadProfile() {
  loading.value = true
  try {
    const response = await getProfileApi()
    profile.value = response.data
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="personal-center-page" v-loading="loading">
    <div class="page-header">
      <h2>个人中心</h2>
      <span>账号、岗位和所属车站信息均来自系统用户数据库</span>
    </div>

    <el-card shadow="never" class="profile-card">
      <template #header>
        <div class="card-header">
          <strong>个人资料</strong>
          <el-tag v-if="profile" :type="statusInfo.type">{{ statusInfo.label }}</el-tag>
        </div>
      </template>
      <el-skeleton v-if="loading && !profile" :rows="4" animated />
      <el-descriptions v-else-if="profile" :column="2" border>
        <el-descriptions-item label="姓名">{{ profile.realName }}</el-descriptions-item>
        <el-descriptions-item label="登录账号">{{ profile.phone }}</el-descriptions-item>
        <el-descriptions-item label="人员类别">{{ profile.roleName }}</el-descriptions-item>
        <el-descriptions-item label="具体岗位">{{ profile.postName || '尚未配置' }}</el-descriptions-item>
        <el-descriptions-item label="所属线路">{{ profile.lineName ? `${profile.lineName}号线` : '尚未配置' }}</el-descriptions-item>
        <el-descriptions-item label="所属车站">{{ profile.stationName || '尚未配置' }}</el-descriptions-item>
        <el-descriptions-item label="在岗状态" :span="2">
          <el-tag :type="statusInfo.type">{{ statusInfo.label }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="未取得个人资料" />
    </el-card>

    <ChangePasswordCard />
  </div>
</template>

<style scoped>
.personal-center-page{min-height:100%}.page-header{margin-bottom:20px}.page-header h2{margin:0;color:var(--metro-text-primary);font-size:22px}.page-header span{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.profile-card{border:1px solid var(--metro-border);background:var(--metro-bg-card)}.card-header{display:flex;justify-content:space-between;align-items:center}.card-header strong{color:var(--metro-text-primary);font-size:16px}
</style>
