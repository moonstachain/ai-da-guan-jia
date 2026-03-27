<template>
  <section class="selector-hero card heavy-top-gold">
    <div class="selector-copy">
      <p class="eyebrow mono">AI造物 · 以赛代练 · 家长入口</p>
      <h1>选择你的孩子</h1>
      <p class="selector-lede">
        家长打开后先选自己的孩子。涛哥也能把游小鹏案例页直接当作“活广告”发给潜在家长。
      </p>
    </div>

    <div class="selector-metrics">
      <article class="metric">
        <div class="metric-label">在训学员</div>
        <div class="metric-val">{{ students.length }}</div>
      </article>
      <article class="metric">
        <div class="metric-label">数据源</div>
        <div class="metric-val">{{ sourceLabel }}</div>
      </article>
    </div>
  </section>

  <section v-if="loading" class="selector-grid">
    <article v-for="index in 3" :key="index" class="student-card card skeleton-card">
      <div class="skeleton-line short"></div>
      <div class="skeleton-line tall"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line"></div>
    </article>
  </section>

  <section v-else-if="students.length" class="selector-grid">
    <StudentCard
      v-for="student in students"
      :key="student.孩子ID"
      :student="student"
      @open="openStudent"
    />
  </section>

  <section v-else class="card empty-card">
    暂无在训学员，请检查飞书数据源是否已连通。
  </section>
</template>

<script setup>
import { computed } from 'vue'
import StudentCard from '../../components/smart-youth/StudentCard.vue'
import { useSmartYouthContext } from '../../hooks/useSmartYouthContext'

const { students, loading, source, switchStudent } = useSmartYouthContext()

const sourceLabel = computed(() => (source.value === 'feishu' ? '飞书实时' : '本地回退'))

const openStudent = (studentId) => {
  switchStudent(studentId)
}
</script>

<style scoped>
.selector-hero {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.selector-copy h1 {
  margin: 10px 0 0;
  font-size: clamp(36px, 4vw, 56px);
  line-height: 1.05;
}

.selector-lede {
  margin-top: 10px;
  max-width: 60ch;
  color: rgba(245, 240, 232, 0.82);
  line-height: 1.75;
}

.selector-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.selector-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.empty-card {
  color: var(--dim);
}

.skeleton-card {
  gap: 10px;
}

.skeleton-line {
  height: 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.skeleton-line.short {
  width: 42%;
}

.skeleton-line.tall {
  height: 24px;
}

@media (max-width: 1100px) {
  .selector-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .selector-metrics,
  .selector-grid {
    grid-template-columns: 1fr;
  }
}
</style>
