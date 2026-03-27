import { computed, ref, watch } from 'vue'
import { loadSmartYouthCapability } from './useSmartYouthQuery'
import {
  formatSmartYouthDate,
  formatSmartYouthMonthLabel,
  isSmartYouthAssetAuthorized,
  toSmartYouthDate
} from '../data/smartYouthTheme'

const assetQuery = {
  sort: [{ field: '授权有效期', order: 'desc' }]
}

function enrichAsset(asset) {
  if (!asset) {
    return null
  }
  const authorized = isSmartYouthAssetAuthorized(asset)
  const expiryDate = toSmartYouthDate(asset?.授权有效期)
  const expired = Boolean(expiryDate && expiryDate.getTime() < Date.now())
  const scenarioList = Array.isArray(asset?.可用场景) ? asset.可用场景.filter(Boolean) : []
  return {
    ...asset,
    authorized,
    authorizationTone: authorized ? 'gold' : 'dim',
    authorizationLabel: expired ? '已过期' : (authorized ? '已授权' : (asset?.授权状态 || '待授权')),
    expired,
    expiryLabel: expiryDate ? formatSmartYouthDate(expiryDate, { mode: 'short' }) : '',
    monthLabel: formatSmartYouthMonthLabel(asset?.授权有效期),
    scenarioList,
    scenarioLabel: scenarioList.join(' · '),
    quoteText: asset?.可引用金句 || '',
    sourceLabel: asset?.资产名称 || asset?.资产ID || ''
  }
}

export function useAssets(studentIdRef) {
  const assets = ref([])
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
      assets.value = []
      loading.value = false
      return null
    }
    loading.value = true
    const result = await loadSmartYouthCapability('smart_youth_assets', {
      filter: { field: '孩子ID', operator: 'equals', value: studentId },
      sort: assetQuery.sort
    })
    assets.value = result.records.map(enrichAsset).filter(Boolean)
    source.value = result.source
    error.value = result.error
    loading.value = false
    return result
  }

  watch(resolvedStudentId, () => {
    void refresh()
  }, { immediate: true })

  const authorizedAssets = computed(() => assets.value.filter(asset => asset.authorized))
  const quoteAssets = computed(() => assets.value.filter(asset => asset.quoteText))
  const visibleAssets = computed(() => assets.value.slice())

  return {
    assets,
    authorizedAssets,
    quoteAssets,
    visibleAssets,
    loading,
    source,
    error,
    refresh
  }
}
