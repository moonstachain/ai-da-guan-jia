<template>
  <article class="action-item card" :style="{ borderLeft: `3px solid ${tone}` }">
    <div class="action-top">
      <span class="badge" :class="badgeClass">{{ action?.urgencyLabel || '待办' }}</span>
      <span class="mono action-date">{{ action?.dateLabel || '' }}</span>
    </div>

    <h3>{{ action?.title || '未命名待办' }}</h3>
    <p class="action-description">{{ action?.description || '' }}</p>
    <p v-if="action?.note" class="action-note serif">{{ action.note }}</p>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  action: {
    type: Object,
    default: null
  }
})

const toneMap = {
  spark: 'var(--spark)',
  gold: 'var(--gold)',
  teal: 'var(--teal)',
  dim: 'var(--rule-light)'
}

const badgeClassMap = {
  spark: 'badge-spark',
  gold: 'badge-gold',
  teal: 'badge-teal',
  dim: 'badge-dim'
}

const tone = computed(() => toneMap[props.action?.tone || 'dim'])
const badgeClass = computed(() => badgeClassMap[props.action?.tone || 'dim'])
</script>

<style scoped>
.action-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

h3 {
  margin: 0;
  font-size: 18px;
}

.action-description {
  color: rgba(245, 240, 232, 0.8);
  line-height: 1.7;
}

.action-note {
  color: var(--paper);
  font-size: 18px;
  line-height: 1.6;
}

.action-date {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.12em;
}
</style>
