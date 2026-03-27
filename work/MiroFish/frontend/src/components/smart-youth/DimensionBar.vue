<template>
  <article class="dimension-row">
    <div class="dimension-copy">
      <div class="dimension-title">{{ item?.emoji || '•' }} {{ item?.label || '维度' }}</div>
      <div class="dimension-line">
        <span v-if="item?.locked" class="badge badge-dim">{{ item.lockLabel || '关卡6解锁' }}</span>
        <span v-else class="mono">
          {{ item?.baselineScore ?? 0 }} → {{ item?.latestScore ?? 0 }}
          <span :class="deltaClass">{{ deltaLabel }}</span>
        </span>
      </div>
    </div>

    <div class="dimension-bar" aria-hidden="true">
      <span
        v-for="block in blocks"
        :key="block"
        class="bar-cell"
        :class="{ filled: block <= (item?.latestScore || 0), baseline: block <= (item?.baselineScore || 0) }"
      ></span>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: {
    type: Object,
    default: null
  }
})

const blocks = computed(() => Array.from({ length: 5 }, (_, index) => index + 1))

const deltaLabel = computed(() => {
  const diff = Number(props.item?.diff || 0)
  if (diff > 0) {
    return `↑ +${diff}`
  }
  if (diff < 0) {
    return `↓ ${diff}`
  }
  return '→ 0'
})

const deltaClass = computed(() => {
  const diff = Number(props.item?.diff || 0)
  if (diff > 0) return 'delta-up'
  if (diff < 0) return 'delta-down'
  return 'delta-flat'
})
</script>

<style scoped>
.dimension-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.3fr) minmax(220px, 1fr);
  gap: 14px;
  align-items: center;
  padding: 14px 0;
  border-top: 1px solid var(--rule-light);
}

.dimension-title {
  font-size: 16px;
  font-weight: 700;
}

.dimension-line {
  margin-top: 8px;
  color: var(--dim);
}

.dimension-bar {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}

.bar-cell {
  height: 12px;
  border: 1px solid var(--rule-light);
  background: var(--abyss-light);
}

.bar-cell.filled {
  background: var(--gold);
  border-color: var(--gold);
}

.bar-cell.baseline {
  opacity: 0.72;
}

.delta-up {
  color: var(--gold);
}

.delta-down {
  color: var(--spark);
}

.delta-flat {
  color: var(--dim);
}

@media (max-width: 760px) {
  .dimension-row {
    grid-template-columns: 1fr;
  }
}
</style>

