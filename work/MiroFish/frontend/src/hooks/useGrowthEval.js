import { computed, ref, watch } from 'vue'
import { loadSmartYouthCapability } from './useSmartYouthQuery'
import {
  selectBaselineRecord,
  selectLatestRecord,
  smartYouthDimensionCatalog,
  toSmartYouthDate
} from '../data/smartYouthTheme'

const growthQuery = {
  sort: [{ field: '评估日期', order: 'asc' }]
}

function toScore(value) {
  if (value == null || value === '') {
    return 0
  }
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function buildDimensionEntries(baseline, latest) {
  return smartYouthDimensionCatalog.map(dimension => {
    const baselineScore = toScore(baseline?.[dimension.field])
    const latestScore = toScore(latest?.[dimension.field])
    const locked = dimension.key === 'D4仿真试错' && baselineScore === 0 && latestScore === 0
    return {
      ...dimension,
      baselineScore,
      latestScore,
      diff: latestScore - baselineScore,
      locked
    }
  })
}

function buildRadarSeries(evaluations) {
  const baseline = selectBaselineRecord(evaluations, '评估日期')
  const latest = selectLatestRecord(evaluations, '评估日期')
  const baselineValues = smartYouthDimensionCatalog.map(item => toScore(baseline?.[item.field]))
  const latestValues = smartYouthDimensionCatalog.map(item => toScore(latest?.[item.field]))
  return {
    baseline,
    latest,
    baselineValues,
    latestValues,
    dimensionEntries: buildDimensionEntries(baseline, latest)
  }
}

export function useGrowthEval(studentIdRef) {
  const evaluations = ref([])
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
      evaluations.value = []
      loading.value = false
      return null
    }
    loading.value = true
    const result = await loadSmartYouthCapability('smart_youth_growth_eval', {
      filter: { field: '孩子ID', operator: 'equals', value: studentId },
      sort: growthQuery.sort
    })
    evaluations.value = result.records
    source.value = result.source
    error.value = result.error
    loading.value = false
    return result
  }

  watch(resolvedStudentId, () => {
    void refresh()
  }, { immediate: true })

  const derived = computed(() => buildRadarSeries(evaluations.value))

  return {
    evaluations,
    loading,
    source,
    error,
    refresh,
    baseline: computed(() => derived.value.baseline),
    latest: computed(() => derived.value.latest),
    baselineValues: computed(() => derived.value.baselineValues),
    latestValues: computed(() => derived.value.latestValues),
    dimensionEntries: computed(() => derived.value.dimensionEntries),
    latestJudgment: computed(() => derived.value.latest?.总教头判断 || ''),
    latestDate: computed(() => derived.value.latest?.评估日期 || ''),
    latestScore: computed(() => derived.value.latest?.总分 || 0)
  }
}

