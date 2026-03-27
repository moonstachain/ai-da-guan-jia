<template>
  <div class="smart-youth-shell page-shell">
    <div class="page-content smart-youth-layout">
      <SmartYouthNavBar
        :students="students"
        :active-student-id="activeStudentId"
        :active-tab-name="activeTabName"
        :source="source"
        :loading="loading"
        @change-student="goToStudent"
      />

      <main class="smart-youth-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SmartYouthNavBar from '../../components/smart-youth/SmartYouthNavBar.vue'
import { provideSmartYouthContext } from '../../hooks/useSmartYouthContext'
import { useStudentRoster } from '../../hooks/useStudentRoster'

const route = useRoute()
const router = useRouter()
const { roster, loading, source, refresh } = useStudentRoster()

const activeStudentId = computed(() => String(route.params.studentId || ''))
const activeStudent = computed(() => roster.value.find(item => item.孩子ID === activeStudentId.value) || null)
const activeTabName = computed(() => {
  const routeName = String(route.name || '')
  if (['SmartYouthHeroMap', 'SmartYouthGrowth', 'SmartYouthHighlights', 'SmartYouthParentGuide'].includes(routeName)) {
    return routeName
  }
  return 'SmartYouthSelector'
})

const goToStudent = (studentId) => {
  if (!studentId) {
    return
  }
  const nextTabName = activeTabName.value === 'SmartYouthSelector' ? 'SmartYouthHeroMap' : activeTabName.value
  router.push({ name: nextTabName, params: { studentId } })
}

provideSmartYouthContext({
  students: roster,
  loading,
  source,
  activeStudentId,
  activeStudent,
  activeTabName,
  switchStudent: goToStudent,
  refreshRoster: refresh
})
</script>

<style scoped>
.smart-youth-shell {
  min-height: 100vh;
}

.smart-youth-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-block: 24px 28px;
}

.smart-youth-main {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
</style>

