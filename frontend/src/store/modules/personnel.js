import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getStationPersonnelOptions } from '@/api/station'

export const usePersonnelStore = defineStore('personnel', () => {
  const personnelList = ref([])
  const statusApplications = ref([])

  async function loadPersonnel() {
    try {
      // 人员台账统一从真实后端拉取（本站一线执行与后勤安保人员）
      const res = await getStationPersonnelOptions()
      personnelList.value = (res.data || []).map((person) => ({
        ...person,
        // 兼容旧页面字段：name/position/status
        username: person.phone || '',
        name: person.name || '',
        position: person.postName || '',
        status: person.status || 'OFF_DUTY',
        personnelType: person.role === 'support' ? 'support' : 'field'
      }))
    } catch {
      personnelList.value = []
    }
  }

  function findPersonByUsername(username) {
    return personnelList.value.find((person) => person.username === username)
  }

  function addPerson(person) {
    personnelList.value.unshift({ ...person })
  }

  function updatePerson(person) {
    const index = personnelList.value.findIndex((item) => item.id === person.id)
    if (index !== -1) {
      personnelList.value[index] = { ...person }
    }
  }

  function setPersonStatus(username, status) {
    const person = findPersonByUsername(username)
    if (person) {
      person.status = status
    } else {
      personnelList.value.unshift({
        id: Date.now(),
        username,
        name: username,
        personnelType: 'field',
        position: '一线执行',
        area: '',
        status,
        phone: '',
        canBeLeader: false
      })
    }
  }

  function addStatusApplication(application) {
    statusApplications.value.unshift({ ...application })
  }

  return {
    personnelList,
    statusApplications,
    loadPersonnel,
    findPersonByUsername,
    addPerson,
    updatePerson,
    setPersonStatus,
    addStatusApplication
  }
})
