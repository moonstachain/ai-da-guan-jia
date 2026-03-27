import { computed, ref, watch } from 'vue'
import { loadSmartYouthCapability } from './useSmartYouthQuery'
import { selectFeaturedProject, smartYouthProjectStatusRank, toSmartYouthDate } from '../data/smartYouthTheme'

const projectQuery = {
  sort: [{ field: '最新更新', order: 'desc' }]
}

function enrichProject(project) {
  if (!project) {
    return null
  }
  const statusRank = smartYouthProjectStatusRank[project.状态] ?? 99
  return {
    ...project,
    statusRank,
    statusTone: statusRank <= 1 ? 'gold' : statusRank === 2 ? 'teal' : 'dim',
    startDateLabel: project.起始日期 ? toSmartYouthDate(project.起始日期)?.toISOString() : '',
    latestUpdateLabel: project.最新更新 ? toSmartYouthDate(project.最新更新)?.toISOString() : ''
  }
}

export function useProjects(studentIdRef) {
  const projects = ref([])
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
      projects.value = []
      loading.value = false
      return null
    }
    loading.value = true
    const result = await loadSmartYouthCapability('smart_youth_projects', {
      filter: { field: '孩子ID', operator: 'equals', value: studentId },
      sort: projectQuery.sort
    })
    projects.value = result.records.map(enrichProject)
    source.value = result.source
    error.value = result.error
    loading.value = false
    return result
  }

  watch(resolvedStudentId, () => {
    void refresh()
  }, { immediate: true })

  const featured = computed(() => selectFeaturedProject(projects.value))
  const sortedProjects = computed(() => [...projects.value].sort((left, right) => (left?.statusRank ?? 99) - (right?.statusRank ?? 99)))

  return {
    projects,
    loading,
    source,
    error,
    refresh,
    featured,
    sortedProjects
  }
}

