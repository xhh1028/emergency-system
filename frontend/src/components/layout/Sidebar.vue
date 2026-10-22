<script setup>import { computed, ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useUserStore } from '@/store/modules/user';
import { useNotificationStore } from '@/store/modules/notification';
import { getUser } from '@/utils/auth';
import { DataAnalysis, Tickets, Document, Promotion, DataLine, Message, Position, Monitor, Warning, List, ChatLineSquare, Clock, Box, Lock, Tools, SwitchButton, User } from '@element-plus/icons-vue';
const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const notificationStore = useNotificationStore();
const userData = getUser();
const role = computed(() => userStore.role || userData?.role || '');
const nickname = computed(() => userStore.nickname || userData?.nickname || '用户');
const avatar = computed(() => userStore.userInfo?.avatar || userData?.avatar || '');
const showAvatarFallback = ref(false);
const iconMap = {
 DataAnalysis, Tickets, Document, Promotion, DataLine,
 Message, Position, Monitor, Warning, List, ChatLineSquare, Clock, Box, Lock, Tools, User
};

// 各角色与“任务/事件”相关的菜单路径：有新任务提醒时，在这些菜单右上角显示红点
const taskMenuPathMap = {
 admin: ['/dispatch/events', '/dispatch/commands'],
 station: ['/station/event-todo'],
 field: ['/field/tasks'],
 // 后勤安保的"任务待办"为新任务红点提示菜单
 support: ['/support/todos']
};

// 未读的任务相关通知（任务分配/任务更新/新指令/事件上报/物资调配等），用于驱动左侧菜单红点
const unreadTaskMessages = computed(() =>
 notificationStore.messages.filter(
 m => !m.read && (m.type.includes('任务') || m.type.includes('指令') || m.type.includes('事件') || m.type.includes('物资'))
 )
);

// 是否有新任务类提醒
const hasUnreadTask = computed(() => unreadTaskMessages.value.length > 0);

// 判断指定菜单项是否属于当前角色的任务类菜单（需要显示红点）
function isTaskMenuItem(path) {
 return (taskMenuPathMap[role.value] || []).includes(path);
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
 { title: '故障上报', icon: 'Warning', path: '/field/report' },
 { title: '我的待办', icon: 'List', path: '/field/tasks' },
 { title: '历史记录', icon: 'Clock', path: '/field/history' },
 { title: '个人中心', icon: 'User', path: '/field/profile' }
 ],
  support: [
  { title: '险情上报', icon: 'Warning', path: '/support/report' },
  { title: '我的待办', icon: 'List', path: '/support/todos' },
  { title: '历史记录', icon: 'Clock', path: '/support/history' },
  { title: '个人中心', icon: 'User', path: '/support/profile' }
  ]
};
const menuList = computed(() => {
 return menuMap[role.value] || [];
});
const currentPath = computed(() => route.path);
// 点击左侧菜单时，如果是任务相关菜单，将任务类通知标记为已读，红点自动消失
function handleMenuClick(path) {
 router.push(path);
 if (isTaskMenuItem(path)) {
   // 将未读的任务类通知全部标记为已读（点击任务相关菜单后消除红点）
   notificationStore.messages.forEach(msg => {
     if (!msg.read && (msg.type.includes('任务') || msg.type.includes('指令') || msg.type.includes('事件') || msg.type.includes('物资'))) {
       msg.read = true;
     }
   });
 }
}
function handleLogout() {
 userStore.logout();
 router.push('/login');
}
function handleAvatarError() {
 showAvatarFallback.value = true;
}
const initialLetter = computed(() => nickname.value?.charAt(0) || '管');
const roleLabel = computed(() => {
 const roleMap = {
 admin: '调度指挥',
 station: '车站管理',
 field: '一线执行',
 support: '后勤安保'
 };
 return roleMap[role.value] || '未知角色';
});

const showPersonnelPanel = computed(() => role.value === 'station');
// 人员基本信息为前端静态参考数据（展示用），实际业务数据均从后端接口获取
const personnelInfoList = ref([
  { id: 1, name: '车站值班站长', position: '值班站长', phone: '—', status: 'on_duty' },
  { id: 2, name: '站务员', position: '站务员', phone: '—', status: 'on_duty' },
  { id: 3, name: '安保人员', position: '安保人员', phone: '—', status: 'on_duty' },
  { id: 4, name: '客运员', position: '客运员', phone: '—', status: 'rest' }
]);

function getPersonnelStatusLabel(status) {
 return {
 ON_DUTY: '在岗',
 OFF_DUTY: '离岗',
 on_duty: '空闲',
 rest: '轮休',
 leave: '请假',
 out: '临时外出'
 }[status] || '未知';
}
</script>

<template>
  <div class="sidebar">
    <div class="logo-area">
      <span class="logo-icon">⚡</span>
      <div class="logo-text">
        <span class="logo-main">轨交应急</span>
        <span class="logo-sub">METRO EMERGENCY</span>
      </div>
      <div class="logo-divider"></div>
    </div>

    <div v-if="showPersonnelPanel" class="personnel-panel">
      <div class="panel-title">人员基本信息</div>
      <div v-for="person in personnelInfoList" :key="person.id" class="person-row">
        <div class="person-name">{{ person.name }}</div>
        <div class="person-detail">{{ person.position }} · {{ person.phone }}</div>
        <div class="person-status">{{ getPersonnelStatusLabel(person.status) }}</div>
      </div>
    </div>

    <div class="menu-list">
      <div
        v-for="item in menuList"
        :key="item.path"
        class="menu-item"
        :class="{ active: currentPath.includes(item.path) }"
        @click="handleMenuClick(item.path)"
      >
        <el-icon class="menu-icon"><component :is="iconMap[item.icon]" /></el-icon>
        <span class="menu-text">{{ item.title }}</span>
        <!-- 新任务红点提示：任务相关菜单且有未读的任务类通知时，在右上角显示红色小圆点 -->
        <span v-if="hasUnreadTask && isTaskMenuItem(item.path)" class="menu-dot"></span>
      </div>
    </div>

    <div class="user-area">
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
      <div class="user-info">
        <span class="user-name">{{ nickname }}</span>
        <span class="user-role">{{ roleLabel }}</span>
      </div>
      <el-icon class="logout-icon" @click="handleLogout"><SwitchButton /></el-icon>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  width: 200px;
  height: 100vh;
  background: #111118;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.logo-area {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  position: relative;
}

.logo-icon {
  font-size: 20px;
  color: #00e5ff;
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-main {
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.logo-sub {
  font-size: 9px;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.35);
}

.logo-divider {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
}

.menu-list {
  flex: 1;
  overflow-y: auto;
  padding-top: 8px;
}

.menu-item {
  height: 46px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: rgba(255, 255, 255, 0.5);
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
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.85);
}

.menu-item.active {
  background: rgba(0, 229, 255, 0.1);
  color: #00e5ff;
  border-left: 3px solid #00e5ff;
  padding-left: 17px;
}

.menu-icon {
  font-size: 16px;
  margin-right: 10px;
}

.personnel-panel {
  margin: 16px 16px 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: #e5e7eb;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 12px;
}

.person-row {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.person-row:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.person-name {
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
}

.person-detail {
  margin-top: 4px;
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.5;
}

.person-status {
  margin-top: 8px;
  display: inline-block;
  font-size: 10px;
  color: #10b981;
  background: rgba(16, 185, 129, 0.12);
  padding: 2px 6px;
  border-radius: 999px;
}


.menu-text {
  font-size: 13px;
}

.user-area {
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar-wrapper {
  flex-shrink: 0;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
}

.user-avatar-fallback {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00e5ff, #7c5cfc);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
}

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

.logout-icon {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.45);
  cursor: pointer;
  transition: color 0.2s;
}

.logout-icon:hover {
  color: #ff4d6d;
}
</style>
