import { onMounted, reactive, toRef, watch } from 'vue'
import { requestWithRetry } from '../api/index'
import { searchSmartYouthRecords } from '../api/smartYouth'
import { applySmartYouthQuery } from '../data/smartYouthTheme'
import { smartYouthFallbackCapabilityRecords } from '../data/smartYouthFallback'

export async function loadSmartYouthCapability(capabilityId, query = {}) {
  try {
    const response = await requestWithRetry(() => searchSmartYouthRecords(capabilityId, query), 2, 350)
    const payload = response?.data || response || {}
    const records = Array.isArray(payload.records) ? payload.records : []
    return {
      source: 'feishu',
      payload,
      records,
      error: null
    }
  } catch (error) {
    const fallbackRecords = smartYouthFallbackCapabilityRecords[capabilityId] || []
    const records = applySmartYouthQuery(fallbackRecords, query)
    return {
      source: 'fallback',
      payload: {
        source: 'fallback',
        capability_id: capabilityId,
        query,
        records,
        record_count: records.length
      },
      records,
      error
    }
  }
}

export function createSmartYouthState() {
  return reactive({
    loading: true,
    source: 'fallback',
    error: null
  })
}

export function bindSmartYouthRefresh(loader, state, target) {
  const run = async () => {
    state.loading = true
    const result = await loader()
    target.value = result
    state.source = result.source
    state.error = result.error
    state.loading = false
    return result
  }
  onMounted(run)
  return run
}

export function watchSmartYouthQuery(sourceRef, loader, state, target) {
  const run = async () => {
    state.loading = true
    const result = await loader()
    target.value = result
    state.source = result.source
    state.error = result.error
    state.loading = false
    return result
  }
  watch(sourceRef, run, { immediate: true })
  return run
}

