<template>
  <div class="guide-page">
    <section class="card heavy-top-spark">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">配合建议</p>
          <h1>{{ profile?.姓名 || '未命名学员' }} 的家长指南</h1>
        </div>
        <span class="mono section-meta">{{ personaLabel }}</span>
      </div>
      <p class="guide-lede">
        {{ profile?.家长画像 ? guidanceCopy : '先以通用陪跑建议为主：稳定在场，不代替孩子做。' }}
      </p>
    </section>

    <section class="card heavy-top-gold">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">本周待办</p>
          <h2>让家长知道下一步该做什么</h2>
        </div>
      </div>

      <div v-if="actionItems.length" class="action-stack">
        <ActionItem
          v-for="action in actionItems"
          :key="`${action.title}-${action.dateLabel}`"
          :action="action"
        />
      </div>
      <p v-else class="empty-copy">暂无近期里程碑，建议继续鼓励孩子讲项目。</p>
    </section>

    <section v-if="comparisonCards.length" class="card heavy-top-teal comparison-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">同组学员 · 横向参考</p>
          <h2>看看孩子在同组里的位置</h2>
        </div>
        <span class="mono section-meta">{{ comparisonScopeLabel }}</span>
      </div>

      <p class="comparison-lede">
        {{ comparisonScopeHint }}
      </p>

      <div class="comparison-grid">
        <article
          v-for="card in comparisonCards"
          :key="card.id"
          class="comparison-card"
          :class="{ self: card.isSelf }"
        >
          <div class="comparison-top">
            <span class="badge" :class="card.badgeClass">{{ card.roleLabel }}</span>
            <span class="mono comparison-age">{{ card.ageLabel }}</span>
          </div>

          <h3>{{ card.name }}</h3>
          <p class="comparison-gate">{{ card.gateLabel }}</p>

          <div class="comparison-metrics">
            <span class="badge badge-dim">{{ card.baseRatingSummary }}</span>
            <span class="badge badge-dim">{{ card.authorizationLabel }}</span>
          </div>

          <p class="comparison-drive">{{ card.driveLabel }}</p>
          <p class="comparison-persona serif">{{ card.personaLine }}</p>
          <p class="comparison-achievement">{{ card.achievementSummary }}</p>
        </article>
      </div>
    </section>

    <section class="card heavy-top-teal">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">关键洞察</p>
          <h2>来自总教头的最新判断</h2>
        </div>
      </div>

      <article class="insight-card">
        <p class="serif insight-text">
          {{ judgmentLead }}
          <span v-if="judgmentBreakthrough" class="gold">{{ judgmentBreakthrough }}</span>
        </p>
      </article>
    </section>

    <section class="card heavy-top-gold">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">性格特点与配合方式</p>
          <h2>从家长画像出发</h2>
        </div>
      </div>

      <div class="persona-grid">
        <article class="persona-card">
          <div class="persona-title mono">家长画像</div>
          <div class="persona-copy">{{ personaLabel }}</div>
        </article>
        <article class="persona-card">
          <div class="persona-title mono">建议</div>
          <div class="persona-copy">{{ guidanceCopy }}</div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ActionItem from '../../components/smart-youth/ActionItem.vue'
import {
  buildSmartYouthComparisonGroup,
  formatSmartYouthDate,
  getHighlightTone,
  getParentGuidance
} from '../../data/smartYouthTheme'
import { useSmartYouthContext } from '../../hooks/useSmartYouthContext'
import { useMilestones } from '../../hooks/useMilestones'
import { useGrowthEval } from '../../hooks/useGrowthEval'
import { useStudentProfile } from '../../hooks/useStudentProfile'

const route = useRoute()
const studentId = computed(() => String(route.params.studentId || ''))

const { students } = useSmartYouthContext()
const { profile } = useStudentProfile(studentId)
const { nextTwoWeeks } = useMilestones(studentId)
const { latestJudgment } = useGrowthEval(studentId)
const comparisonGroup = computed(() => buildSmartYouthComparisonGroup(students.value, profile.value))

const personaLabel = computed(() => profile.value?.家长画像 || '未标注')
const guidanceCopy = computed(() => getParentGuidance(profile.value?.家长画像))
const comparisonScopeLabel = computed(() => comparisonGroup.value.scopeLabel || '暂无对比')
const comparisonScopeHint = computed(() => comparisonGroup.value.scopeHint || '先选择一个孩子')
const comparisonCards = computed(() => comparisonGroup.value.items.map(student => ({
  id: student.孩子ID,
  name: student.姓名 || '未命名',
  ageLabel: student.当前年龄 ? `${student.当前年龄}岁` : '—',
  gateLabel: `${student.gateLabel || '关卡'} ${student.gateName || ''}`.trim(),
  baseRatingSummary: student.baseRatingSummary || 'D1/D3/D6 未录入',
  authorizationLabel: student.portraitAuthorization || '未授权',
  driveLabel: student.内在驱动方向 || '未标注驱动力',
  personaLine: student.personaLine || '尚未形成稳定画像',
  achievementSummary: student.achievementSummary || '暂无已解锁成就',
  roleLabel: student.孩子ID === profile.value?.孩子ID ? '当前孩子' : '同组参考',
  badgeClass: student.highlightTone?.badgeClass || 'badge-dim',
  isSelf: student.孩子ID === profile.value?.孩子ID
})))

const judgmentLead = computed(() => {
  const text = latestJudgment.value || ''
  const marker = '下一个突破口是'
  if (!text.includes(marker)) {
    return text
  }
  return text.split(marker)[0]
})

const judgmentBreakthrough = computed(() => {
  const text = latestJudgment.value || ''
  const marker = '下一个突破口是'
  if (!text.includes(marker)) {
    return ''
  }
  return text.split(marker)[1] || ''
})

const actionItems = computed(() => {
  if (!nextTwoWeeks.value.length) {
    return [
      {
        title: '鼓励他向您讲项目',
        description: '您听不懂的地方，正是他需要讲得更清楚的地方。',
        note: '家长只需要先听懂，再问一个问题。',
        tone: 'teal',
        urgencyLabel: '固定建议',
        dateLabel: '本周'
      }
    ]
  }
  return nextTwoWeeks.value.map(milestone => ({
    title: milestone.标题 || milestone.里程碑类型 || '未命名节点',
    description: milestone.详细记录 || milestone.可引用金句 || '',
    note: milestone.下一轮发射台 || '',
    tone: getHighlightTone(milestone.高光层级).key,
    urgencyLabel: milestone.高光层级 || '待办',
    dateLabel: formatSmartYouthDate(milestone.里程碑日期, { mode: 'short' })
  }))
})
</script>

<style scoped>
.guide-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.guide-lede {
  color: rgba(245, 240, 232, 0.86);
  line-height: 1.8;
}

.comparison-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.comparison-lede {
  color: rgba(245, 240, 232, 0.82);
  line-height: 1.7;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.comparison-card {
  padding: 18px 20px;
  background: var(--abyss-light);
  border: 1px solid var(--rule-light);
  border-top: 3px solid var(--rule-light);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comparison-card.self {
  border-top-color: var(--gold);
}

.comparison-top,
.comparison-metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.comparison-age {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.12em;
}

.comparison-card h3 {
  margin: 0;
  font-size: 24px;
  line-height: 1.25;
}

.comparison-gate {
  color: var(--paper);
  line-height: 1.6;
}

.comparison-drive,
.comparison-achievement {
  color: rgba(245, 240, 232, 0.76);
  line-height: 1.7;
}

.comparison-persona {
  font-size: 16px;
  line-height: 1.7;
}

.action-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.insight-text {
  font-size: clamp(22px, 2.8vw, 32px);
  line-height: 1.65;
}

.gold {
  color: var(--gold);
}

.persona-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.persona-card {
  padding: 18px 20px;
  background: var(--abyss-light);
  border: 1px solid var(--rule-light);
}

.persona-title {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.14em;
  margin-bottom: 10px;
}

.persona-copy {
  line-height: 1.8;
}

@media (max-width: 760px) {
  .persona-grid {
    grid-template-columns: 1fr;
  }

  .comparison-grid {
    grid-template-columns: 1fr;
  }
}
</style>
