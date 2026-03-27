<template>
  <article class="student-card card" :class="studentToneClass">
    <div class="student-topline">
      <span class="badge" :class="student?.highlightTone?.badgeClass || 'badge-dim'">
        {{ student?.highlightTone?.emoji || '◦' }} {{ student?.最高高光层级 || '未标注' }}
      </span>
      <span class="mono student-status">{{ student?.状态 || '在训' }}</span>
    </div>

    <h3 class="student-name">{{ student?.姓名 || '未命名' }}</h3>
    <p class="student-meta">
      {{ student?.当前年龄 || '—' }}岁 · {{ student?.gateLabel || '关卡' }} {{ student?.gateName || '' }}
      <span v-if="student?.trainingMonths">· 在训{{ student.trainingMonths }}</span>
    </p>
    <p class="student-line">
      {{ student?.personaLine || '尚未形成清晰画像' }}
    </p>

    <div class="student-signal-row">
      <span class="badge badge-dim">关卡代号 {{ student?.gateCodeLabel || student?.gateCode || '未标注' }}</span>
      <span class="badge badge-dim">{{ student?.baseRatingSummary || 'D1/D3/D6 未录入' }}</span>
    </div>

    <div class="student-auth-row">
      <span class="badge" :class="student?.portraitAuthorized ? 'badge-gold' : 'badge-dim'">
        {{ student?.portraitAuthorization || '未授权' }}
      </span>
      <span class="student-achievements">{{ student?.achievementSummary || '暂无已解锁成就' }}</span>
    </div>

    <div class="student-footer">
      <div class="student-project">{{ student?.代表作品 || '等待作品' }}</div>
      <button class="student-open" type="button" @click="$emit('open', student?.孩子ID)">
        进入 →
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  student: {
    type: Object,
    default: null
  }
})

defineEmits(['open'])

const studentToneClass = computed(() => props.student?.highlightTone?.key || 'dim')
</script>

<style scoped>
.student-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 228px;
  border-top: 3px solid var(--rule-light);
}

.student-card.spark {
  border-top-color: var(--spark);
}

.student-card.gold {
  border-top-color: var(--gold);
}

.student-card.teal {
  border-top-color: var(--teal);
}

.student-card.dim {
  border-top-color: var(--rule-light);
}

.student-topline,
.student-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.student-name {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.student-meta {
  color: var(--dim);
  font-size: 13px;
}

.student-line {
  color: rgba(245, 240, 232, 0.9);
  font-size: 14px;
  line-height: 1.7;
}

.student-signal-row,
.student-auth-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.student-auth-row {
  align-items: center;
  justify-content: space-between;
}

.student-achievements {
  color: var(--dim);
  font-size: 12px;
  line-height: 1.6;
}

.student-project {
  color: var(--paper);
  font-weight: 700;
}

.student-status {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.12em;
}

.student-open {
  border: 1px solid var(--rule-light);
  background: transparent;
  color: var(--paper);
  padding: 8px 12px;
  font: inherit;
  font-family: 'Space Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.student-open:hover {
  border-color: var(--gold);
  color: var(--gold);
}

@media (max-width: 720px) {
  .student-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
