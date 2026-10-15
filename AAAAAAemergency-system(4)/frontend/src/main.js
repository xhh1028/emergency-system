import { createApp } from 'vue'
import App from './App.vue'
import pinia from './store'
import router from './router'

import 'element-plus/theme-chalk/dark/css-vars.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-notification.css'
import 'element-plus/theme-chalk/el-loading.css'
import './styles/global.css'

const app = createApp(App)

app.use(pinia)
app.use(router)

app.mount('#app')
