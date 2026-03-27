import { computed, ref, watch } from 'vue'
import { loadSmartYouthCapability } from './useSmartYouthQuery'
import { selectUpcomingMilestones, toSmartYouthDate } from '../data/smartYouthTheme'

const milestoneQuery = {
  sort: [{ field: '里程碑日期', order: 'desc' }]
}

function toIsoDate(value) {
  const date = toSmartYouthDate(value)
  return date ? date.toISOString() : ''
}

export function useMilestones(studentIdRef) {
  const milestones = ref([])
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
      milestones.value = []
      loading.value = false
      return null
    }
    loading.value = true
    const result = await loadSmartYouthCapability('smart_youth_milestones', {
      filter: { field: '孩子ID', operator: 'equals', value: studentId },
      sort: milestoneQuery.sort
    })
    milestones.value = result.records
    source.value = result.source
    error.value = result.error
    loading.value = false
    return result
  }

  watch(resolvedStudentId, () => {
    void refresh()
  }, { immediate: true })

  const upcoming = computed(() => selectUpcomingMilestones(milestones.value, 14))
  const recent = computed(() => milestones.value.slice(0, 3))
  const nextTwoWeeks = computed(() => selectUpcomingMilestones(milestones.value, 14).slice(0, 3))

  return {
    milestones,
    loading,
    source,
    error,
    refresh,
    upcoming,
    recent,
    nextTwoWeeks,
    toIsoDate
  }
}

