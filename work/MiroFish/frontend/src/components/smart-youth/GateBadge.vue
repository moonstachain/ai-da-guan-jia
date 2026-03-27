<template>
  <article class="gate-badge" :class="stateClass">
    <div class="gate-head mono">
      <span class="gate-icon">{{ icon }}</span>
      <span>{{ gate?.gateLabel || '关卡' }}</span>
    </div>
    <div class="gate-name">{{ gate?.name || '未命名' }}</div>
    <div class="gate-phase caption">{{ gate?.phase || '' }}</div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  gate: {
    type: Object,
    default: null
  },
  currentIndex: {
    type: Number,
    default: 0
  }
})

const state = computed(() => {
  if ((props.gate?.index || 0) < props.currentIndex) {
    return 'done'
  }
  if ((props.gate?.index || 0) === props.currentIndex) {
    return 'current'
  }
  return 'locked'
})

const stateClass = computed(() => state.value)
const icon = computed(() => {
  if (state.value === 'done') return '✓'
  if (state.value === 'current') return '★'
  return '🔒'
})
</script>

<style scoped>
.gate-badge {
  min-height: 118px;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--abyss-light);
  border: 1px solid var(--rule-light);
  border-top: 3px solid var(--rule-light);
}

.gate-badge.done {
  border-top-color: var(--teal);
}

.gate-badge.current {
  border-top-color: var(--spark);
}

.gate-badge.locked {
  opacity: 0.72;
}

.gate-head {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.12em;
}

.gate-name {
  font-size: 16px;
  font-weight: 700;
}

.gate-phase {
  color: var(--dim);
}

.current .gate-icon {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: translateY(0);
  }

  50% {
    opacity: 0.6;
    transform: translateY(-1px);
  }
}
</style>

