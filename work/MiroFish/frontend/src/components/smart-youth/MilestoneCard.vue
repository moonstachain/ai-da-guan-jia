<template>
  <article class="milestone-card card" :style="{ borderLeft: `3px solid ${tone.border}` }">
    <div class="milestone-top">
      <span class="badge" :class="tone.badgeClass">
        {{ tone.emoji }} {{ milestone?.高光层级 || '未标注' }}
      </span>
      <span class="badge badge-dim">{{ milestone?.里程碑类型 || '里程碑' }}</span>
    </div>

    <h3>{{ milestone?.标题 || '未命名里程碑' }}</h3>
    <p class="milestone-quote serif">{{ milestone?.可引用金句 || '' }}</p>
    <p class="milestone-meta mono">
      {{ dateLabel }} · {{ milestone?.关联Phase || '未标注' }} · {{ milestone?.外部认可来源 || '内部节点' }}
    </p>
    <p v-if="milestone?.详细记录" class="milestone-detail">{{ milestone.详细记录 }}</p>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { formatSmartYouthDate, getHighlightTone } from '../../data/smartYouthTheme'

const props = defineProps({
  milestone: {
    type: Object,
    default: null
  }
})

const tone = computed(() => getHighlightTone(props.milestone?.高光层级))
const dateLabel = computed(() => formatSmartYouthDate(props.milestone?.里程碑日期, { mode: 'short' }))
</script>

<style scoped>
.milestone-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.milestone-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

h3 {
  margin: 0;
  font-size: 24px;
  line-height: 1.25;
}

.milestone-quote {
  font-size: 18px;
  line-height: 1.7;
}

.milestone-meta {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.12em;
}

.milestone-detail {
  color: rgba(245, 240, 232, 0.78);
  line-height: 1.6;
}
</style>
