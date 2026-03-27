<template>
  <div class="highlights-page">
    <section class="card heavy-top-gold">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">高光时刻</p>
          <h1>{{ profile?.姓名 || '未命名学员' }} 的时间线</h1>
        </div>
        <span class="mono section-meta">{{ milestones.length }} 条记录</span>
      </div>
    </section>

    <section v-if="milestones.length" class="timeline">
      <MilestoneCard
        v-for="milestone in milestones"
        :key="milestone.里程碑ID || milestone.标题"
        :milestone="milestone"
      />
    </section>

    <section v-else class="card empty-card">
      暂无里程碑记录。
    </section>

    <section v-if="quoteCards.length" class="card heavy-top-teal quote-wall">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">孩子说了什么</p>
          <h2>来自真实录音的原话</h2>
        </div>
        <span class="mono section-meta">{{ authorizedQuoteCount }} / {{ quoteCards.length }} 已授权</span>
      </div>

      <div class="quote-grid">
        <article
          v-for="card in quoteCards"
          :key="card.milestoneId"
          class="quote-card"
          :class="{ locked: card.locked }"
        >
          <div class="quote-top">
            <span class="badge" :class="card.authClass">{{ card.authLabel }}</span>
            <span class="mono quote-date">{{ card.dateLabel || card.fullDateLabel }}</span>
          </div>

          <h3>{{ card.title }}</h3>
          <p class="quote-copy serif">“{{ card.quote }}”</p>

          <div class="quote-meta">
            <span>{{ card.sourceLabel }}</span>
            <span v-if="card.sceneLabel">{{ card.sceneLabel }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import MilestoneCard from '../../components/smart-youth/MilestoneCard.vue'
import { buildSmartYouthQuoteCards } from '../../data/smartYouthTheme'
import { useAssets } from '../../hooks/useAssets'
import { useMilestones } from '../../hooks/useMilestones'
import { useStudentProfile } from '../../hooks/useStudentProfile'

const route = useRoute()
const studentId = computed(() => String(route.params.studentId || ''))

const { profile } = useStudentProfile(studentId)
const { milestones } = useMilestones(studentId)
const { assets } = useAssets(studentId)

const quoteCards = computed(() => buildSmartYouthQuoteCards(milestones.value, assets.value))
const authorizedQuoteCount = computed(() => quoteCards.value.filter(card => !card.locked).length)
</script>

<style scoped>
.highlights-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-left: 18px;
  border-left: 1px solid var(--rule-light);
}

.quote-wall {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.quote-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.quote-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 20px;
  border: 1px solid var(--rule-light);
  background: rgba(255, 255, 255, 0.02);
}

.quote-card:first-child {
  grid-column: 1 / -1;
}

.quote-card.locked {
  opacity: 0.3;
}

.quote-top,
.quote-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.quote-top {
  flex-wrap: wrap;
}

.quote-date,
.quote-meta {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.quote-card h3 {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

.quote-copy {
  font-size: 18px;
  line-height: 1.7;
}

.quote-meta {
  flex-wrap: wrap;
}

@media (max-width: 860px) {
  .quote-grid {
    grid-template-columns: 1fr;
  }

  .quote-card:first-child {
    grid-column: auto;
  }
}
</style>
