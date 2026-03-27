import { computed, ref, watch } from 'vue'
import { loadSmartYouthCapability } from './useSmartYouthQuery'
import {
  enrichSmartYouthStudentProfile
} from '../data/smartYouthTheme'

export function useStudentProfile(studentIdRef) {
  const profile = ref(null)
  const loading = ref(true)
  const source = ref('fallback')
  const error = ref(null)

  const resolvedStudentId = computed(() => {
    if (typeof studentIdRef === 'string') {
      return studentIdRef
    }
    return studentIdRef?.value ? String(studentIdRef.value) : ''
  })

  const refresh = async () => {
    const studentId = resolvedStudentId.value
    if (!studentId) {
      profile.value = null
      loading.value = false
      return null
    }
    loading.value = true
    const result = await loadSmartYouthCapability('smart_youth_student_profile', {
      filter: { field: '孩子ID', operator: 'equals', value: studentId },
      limit: 1
    })
    profile.value = enrichSmartYouthStudentProfile(result.records[0] || null)
    source.value = result.source
    error.value = result.error
    loading.value = false
    return result
  }

  watch(resolvedStudentId, () => {
    void refresh()
  }, { immediate: true })

  return {
    profile,
    loading,
    source,
    error,
    refresh
  }
}
