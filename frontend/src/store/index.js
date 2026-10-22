import { createPinia } from 'pinia'

const pinia = createPinia()

export default pinia

export { useNotificationStore } from './modules/notification'
export { useCommandStore } from './modules/command'
export { useEventStore } from './modules/event'
export { useFaultStore } from './modules/fault'
export { useTaskStore } from './modules/task'
export { usePersonnelStore } from './modules/personnel'