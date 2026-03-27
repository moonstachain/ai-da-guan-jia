import { computed, ref } from 'vue'
import { loadSmartYouthCapability } from './useSmartYouthQuery'
import {
  enrichSmartYouthStudentProfile,
  extractGateIndex
} from '../data/smartYouthTheme'

const studentRosterQuery = {
  filter: { field: '状态', operator: 'equals', value: '在训' },
  sort: [{ field: '入营日期', order: 'asc' }]
}

export function useStudentRoster() {
  const roster = ref([])
  const loading = ref(true)
  const source = ref('fallback')
  const error = ref(null)

  const refresh = async () => {
    loading.value = true
    const result = await loadSmartYouthCapability('smart_youth_student_profile', studentRosterQuery)
    roster.value = result.records
      .map(enrichSmartYouthStudentProfile)
      .sort((left, right) => {
        const leftRank = left.highlightTone?.key === 'spark' ? 0 : left.highlightTone?.key === 'gold' ? 1 : left.highlightTone?.key === 'teal' ? 2 : 3
        const rightRank = right.highlightTone?.key === 'spark' ? 0 : right.highlightTone?.key === 'gold' ? 1 : right.highlightTone?.key === 'teal' ? 2 : 3
        if (leftRank !== rightRank) {
          return leftRank - rightRank
        }
        const leftGate = Number(left?.gateIndex || extractGateIndex(left?.当前关卡) || 0)
        const rightGate = Number(right?.gateIndex || extractGateIndex(right?.当前关卡) || 0)
        if (leftGate !== rightGate) {
          return rightGate - leftGate
        }
        return String(left?.姓名 || '').localeCompare(String(right?.姓名 || ''), 'zh-Hans-CN')
      })
    source.value = result.source
    error.value = result.error
    loading.value = false
    return result
  }

  void refresh()

  const activeStudentIds = computed(() => roster.value.map(item => item.孩子ID))

  return {
    roster,
    activeStudentIds,
    loading,
    source,
    error,
    refresh
  }
}
