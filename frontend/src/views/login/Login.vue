<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import { getRolesApi } from '@/api/auth'
import { clearAuth } from '@/utils/auth'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const selectedRole = ref('')

// 登录身份数据：由后端 GET /api/auth/roles 动态拉取，不再写死在前端
const roleOptions = ref([])
// 身份列表加载状态
const rolesLoading = ref(false)

// 后端接口暂未就绪时的兜底身份数据（保证登录页可用，接口就绪后自动被覆盖）
const FALLBACK_ROLES = [
  { roleKey: 'admin', roleName: '调度指挥', defaultPath: '/dispatch/overview' },
  { roleKey: 'station', roleName: '车站管理', defaultPath: '/station/event-todo' },
  { roleKey: 'field', roleName: '一线执行', defaultPath: '/field/tasks' },
  { roleKey: 'support', roleName: '后勤安保', defaultPath: '/support/todos' }
]

// 挂载时从后端拉取登录身份列表
async function fetchRoles() {
  rolesLoading.value = true
  try {
    const res = await getRolesApi()
    // 兼容两种返回结构：直接数组 或 { data: [...] }
    const list = Array.isArray(res) ? res : (res?.data || [])
    if (list.length > 0) {
      roleOptions.value = list
    }
  } catch {
    // 接口失败时使用兜底身份，保证登录页不空白
    roleOptions.value = FALLBACK_ROLES
  } finally {
    rolesLoading.value = false
  }
}

function handleRoleChange(roleKey) {
  selectedRole.value = roleKey
}

onMounted(() => {
  // 进入登录页时清空本地残留的旧会话（token/用户/时间戳），
  // 避免旧版本代码留下的不完整登录状态导致首次登录后又被路由守卫弹回
  clearAuth()
  fetchRoles()
})

async function handleLogin() {
  // 空字段给出明确提示，避免“点了没反应”造成需要重复输入
  if (!username.value.trim()) {
    ElMessage.warning('请输入登录手机号')
    return
  }
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }
  // 防止加载中重复提交
  if (loading.value) return

  loading.value = true
  try {
    // trim 去除手机号首尾空格，避免因多余空格导致“用户名或密码错误”
    await userStore.login(username.value.trim(), password.value)
    // 按后端返回的真实账号角色跳转对应业务首页
    const roleDefaultPath = {
      dispatch_center: '/dispatch/overview',
      admin: '/dispatch/overview',
      station: '/station/event-todo',
      station_admin: '/station/event',
      field: '/field/tasks',
      support: '/support/todos'
    }
    const selectedRoleItem = roleOptions.value.find((r) => r.roleKey === selectedRole.value)
    const defaultPath = roleDefaultPath[userStore.role] || selectedRoleItem?.defaultPath || '/dashboard'
    await router.push(defaultPath)
  } catch {
    // 登录失败时，axios 拦截器已弹出具体原因，这里仅复位按钮状态
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="glow-top"></div>
    <div class="glow-bottom"></div>
    
    <div class="login-card">
      <div class="brand-section">
        <div class="logo-icon">
          <svg viewBox="0 0 48 48" class="logo-svg">
            <path d="M 6 24 L 42 24" stroke="#0a84ff" stroke-width="3" stroke-linecap="round"/>
            <path d="M 12 30 L 36 30" stroke="#0a84ff" stroke-width="3" stroke-linecap="round"/>
            <circle cx="24" cy="24" r="4" fill="#0a84ff"/>
            <circle cx="24" cy="30" r="4" fill="#0a84ff"/>
            <circle cx="24" cy="27" r="3" fill="#1c1c1e"/>
          </svg>
        </div>
        <h1 class="brand-title">轨道交通应急管理系统</h1>
        <p class="brand-subtitle">城市级应急指挥调度平台</p>
      </div>

      <div class="form-section">
        <div class="select-wrap">
          <select
            v-model="selectedRole"
            class="form-select"
            @change="handleRoleChange(selectedRole)"
          >
            <option value="" disabled selected>
              {{ rolesLoading ? '身份加载中…' : '选择登录身份' }}
            </option>
            <option v-for="role in roleOptions" :key="role.roleKey" :value="role.roleKey">
              {{ role.roleName }}
            </option>
          </select>
          <span class="select-arrow">›</span>
        </div>

        <input
          v-model="username"
          type="text"
          class="form-input"
          placeholder="手机号（系统登录账号为本人手机号）"
          @keyup.enter="handleLogin"
        />
        
        <div class="password-wrap">
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            class="form-input"
            placeholder="密码"
            @keyup.enter="handleLogin"
          />
          <button
            type="button"
            class="password-toggle"
            @click="showPassword = !showPassword"
          >
            {{ showPassword ? '隐藏' : '显示' }}
          </button>
        </div>
      </div>

      <button
        type="button"
        class="login-btn"
        :disabled="loading"
        @click="handleLogin"
      >
        {{ loading ? '登录中…' : '登录' }}
      </button>

      <p class="demo-hint">请使用本人手机号和登录密码进入系统</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  width: 100vw;
  min-height: 100vh;
  background: var(--bg-base);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.glow-top {
  position: fixed;
  top: -200px;
  left: 50%;
  transform: translateX(-50%);
  width: 800px;
  height: 600px;
  background: radial-gradient(ellipse, rgba(10,132,255,0.06) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.glow-bottom {
  position: fixed;
  bottom: -100px;
  right: -100px;
  width: 500px;
  height: 500px;
  background: radial-gradient(ellipse, rgba(48,209,88,0.04) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.login-card {
  width: 400px;
  padding: 48px 40px;
  background: rgba(44,44,46,0.8);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  backdrop-filter: blur(60px) saturate(150%);
  box-shadow: 0 40px 80px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);
  position: relative;
  z-index: 1;
}

.brand-section {
  text-align: center;
}

.logo-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  box-shadow: 0 8px 24px rgba(10,132,255,0.4);
}

.logo-symbol {
  font-size: 22px;
  color: #ffffff;
}

.logo-svg {
  width: 100%;
  height: 100%;
}

.brand-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
  margin: 0 0 6px;
}

.brand-subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  font-weight: 400;
  margin: 0;
}

.form-section {
  margin-top: 36px;
}

.select-wrap {
  position: relative;
  margin-bottom: 10px;
}

.form-select {
  width: 100%;
  height: 46px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 0 36px 0 14px;
  font-size: 15px;
  color: var(--text-primary);
  font-family: inherit;
  outline: none;
  transition: all 0.2s ease;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.form-select:invalid {
  color: var(--text-tertiary);
}

.form-select option {
  background: #2c2c2e;
  color: var(--text-primary);
  padding: 12px;
}

.form-select:focus {
  border-color: rgba(10,132,255,0.6);
  box-shadow: 0 0 0 3px rgba(10,132,255,0.15);
  background: rgba(255, 255, 255, 0.08);
}

.select-arrow {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%) rotate(90deg);
  font-size: 18px;
  color: var(--text-tertiary);
  pointer-events: none;
  line-height: 1;
}

.form-input {
  width: 100%;
  height: 46px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 0 14px;
  font-size: 15px;
  color: var(--text-primary);
  font-family: inherit;
  outline: none;
  transition: all 0.2s ease;
  margin-bottom: 10px;
  box-sizing: border-box;
}

.form-input::placeholder {
  color: var(--text-tertiary);
}

.form-input:focus {
  border-color: rgba(10,132,255,0.6);
  box-shadow: 0 0 0 3px rgba(10,132,255,0.15);
  background: rgba(255, 255, 255, 0.08);
}

.password-wrap {
  position: relative;
}

.password-toggle {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: var(--accent);
  font-weight: 500;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s ease;
  font-family: inherit;
  padding: 0;
}

.password-toggle:hover {
  color: var(--accent-hover);
}

.login-btn {
  width: 100%;
  height: 46px;
  margin-top: 20px;
  border-radius: 10px;
  background: var(--accent);
  border: none;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: -0.1px;
  box-shadow: 0 4px 16px rgba(10,132,255,0.4);
  transition: all 0.2s ease;
  font-family: inherit;
}

.login-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 6px 20px rgba(10,132,255,0.5);
}

.login-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.demo-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
  margin: 16px 0 0;
}
</style>
