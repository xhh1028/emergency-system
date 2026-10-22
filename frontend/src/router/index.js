import { createRouter, createWebHashHistory } from 'vue-router'
import { getToken, getUser, getLoginAt, clearAuth } from '@/utils/auth'

// 本地会话有效期（毫秒）：登录后超过该时长未再登录，重新打开网页时需要重新登录。
// 默认 8 小时（一个工作时段）；"不小心关闭又很快重新打开"的短时间重开不受影响。
const SESSION_TIMEOUT = 8 * 60 * 60 * 1000

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/Login.vue'),
    meta: { title: '用户登录', noAuth: true }
  },
  {
    path: '/',
    component: () => import('@/components/layout/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Dashboard.vue'),
        meta: {
          title: '应急指挥看板',
          icon: 'Odometer',
          roles: ['admin', 'station', 'field', 'support', 'dispatch_center', 'station_admin']
        }
      },
      // 注：dispatch/overview 与 dispatch/progress 由下方"调度指挥中心"路由统一提供（兼容 admin + dispatch_center）
      {
        path: 'dispatch/events',
        name: 'DispatchEvents',
        component: () => import('@/views/dispatch/EventManagement.vue'),
        meta: {
          title: '事件管理',
          icon: 'Tickets',
          roles: ['admin']
        }
      },
      {
        path: 'dispatch/plans',
        name: 'DispatchPlans',
        component: () => import('@/views/dispatch/PlanManagement.vue'),
        meta: {
          title: '预案管理',
          icon: 'Document',
          roles: ['admin']
        }
      },
      {
        path: 'dispatch/commands',
        name: 'DispatchCommands',
        component: () => import('@/views/dispatch/CommandDispatch.vue'),
        meta: {
          title: '指令下发',
          icon: 'Promotion',
          roles: ['admin']
        }
      },
      {
        path: 'station/event-todo',
        name: 'StationEventTodo',
        component: () => import('@/views/station/EventTodo.vue'),
        meta: {
          title: '事件待办',
          icon: 'Tickets',
          roles: ['station']
        }
      },
      {
        path: 'station/commands',
        name: 'StationCommands',
        component: () => import('@/views/station/CommandReceive.vue'),
        meta: {
          title: '指令接收',
          icon: 'Message',
          roles: ['station']
        }
      },
      {
        path: 'station/assign',
        name: 'StationAssign',
        component: () => import('@/views/station/TaskAssign.vue'),
        meta: {
          title: '任务分配',
          icon: 'Position',
          hidden: true,
          roles: ['station']
        }
      },
      {
        path: 'station/progress',
        name: 'StationProgress',
        component: () => import('@/views/station/ProgressMonitor.vue'),
        meta: {
          title: '进度监控',
          icon: 'DataLine',
          roles: ['station']
        }
      },
      {
        // 第二层：按事件钻取，展示该事件全部子任务
        path: 'station/progress/event/:id',
        name: 'StationEventProgress',
        component: () => import('@/views/station/EventProgress.vue'),
        meta: {
          title: '事件处置详情',
          roles: ['station']
        }
      },
      {
        // 第三层：钻取单条子任务，查看一线完成说明与现场图片
        path: 'station/progress/task/:id',
        name: 'StationTaskProgressDetail',
        component: () => import('@/views/station/TaskProgressDetail.vue'),
        meta: {
          title: '子任务处置详情',
          roles: ['station']
        }
      },
      {
        path: 'station/report',
        name: 'StationReport',
        component: () => import('@/views/station/EventReport.vue'),
        meta: {
          title: '事件上报',
          icon: 'Warning',
          hidden: true,
          roles: ['station']
        }
      },
      {
        path: 'station/personnel',
        name: 'StationPersonnel',
        component: () => import('@/views/station/PersonnelManagement.vue'),
        meta: {
          title: '人员管理',
          icon: 'User',
          roles: ['station']
        }
      },
      {
        path: 'station/faults',
        name: 'StationFaultList',
        component: () => import('@/views/station/FaultList.vue'),
        meta: {
          title: '故障清单',
          icon: 'Warning',
          roles: ['station']
        }
      },
      {
        path: 'station/event/:id',
        name: 'StationEventDetail',
        component: () => import('@/views/station/EventDetail.vue'),
        meta: {
          title: '事件详情',
          hidden: true,
          roles: ['station']
        }
      },
      {
        path: 'field/report',
        name: 'FieldReport',
        component: () => import('@/views/field/IncidentReport.vue'),
        meta: {
          title: '故障上报',
          icon: 'Warning',
          roles: ['field']
        }
      },
      {
        path: 'field/tasks',
        name: 'FieldTasks',
        component: () => import('@/views/field/MyTasks.vue'),
        meta: {
          title: '我的待办',
          icon: 'List',
          roles: ['field']
        }
      },
      {
        path: 'field/profile',
        name: 'FieldProfile',
        component: () => import('@/views/field/PersonalCenter.vue'),
        meta: {
          title: '个人中心',
          icon: 'User',
          roles: ['field']
        }
      },
      {
        path: 'field/detail/:id',
        name: 'FieldTaskDetail',
        component: () => import('@/views/field/TaskDetail.vue'),
        meta: {
          title: '任务详情',
          hidden: true,
          roles: ['field']
        }
      },
      {
        path: 'field/history',
        name: 'FieldHistory',
        component: () => import('@/views/field/TaskHistory.vue'),
        meta: {
          title: '历史记录',
          icon: 'Clock',
          roles: ['field']
        }
      },
      {
        // 后勤安保 - 险情上报，复用一线执行人员的险情上报页面（IncidentReport.vue）
        // 后勤安保人员在发现险情时，可上报故障设备并同步更新设备运行状态
        path: 'support/report',
        name: 'SupportReport',
        component: () => import('@/views/field/IncidentReport.vue'),
        meta: {
          title: '险情上报',
          icon: 'Warning',
          roles: ['support']
        }
      },
      {
        path: 'support/todos',
        name: 'SupportTodos',
        component: () => import('@/views/field/MyTasks.vue'),
        meta: {
          title: '我的待办',
          icon: 'List',
          roles: ['support']
        }
      },
      {
        path: 'support/detail/:id',
        name: 'SupportTaskDetail',
        component: () => import('@/views/field/TaskDetail.vue'),
        meta: {
          title: '任务详情',
          hidden: true,
          roles: ['support']
        }
      },
      {
        path: 'support/history',
        name: 'SupportHistory',
        component: () => import('@/views/field/TaskHistory.vue'),
        meta: {
          title: '历史记录',
          icon: 'Clock',
          roles: ['support']
        }
      },
      {
        path: 'support/profile',
        name: 'SupportProfile',
        component: () => import('@/views/field/PersonalCenter.vue'),
        meta: {
          title: '个人中心',
          icon: 'User',
          roles: ['support']
        }
      },
      // ==================== 调度指挥中心 ====================
      {
        path: 'dispatch/overview',
        name: 'DispatchOverview',
        component: () => import('@/views/dispatch/Overview.vue'),
        meta: { title: '总览大屏', icon: 'DataAnalysis', roles: ['admin', 'dispatch_center'] }
      },
      {
        path: 'dispatch/event',
        name: 'DispatchEventCenter',
        component: () => import('@/views/dispatch/EventManagement.vue'),
        meta: { title: '事件管理', icon: 'Tickets', roles: ['dispatch_center'] }
      },
      {
        path: 'dispatch/progress',
        name: 'DispatchProgressCenter',
        component: () => import('@/views/dispatch/DispatchProgress.vue'),
        meta: { title: '全线处置进度', icon: 'DataLine', roles: ['admin', 'dispatch_center'] }
      },
      {
        path: 'dispatch/command',
        name: 'DispatchCommandCenter',
        component: () => import('@/views/dispatch/CommandDispatch.vue'),
        meta: { title: '指令下发', icon: 'Promotion', roles: ['dispatch_center'] }
      },
      {
        path: 'dispatch/plan',
        name: 'DispatchPlanCenter',
        component: () => import('@/views/dispatch/PlanManagement.vue'),
        meta: { title: '预案管理', icon: 'Document', roles: ['dispatch_center'] }
      },
      {
        path: 'dispatch/material',
        name: 'DispatchMaterialCenter',
        component: () => import('@/views/dispatch/DispatchMaterial.vue'),
        meta: { title: '全线物资总览', icon: 'Box', roles: ['dispatch_center'] }
      },
      {
        path: 'dispatch/archive',
        name: 'DispatchArchiveCenter',
        component: () => import('@/views/dispatch/DispatchArchive.vue'),
        meta: { title: '事件归档', icon: 'Clock', roles: ['dispatch_center'] }
      },
      // ==================== 车站管理员 ====================
      {
        path: 'station/event',
        name: 'StationAdminEvent',
        component: () => import('@/views/station/StationEventManage.vue'),
        meta: { title: '事件管理', icon: 'Tickets', roles: ['station_admin'] }
      },
      {
        path: 'station/taskAssign',
        name: 'StationAdminTaskAssign',
        component: () => import('@/views/station/TaskAssign.vue'),
        meta: { title: '任务分配', icon: 'Position', roles: ['station_admin'] }
      },
      {
        path: 'station/securityWatch',
        name: 'StationAdminSecurityWatch',
        component: () => import('@/views/station/StationSecurityWatch.vue'),
        meta: { title: '安保值守', icon: 'Lock', roles: ['station_admin'] }
      },
      {
        path: 'station/staffAudit',
        name: 'StationAdminStaffAudit',
        component: () => import('@/views/station/StaffAudit.vue'),
        meta: { title: '人员状态审核', icon: 'User', roles: ['station_admin'] }
      },
      {
        path: 'station/material',
        name: 'StationAdminMaterial',
        component: () => import('@/views/station/StationMaterial.vue'),
        meta: { title: '本站物资管理', icon: 'Box', roles: ['station_admin'] }
      },
      {
        path: 'station/archive',
        name: 'StationAdminArchive',
        component: () => import('@/views/station/StationArchive.vue'),
        meta: { title: '事件归档', icon: 'Clock', roles: ['station_admin'] }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404', noAuth: true }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

// 会话有效期见文件顶部 SESSION_TIMEOUT 定义：
// 登录后超过该时长未再登录需重新登录；短时间重开/页面内正常跳转不会被强制返回登录页。
router.beforeEach((to, from, next) => {
  document.title = to.meta.title
    ? `${to.meta.title} - 城市轨道交通应急管理系统`
    : '城市轨道交通数字化应急管理系统'

  if (to.meta.noAuth) {
    next()
    return
  }

  const token = getToken()
  if (!token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // 超过会话有效期（长时间未登录）：清除本地登录信息，强制回到登录界面，
  // 避免凭残留 token 直接进入工作界面
  const loginAt = getLoginAt()
  if (!loginAt || Date.now() - loginAt > SESSION_TIMEOUT) {
    clearAuth()
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  const userRole = getUser()?.role
  const requiredRoles = to.meta.roles

  if (requiredRoles && Array.isArray(requiredRoles) && userRole) {
    if (!requiredRoles.includes(userRole)) {
      next({ name: 'Dashboard' })
      return
    }
  }

  next()
})

export default router
