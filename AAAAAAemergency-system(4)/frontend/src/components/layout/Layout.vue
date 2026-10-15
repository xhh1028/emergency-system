<script setup>
import { computed, watch, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { useAppStore } from '@/store/modules/app'
import { useNotificationStore } from '@/store/modules/notification'
import { getUser } from '@/utils/auth'
import { 
  Fold, Expand, HomeFilled, Bell,
  DataAnalysis, Tickets, Document, Promotion, DataLine,
  Message, Position, Monitor, Warning, List, ChatLineSquare, Clock, Box, Lock, Tools, User
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()
const notificationStore = useNotificationStore()

const notificationDropdownVisible = ref(false)

onMounted(() => {
  notificationStore.startPolling()
})

onUnmounted(() => {
  notificationStore.stopPolling()
})

function handleBellClick() {
  notificationDropdownVisible.value = !notificationDropdownVisible
}

function handleMarkAllAsRead() {
  notificationStore.markAllAsRead()
}

function handleClickNotification(msg) {
  notificationStore.markAsRead(msg.id)
  notificationDropdownVisible.value = false
}

const userData = getUser()
const role = computed(() => userStore.role || userData?.role || '')
const nickname = computed(() => userStore.nickname || userData?.nickname || '用户')
const initialLetter = computed(() => nickname.value.charAt(0))

const roleLabel = computed(() => {
  const map = {
    admin: '调度指挥', station: '车站管理', field: '一线执行', support: '后勤安保',
    dispatch_center: '调度指挥中心', station_admin: '车站管理员'
  }
  return map[role.value] || '未知角色'
})

const iconMap = {
  DataAnalysis, Tickets, Document, Promotion, DataLine,
  Message, Position, Monitor, Warning, List, ChatLineSquare, Clock, Box, Lock, Tools, User
}

// 各角色与“任务/事件”相关的菜单路径：有新任务提醒时，在这些菜单右上角显示红点
const taskMenuPathMap = {
  admin: ['/dispatch/events', '/dispatch/commands'],
  station: ['/station/event-todo'],
  field: ['/field/tasks'],
  // 后勤安保的"任务待办"为新任务红点提示菜单
  support: ['/support/todos']
}

// 未读的任务相关通知（任务分配/任务更新/新指令/事件上报/物资调配等），用于驱动左侧菜单红点
const unreadTaskMessages = computed(() =>
  notificationStore.messages.filter(
    m => !m.read && (m.type.includes('任务') || m.type.includes('指令') || m.type.includes('事件') || m.type.includes('物资'))
  )
)

// 是否有新任务类提醒
const hasUnreadTask = computed(() => unreadTaskMessages.value.length > 0)

// 判断指定菜单项是否属于当前角色的任务类菜单（需要显示红点）
function isTaskMenuItem(path) {
  return (taskMenuPathMap[role.value] || []).includes(path)
}

const menuMap = {
  admin: [
    { title: '总览大屏', icon: 'DataAnalysis', path: '/dispatch/overview' },
    { title: '事件管理', icon: 'Tickets', path: '/dispatch/events' },
    { title: '预案管理', icon: 'Document', path: '/dispatch/plans' },
    { title: '指令下发', icon: 'Promotion', path: '/dispatch/commands' },
    { title: '全站进度', icon: 'DataLine', path: '/dispatch/progress' }
  ],
  station: [
    { title: '事件待办', icon: 'Tickets', path: '/station/event-todo' },
    { title: '指令接收', icon: 'Message', path: '/station/commands' },
    { title: '进度监控', icon: 'DataLine', path: '/station/progress' },
    { title: '人员管理', icon: 'User', path: '/station/personnel' }
  ],
  field: [
    { title: '险情上报', icon: 'Warning', path: '/field/report' },
    { title: '我的待办', icon: 'List', path: '/field/tasks' },
    { title: '历史记录', icon: 'Clock', path: '/field/history' },
    { title: '个人中心', icon: 'User', path: '/field/profile' }
  ],
  support: [
    { title: '险情上报', icon: 'Warning', path: '/support/report' },
    { title: '我的待办', icon: 'List', path: '/support/todos' },
    { title: '历史记录', icon: 'Clock', path: '/support/history' },
    { title: '个人中心', icon: 'User', path: '/support/profile' }
  ],
  // ============ 调度指挥中心（dispatch_center） ============
  dispatch_center: [
    { title: '总览大屏', icon: 'DataAnalysis', path: '/dispatch/overview' },
    { title: '事件管理', icon: 'Tickets', path: '/dispatch/event' },
    { title: '全线处置进度', icon: 'DataLine', path: '/dispatch/progress' },
    { title: '指令下发', icon: 'Promotion', path: '/dispatch/command' },
    { title: '预案管理', icon: 'Document', path: '/dispatch/plan' },
    { title: '全线物资总览', icon: 'Box', path: '/dispatch/material' },
    { title: '事件归档', icon: 'Clock', path: '/dispatch/archive' }
  ],
  // ============ 车站管理员（station_admin） ============
  station_admin: [
    { title: '事件管理', icon: 'Tickets', path: '/station/event' },
    { title: '任务分配', icon: 'Position', path: '/station/taskAssign' },
    { title: '安保值守', icon: 'Lock', path: '/station/securityWatch' },
    { title: '人员状态审核', icon: 'User', path: '/station/staffAudit' },
    { title: '本站物资管理', icon: 'Box', path: '/station/material' },
    { title: '事件归档', icon: 'Clock', path: '/station/archive' }
  ]
}

const menuItems = computed(() => {
  return menuMap[role.value] || []
})

const activeMenu = computed(() => route.path)

watch(
  () => route.meta.title,
  (title) => {
    appStore.setRouteTitle(title || '')
  },
  { immediate: true }
)

// 点击左侧菜单时，如果是任务相关菜单，将任务类通知标记为已读，红点自动消失
function handleSelect(path) {
  router.push(path)
  markTaskNotificationsAsRead(path)
}

// 将未读的任务类通知全部标记为已读（点击任务相关菜单后消除红点）
function markTaskNotificationsAsRead(path) {
  if (!isTaskMenuItem(path)) return
  notificationStore.messages.forEach(msg => {
    if (!msg.read && (msg.type.includes('任务') || msg.type.includes('指令') || msg.type.includes('事件') || msg.type.includes('物资'))) {
      msg.read = true
    }
  })
}

function handleLogout() {
  userStore.logout()
  router.push({ name: 'Login' })
}

function handleDropdownCommand() {
  handleLogout()
}
</script>

<template>
  <div class="layout-wrapper">
    <header class="layout-header">
      <div class="header-left">
        <el-button
          text
          class="collapse-btn"
          @click="appStore.toggleSidebar()"
        >
          <el-icon :size="18">
            <Fold v-if="!appStore.sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
        </el-button>
        <el-breadcrumb separator="/" class="breadcrumb">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item v-if="appStore.currentRouteTitle">{{ appStore.currentRouteTitle }}</el-breadcrumb-item>
        </el-breadcrumb>
      </div>

      <div class="header-right">
        <span class="role-tag">{{ roleLabel }}</span>
        
        <el-dropdown v-model:visible="notificationDropdownVisible" trigger="click">
          <div class="bell-icon" @click="handleBellClick">
            <el-icon :size="20"><Bell /></el-icon>
            <!-- 消息通知红点：有未读消息时显示红色小圆点 -->
            <el-badge 
              v-if="notificationStore.unreadCount > 0" 
              is-dot 
              class="notification-badge" 
            />
          </div>
          <template #dropdown>
            <el-dropdown-menu class="notification-dropdown">
              <div class="notification-header">
                <span>消息通知</span>
                <el-button 
                  link 
                  type="primary" 
                  size="small" 
                  @click.stop="handleMarkAllAsRead"
                  v-if="notificationStore.unreadCount > 0"
                >
                  全部已读
                </el-button>
              </div>
              <el-dropdown-item 
                v-for="msg in notificationStore.messages.slice(0, 8)" 
                :key="msg.id"
                @click="handleClickNotification(msg)"
                class="notification-item"
                :class="{ 'item-unread': !msg.read }"
              >
                <div class="notification-type">{{ msg.type }}</div>
                <div class="notification-content">{{ msg.content }}</div>
                <div class="notification-time">{{ msg.time }}</div>
              </el-dropdown-item>
              <el-dropdown-item 
                v-if="notificationStore.messages.length === 0" 
                disabled 
                class="notification-empty"
              >
                暂无消息
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        
        <el-dropdown @command="() => handleLogout()" trigger="click">
          <div class="user-avatar" style="cursor: pointer">{{ initialLetter }}</div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="layout-body">
      <aside
        class="layout-sidebar"
        :class="{ collapsed: appStore.sidebarCollapsed }"
      >
        <div class="sidebar-inner">
          <div class="sidebar-logo">
            <div class="logo-icon">
              <svg viewBox="0 0 32 32" class="logo-svg">
                <path d="M 4 16 L 28 16" stroke="#0a84ff" stroke-width="2" stroke-linecap="round"/>
                <path d="M 8 20 L 24 20" stroke="#0a84ff" stroke-width="2" stroke-linecap="round"/>
                <circle cx="16" cy="16" r="3" fill="#0a84ff"/>
                <circle cx="16" cy="20" r="3" fill="#0a84ff"/>
                <circle cx="16" cy="18" r="2" fill="#1c1c1e"/>
              </svg>
            </div>
            <div v-show="!appStore.sidebarCollapsed" class="logo-text">
              <span class="logo-main">轨交应急</span>
              <span class="logo-sub">应急管理平台</span>
            </div>
          </div>

          <nav class="sidebar-menu">
            <div v-show="!appStore.sidebarCollapsed" class="menu-group-title">导航菜单</div>
            <div
              v-for="item in menuItems"
              :key="item.path"
              class="menu-item"
              :class="{ active: activeMenu.includes(item.path) }"
              @click="handleSelect(item.path)"
            >
              <el-icon class="menu-icon"><component :is="iconMap[item.icon]" /></el-icon>
              <span v-show="!appStore.sidebarCollapsed" class="menu-text">{{ item.title }}</span>
              <!-- 新任务红点提示：任务相关菜单且有未读的任务类通知时，在右上角显示红色小圆点 -->
              <span v-if="hasUnreadTask && isTaskMenuItem(item.path)" class="menu-dot"></span>
            </div>
          </nav>


        </div>
      </aside>

      <main class="layout-main">
        <div class="layout-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg-base);
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 24px;
  background: rgba(28,28,30,0.85);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  color: var(--text-secondary);
  padding: 4px;
  background: transparent;
}

.collapse-btn:hover {
  color: var(--text-primary);
}

.breadcrumb {
  font-size: 13px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bell-icon {
  position: relative;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  transition: all 0.2s;
}

.bell-icon:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

/* 消息通知红点：未读时显示红色小圆点 */
.notification-badge :deep(.el-badge__content.is-dot) {
  background-color: #f3445a;
  border-color: var(--bg-base);
}

.notification-dropdown :deep(.el-dropdown-menu__item) {
  line-height: 1.4;
  padding: 8px 12px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.notification-item {
  padding: 10px 12px !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.notification-item:last-of-type {
  border-bottom: none;
}

.notification-item.item-unread {
  background: rgba(255, 255, 255, 0.04);
}

.notification-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
}

.notification-type {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 4px;
}

.notification-content {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.notification-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.notification-empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: 20px !important;
}

.role-tag {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid var(--border);
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #ffffff;
}

.layout-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.layout-sidebar {
  width: 220px;
  height: 100vh;
  flex-shrink: 0;
  transition: width 0.3s ease;
  overflow: hidden;
  background: rgba(28,28,30,0.95);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.layout-sidebar.collapsed {
  width: 64px;
}

.sidebar-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
}

.logo-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-svg {
  width: 100%;
  height: 100%;
}

.logo-symbol {
  font-size: 14px;
  color: #ffffff;
}

.logo-text {
  display: flex;
  flex-direction: column;
  margin-left: 10px;
}

.logo-main {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.logo-sub {
  font-size: 10px;
  color: var(--text-tertiary);
  letter-spacing: 0.3px;
}

.sidebar-menu {
  flex: 1;
  padding: 0 0 8px 0;
  overflow-y: auto;
}

.menu-group-title {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.8px;
  padding: 16px 16px 6px;
  text-transform: uppercase;
}

.menu-item {
  height: 38px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  margin: 1px 8px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

/* 新任务红点：任务相关菜单右上角的红色小圆点 */
.menu-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f3445a;
  flex-shrink: 0;
  margin-left: 6px;
  animation: dot-pulse 1.6s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(243, 68, 90, 0.4);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(243, 68, 90, 0);
  }
}

.menu-item:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.menu-item.active {
  color: var(--accent);
  background: rgba(10,132,255,0.15);
  font-weight: 500;
}

.menu-icon {
  font-size: 14px;
  margin-right: 9px;
  color: inherit;
}

.menu-item.active .menu-icon {
  color: var(--accent);
}

.menu-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-user {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar-sidebar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  flex-shrink: 0;
}

.user-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 11px;
  color: var(--text-tertiary);
}

.logout-icon {
  font-size: 16px;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: color 0.15s ease;
}

.logout-icon:hover {
  color: var(--red);
}

.layout-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.layout-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: var(--bg-base);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
