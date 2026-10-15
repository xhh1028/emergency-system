<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createPersonnel,
  getPersonnel,
  getPersonnelPosts,
  resetPersonnelPassword,
  updatePersonnel
} from '@/api/station'

const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const personnel = ref([])
const posts = ref([])
const dialogVisible = ref(false)
const resetVisible = ref(false)
const editMode = ref(false)
const resetTarget = ref(null)
const search = reactive({ keyword: '', role: '', postId: '' })
const form = reactive({ id: null, realName: '', phone: '', role: 'FRONT', postId: null, status: 'ON_DUTY', initialPassword: '' })
const resetForm = reactive({ newPassword: '', confirmPassword: '' })

const roleOptions = [
  { label: '一线执行人员', value: 'FRONT' },
  { label: '后勤安保人员', value: 'SECURITY' }
]
const statusOptions = [
  { label: '在岗', value: 'ON_DUTY', type: 'success' },
  { label: '轮休', value: 'REST', type: 'warning' },
  { label: '请假', value: 'LEAVE', type: 'danger' },
  { label: '临时外出', value: 'OUT', type: 'primary' }
]

const rolePosts = computed(() => posts.value.filter(item => item.role === form.role))
const filteredRows = computed(() => {
  const keyword = search.keyword.trim().toLowerCase()
  return personnel.value.filter(item => {
    const matchesKeyword = !keyword || [item.name, item.phone, item.postName]
      .some(value => String(value || '').toLowerCase().includes(keyword))
    return matchesKeyword && (!search.role || item.role === search.role)
      && (!search.postId || item.postId === search.postId)
  })
})

function roleLabel(value) { return roleOptions.find(item => item.value === value)?.label || value }
function statusLabel(value) { return statusOptions.find(item => item.value === value)?.label || value }
function statusType(value) { return statusOptions.find(item => item.value === value)?.type || 'info' }

async function loadData() {
  loading.value = true
  try {
    const [peopleResponse, postsResponse] = await Promise.all([getPersonnel(), getPersonnelPosts()])
    personnel.value = peopleResponse.data || []
    posts.value = postsResponse.data || []
  } finally { loading.value = false }
}

function openAdd() {
  editMode.value = false
  Object.assign(form, { id: null, realName: '', phone: '', role: 'FRONT', postId: null, status: 'ON_DUTY', initialPassword: '' })
  dialogVisible.value = true
}

function openEdit(row) {
  editMode.value = true
  Object.assign(form, {
    id: row.id, realName: row.name, phone: row.phone, role: row.role,
    postId: row.postId, status: row.status, initialPassword: ''
  })
  dialogVisible.value = true
}

function validateForm() {
  if (!form.realName.trim()) return ElMessage.warning('请输入人员姓名'), false
  if (!/^1\d{10}$/.test(form.phone)) return ElMessage.warning('请输入正确的11位手机号码'), false
  if (!form.postId) return ElMessage.warning('请选择具体岗位'), false
  if (!editMode.value && (form.initialPassword.length < 6 || form.initialPassword.length > 32)) {
    return ElMessage.warning('初始密码长度必须为6至32位'), false
  }
  return true
}

async function save() {
  if (!validateForm()) return
  saving.value = true
  try {
    const payload = {
      realName: form.realName.trim(), phone: form.phone, role: form.role,
      postId: form.postId, status: form.status,
      initialPassword: editMode.value ? null : form.initialPassword
    }
    if (editMode.value) await updatePersonnel(form.id, payload)
    else await createPersonnel(payload)
    ElMessage.success(editMode.value ? '人员信息已更新' : '人员账号已新增')
    dialogVisible.value = false
    await loadData()
  } finally { saving.value = false }
}

function openReset(row) {
  resetTarget.value = row
  resetForm.newPassword = ''
  resetForm.confirmPassword = ''
  resetVisible.value = true
}

async function submitReset() {
  if (resetForm.newPassword.length < 6 || resetForm.newPassword.length > 32) return ElMessage.warning('新密码长度必须为6至32位')
  if (resetForm.newPassword !== resetForm.confirmPassword) return ElMessage.warning('两次输入的密码不一致')
  resetting.value = true
  try {
    await resetPersonnelPassword(resetTarget.value.id, { newPassword: resetForm.newPassword })
    ElMessage.success(`已为${resetTarget.value.name}重置密码`)
    resetVisible.value = false
  } finally { resetting.value = false }
}

watch(() => form.role, () => {
  if (!rolePosts.value.some(item => item.id === form.postId)) form.postId = null
})
onMounted(loadData)
</script>

<template>
  <div class="personnel-page">
    <div class="page-header">
      <h2>人员管理</h2>
      <span class="page-desc">管理本站一线执行和后勤安保人员账号、岗位及在岗状态；员工忘记密码时可由管理员安全重置。</span>
    </div>

    <el-card shadow="hover" class="filter-card">
      <div class="toolbar">
        <el-input v-model="search.keyword" placeholder="搜索姓名、手机号或岗位" clearable class="keyword" />
        <el-select v-model="search.role" placeholder="人员类别" clearable style="width: 170px">
          <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="search.postId" placeholder="具体岗位" clearable style="width: 190px">
          <el-option v-for="item in posts" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-button type="primary" @click="openAdd">新增人员</el-button>
      </div>
    </el-card>

    <el-card shadow="hover" class="table-card">
      <el-table :data="filteredRows" v-loading="loading" stripe empty-text="本站暂无工作人员" style="width: 100%">
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="phone" label="登录手机号" width="150" />
        <el-table-column label="人员类别" width="150">
          <template #default="{ row }"><el-tag :type="row.role === 'SECURITY' ? 'warning' : 'primary'">{{ roleLabel(row.role) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="postName" label="具体岗位" min-width="170" />
        <el-table-column label="在岗状态" width="120">
          <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" min-width="210" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button type="warning" link @click="openReset(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editMode ? '编辑人员' : '新增人员'" width="570px">
      <el-form label-width="110px">
        <el-form-item label="姓名"><el-input v-model="form.realName" maxlength="40" show-word-limit /></el-form-item>
        <el-form-item label="登录手机号"><el-input v-model="form.phone" maxlength="11" placeholder="该手机号同时作为登录账号" /></el-form-item>
        <el-form-item label="人员类别">
          <el-radio-group v-model="form.role"><el-radio v-for="item in roleOptions" :key="item.value" :value="item.value">{{ item.label }}</el-radio></el-radio-group>
        </el-form-item>
        <el-form-item label="具体岗位">
          <el-select v-model="form.postId" placeholder="请选择与人员类别对应的岗位" style="width: 100%">
            <el-option v-for="item in rolePosts" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="在岗状态">
          <el-select v-model="form.status" style="width: 100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
        </el-form-item>
        <el-form-item v-if="!editMode" label="初始密码"><el-input v-model="form.initialPassword" type="password" show-password placeholder="6至32位，保存后仅本人使用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置员工密码" width="500px">
      <el-alert v-if="resetTarget" :title="`正在为 ${resetTarget.name}（${resetTarget.phone}）设置新密码`" type="warning" :closable="false" show-icon />
      <el-form label-width="100px" class="reset-form">
        <el-form-item label="新密码"><el-input v-model="resetForm.newPassword" type="password" show-password placeholder="6至32位" /></el-form-item>
        <el-form-item label="确认密码"><el-input v-model="resetForm.confirmPassword" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer><el-button @click="resetVisible = false">取消</el-button><el-button type="warning" :loading="resetting" @click="submitReset">确认重置</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.personnel-page{min-height:100%}.page-header{margin-bottom:24px}.page-header h2{margin:0;font-size:22px;color:var(--metro-text-primary)}.page-desc{display:block;margin-top:5px;color:var(--metro-text-muted);font-size:13px}.filter-card,.table-card{border:1px solid var(--metro-border);background:var(--metro-bg-card)}.table-card{margin-top:16px}.toolbar{display:flex;flex-wrap:wrap;gap:12px}.keyword{width:300px}.reset-form{margin-top:20px}
</style>
