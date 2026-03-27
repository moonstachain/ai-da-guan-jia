<template>
  <div class="hero-page">
    <section v-if="profile" class="card heavy-top-spark hero-identity">
      <div class="hero-head">
        <div>
          <p class="eyebrow mono">{{ profile.gateLabel }} · 原力人格</p>
          <h1>{{ profile.姓名 }}，你在第{{ profile.gateIndex || 1 }}关</h1>
        </div>
        <span class="badge" :class="profile.highlightTone?.badgeClass || 'badge-dim'">
          {{ profile.highlightTone?.emoji || '◦' }} {{ profile.最高高光层级 || '未标注' }}
        </span>
      </div>

      <p class="hero-line">
        {{ profile.personaLine }} · {{ profile.当前年龄 }}岁 · {{ profile.状态 || '在训' }} · {{ profile.trainingMonths ? `在训第${profile.trainingMonths}` : '' }}
      </p>
      <p class="hero-sub">
        {{ profile.gateSummary }}
      </p>

      <div class="hero-pills">
        <span class="badge badge-dim">{{ profile.当前Phase || '未标注' }}</span>
        <span class="badge badge-dim">{{ profile.内在驱动方向 || '未标注驱动' }}</span>
        <span class="badge badge-dim">{{ profile.责任助教 || '未分配助教' }}</span>
      </div>
    </section>

    <section v-if="profile" class="card heavy-top-gold hero-credentials">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">入营标记</p>
          <h2>把门打开之前，先看 4 个关键信号</h2>
        </div>
        <span class="mono section-meta">{{ profile.gateCodeLabel || profile.gateCode || '未标注' }}</span>
      </div>

      <div class="credential-grid">
        <article class="credential-card">
          <span class="credential-label mono">关卡代号</span>
          <strong>{{ profile.gateCodeLabel || profile.gateCode || '未标注' }}</strong>
          <p>对外展示与当前 Phase 联动。</p>
        </article>
        <article class="credential-card">
          <span class="credential-label mono">D1 / D3 / D6</span>
          <strong>{{ profile.baseRatingSummary || '未录入' }}</strong>
          <p>入营时的三条基线，决定后续对比起点。</p>
        </article>
        <article class="credential-card">
          <span class="credential-label mono">肖像权授权</span>
          <strong :class="profile.portraitAuthorized ? 'gold' : 'spark'">{{ profile.portraitAuthorization || '未授权' }}</strong>
          <p>决定是否可以把孩子的画面当作活广告。</p>
        </article>
        <article class="credential-card">
          <span class="credential-label mono">已解锁成就</span>
          <strong>{{ profile.achievementCount || 0 }} 枚</strong>
          <p>{{ profile.achievementSummary || '暂无已解锁成就' }}</p>
        </article>
      </div>
    </section>

    <section class="card heavy-top-teal">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">关卡地图</p>
          <h2>八个关口，当前高亮在第 {{ profile?.gateIndex || 1 }} 关</h2>
        </div>
        <span class="mono section-meta">8 格</span>
      </div>

      <div class="gate-grid">
        <GateBadge
          v-for="gate in smartYouthGateCatalog"
          :key="gate.index"
          :gate="gate"
          :current-index="profile?.gateIndex || 0"
        />
      </div>
    </section>

    <section class="card heavy-top-gold">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">当前作品</p>
          <h2>正在被看见的项目</h2>
        </div>
        <span class="mono section-meta">{{ featuredProject ? featuredProject.状态 : '暂无作品' }}</span>
      </div>

      <article v-if="featuredProject" class="featured-project">
        <div class="project-line">
          <span class="badge badge-gold">{{ featuredProject.参赛记录 || '未记录参赛' }}</span>
          <span class="badge badge-teal">{{ featuredProject.商业价值 || '未标注价值' }}</span>
        </div>
        <h3>{{ featuredProject.项目名称 }}</h3>
        <p class="project-copy serif">{{ featuredProject.一句话描述 }}</p>
        <p class="project-desc">{{ featuredProject.解决的问题 }}</p>
      </article>

      <article v-else class="empty-card">
        暂无已识别项目。
      </article>
    </section>

    <section class="card heavy-top-spark">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">下一步</p>
          <h2>未来两周值得跟进的动作</h2>
        </div>
        <span class="mono section-meta">{{ upcoming.length ? `${upcoming.length} 条待办` : '暂无计划' }}</span>
      </div>

      <div v-if="nextActions.length" class="action-stack">
        <ActionItem
          v-for="action in nextActions"
          :key="`${action.title}-${action.dateLabel}`"
          :action="action"
        />
      </div>
      <p v-else class="empty-copy">暂无计划，请联系总教头。</p>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ActionItem from '../../components/smart-youth/ActionItem.vue'
import GateBadge from '../../components/smart-youth/GateBadge.vue'
import { smartYouthGateCatalog, getHighlightTone, formatSmartYouthDate } from '../../data/smartYouthTheme'
import { useStudentProfile } from '../../hooks/useStudentProfile'
import { useProjects } from '../../hooks/useProjects'
import { useMilestones } from '../../hooks/useMilestones'
import { useRoute } from 'vue-router'

const route = useRoute()
const studentId = computed(() => String(route.params.studentId || ''))

const { profile } = useStudentProfile(studentId)
const { featured } = useProjects(studentId)
const { upcoming, nextTwoWeeks } = useMilestones(studentId)

const featuredProject = computed(() => featured.value)

const nextActions = computed(() => {
  if (!nextTwoWeeks.value.length) {
    return []
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
.hero-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-identity {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-head,
.section-head,
.project-line {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.hero-head h1 {
  margin: 0;
  font-size: clamp(36px, 4.6vw, 68px);
  line-height: 1.02;
}

.hero-line {
  color: rgba(245, 240, 232, 0.86);
  line-height: 1.8;
}

.hero-sub {
  color: var(--paper);
  line-height: 1.8;
}

.hero-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-credentials {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.credential-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.credential-card {
  padding: 16px 18px;
  border: 1px solid var(--rule-light);
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.credential-label {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.14em;
}

.credential-card strong {
  font-size: 18px;
  line-height: 1.35;
}

.credential-card p {
  color: rgba(245, 240, 232, 0.74);
  line-height: 1.7;
}

.gate-grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 10px;
}

.featured-project {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.featured-project h3 {
  margin: 0;
  font-size: clamp(26px, 3vw, 36px);
}

.project-copy {
  font-size: 18px;
  line-height: 1.7;
}

.project-desc {
  color: rgba(245, 240, 232, 0.82);
  line-height: 1.8;
}

.action-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-copy,
.empty-card {
  color: var(--dim);
}

@media (max-width: 1200px) {
  .gate-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .credential-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .hero-head,
  .section-head,
  .project-line {
    flex-direction: column;
  }

  .gate-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .credential-grid {
    grid-template-columns: 1fr;
  }
}
</style>
