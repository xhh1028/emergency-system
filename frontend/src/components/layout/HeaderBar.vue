<script setup>
import { ref, computed } from 'vue'
import { onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { useAppStore } from '@/store/modules/app'
import { useNotificationStore } from '@/store/modules/notification'
import { useRouter } from 'vue-router'

const userStore = useUserStore()
const appStore = useAppStore()
const notificationStore = useNotificationStore()
const router = useRouter()

const showAvatarFallback = ref(false)

const avatar = computed(() => userStore.userInfo?.avatar || '')
const initialLetter = computed(() => userStore.nickname?.charAt(0) || 'U')

function handleAvatarError() {
  showAvatarFallback.value = true
}

function handleLogout() {
  notificationStore.stopPolling()
  userStore.logout()
  router.push({ name: 'Login' })
}

function handleNotificationClick() {
  notificationStore.markAllAsRead()
}

onMounted(() => {
  notificationStore.startPolling()
})

onUnmounted(() => {
  notificationStore.stopPolling()
})

const roleTagConfig = {
  admin: { text: '调度指挥' },
  station: { text: '车站管理' },
  field: { text: '一线执行' },
  support: { text: '后勤安保' }
}
</script>

<template>
  <div class="header-bar">
    <div class="header-left">
      <div class="system-status">
        <span class="status-dot"></span>
        <span class="system-name">轨道交通应急管理系统</span>
      </div>
    </div>

    <div class="header-right">
      <!-- 消息通知红点：有未读消息时显示红色小圆点 -->
      <el-badge
        is-dot
        :hidden="notificationStore.unreadCount === 0"
        class="notification-badge"
      >
        <el-dropdown trigger="click" @command="handleNotificationClick">
          <el-button text class="notification-btn">
            <el-icon :size="22">
              <Bell />
            </el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu class="notification-menu">
              <div class="notification-header">
                <span>消息通知</span>
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click.stop="notificationStore.markAllAsRead()"
                >
                  全部已读
                </el-button>
              </div>
              <el-scrollbar height="300px">
                <div
                  v-for="msg in notificationStore.messages.slice(0, 10)"
                  :key="msg.id"
                  class="notification-item"
                  :class="{ unread: !msg.read }"
                  @click="notificationStore.markAsRead(msg.id)"
                >
                  <div class="notification-item-header">
                    <el-tag
                      size="small"
                      :type="msg.type === '新指令' ? 'danger' : msg.type === '任务更新' ? 'warning' : 'primary'"
                    >
                      {{ msg.type }}
                    </el-tag>
                    <span class="notification-time">{{ msg.time }}</span>
                  </div>
                  <div class="notification-title">{{ msg.title }}</div>
                  <div class="notification-content">{{ msg.content }}</div>
                </div>
                <el-empty
                  v-if="notificationStore.messages.length === 0"
                  description="暂无消息"
                  :image-size="60"
                />
              </el-scrollbar>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-badge>

      <span class="role-tag">{{ roleTagConfig[userStore.role]?.text }}</span>

      <div class="user-info">
        <div class="avatar-wrapper">
          <img 
            v-if="avatar && !showAvatarFallback" 
            :src="avatar" 
            class="user-avatar"
            @error="handleAvatarError"
            alt="头像"
          />
          <div v-else class="user-avatar-fallback">{{ initialLetter }}</div>
        </div>
        <span class="user-name">{{ userStore.nickname }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 20px;
  background: #111118;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00e5ff;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(0, 229, 255, 0.7);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(0, 229, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(0, 229, 255, 0);
  }
}

.system-name {
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.notification-badge {
  cursor: pointer;
}

/* 消息通知红点：未读时显示红色小圆点 */
.notification-badge :deep(.el-badge__content.is-dot) {
  background-color: #f3445a;
  border-color: #111118;
}

.notification-btn {
  padding: 8px;
}

.notification-menu {
  width: 320px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-weight: 600;
  color: #ffffff;
}

.notification-item {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: background-color 0.2s;
}

.notification-item:hover {
  background-color: rgba(255, 255, 255, 0.03);
}

.notification-item.unread {
  background-color: rgba(0, 229, 255, 0.08);
}

.notification-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.notification-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.notification-title {
  font-size: 13px;
  font-weight: 500;
  color: #ffffff;
  margin-bottom: 4px;
}

.notification-content {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.4;
}

.role-tag {
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: #00e5ff;
  background: rgba(0, 229, 255, 0.1);
  border: 1px solid rgba(0, 229, 255, 0.4);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar-wrapper {
  position: relative;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(0, 229, 255, 0.4);
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-avatar:hover {
  border-color: rgba(0, 229, 255, 0.8);
}

.user-avatar-fallback {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00e5ff, #7c5cfc);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  border: 2px solid rgba(0, 229, 255, 0.4);
  cursor: pointer;
}

.user-avatar::after {
  content: '';
  position: absolute;
  bottom: 1px;
  right: 1px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #00d68f;
  border: 2px solid #111118;
}

.user-name {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
}
</style>
