import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const currentRouteTitle = ref('')
  const loading = ref(false)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setSidebarCollapsed(value) {
    sidebarCollapsed.value = value
  }

  function setRouteTitle(title) {
    currentRouteTitle.value = title
  }

  function setLoading(value) {
    loading.value = value
  }

  return {
    sidebarCollapsed,
    currentRouteTitle,
    loading,
    toggleSidebar,
    setSidebarCollapsed,
    setRouteTitle,
    setLoading
  }
})