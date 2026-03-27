import { inject, provide } from 'vue'

export const SMART_YOUTH_CONTEXT_KEY = Symbol('smartYouthContext')

export function provideSmartYouthContext(context) {
  provide(SMART_YOUTH_CONTEXT_KEY, context)
}

export function useSmartYouthContext() {
  const context = inject(SMART_YOUTH_CONTEXT_KEY, null)
  if (!context) {
    throw new Error('SmartYouth context not found. Make sure the page is rendered under SmartYouthLayout.')
  }
  return context
}

