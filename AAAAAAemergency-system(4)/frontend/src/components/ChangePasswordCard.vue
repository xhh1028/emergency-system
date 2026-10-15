<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePasswordApi } from '@/api/auth'
import { useUserStore } from '@/store/modules/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

function validateConfirm(rule, value, callback) {
  if (value !== form.newPassword) callback(new Error('两次输入的新密码不一致'))
  else callback()
}

const rules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度必须为6到64位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

async function submit() {
  if (!formRef.value) return
  await formRef.value.validate()
  loading.value = true
  try {
    await changePasswordApi({ oldPassword: form.oldPassword, newPassword: form.newPassword })
    ElMessage.success('密码修改成功，请使用新密码重新登录')
    userStore.logout()
    router.push({ name: 'Login' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card shadow="hover" class="password-card">
    <div class="card-heading">
      <div class="card-title">修改登录密码</div>
      <div class="card-desc">修改成功后当前登录状态会失效，需要使用新密码重新登录。</div>
    </div>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" class="password-form">
      <el-form-item label="原密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">确认修改</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.password-card { margin-top: 16px; background: var(--metro-bg-card); border: 1px solid var(--metro-border); }
.card-heading { padding-bottom: 18px; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,.08); }
.card-title { color: var(--metro-text-primary); font-size: 16px; font-weight: 600; }
.card-desc { margin-top: 6px; color: var(--metro-text-muted); font-size: 13px; }
.password-form { max-width: 560px; }
</style>
