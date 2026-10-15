<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/store/modules/app'
import Sidebar from './Sidebar.vue'
import HeaderBar from './HeaderBar.vue'

const route = useRoute()
const appStore = useAppStore()

watch(
  () => route.meta.title,
  (title) => {
    appStore.setRouteTitle(title || '')
  },
  { immediate: true }
)
</script>

<template>
  <div class="app-layout">
    <aside class="layout-sidebar">
      <Sidebar />
    </aside>
    <div class="layout-main">
      <HeaderBar />
      <main class="layout-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.layout-sidebar {
  width: 180px;
  flex-shrink: 0;
  overflow: hidden;
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
  padding: 0;
  background-color: #0d1421;
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
