<template>
  <div class="strategic-page">
    <div class="ambient ambient-one"></div>
    <div class="ambient ambient-two"></div>

    <header class="hero">
      <div>
        <p class="eyebrow">治理驾驶舱 2.0 · Strategic Task Tracker</p>
        <h1>战略任务追踪</h1>
        <p class="subtitle">
          打开后先看全局，再看阻塞，再看历史。把战略任务从“记得住”变成“追得上”。
        </p>
      </div>

      <div class="hero-actions">
        <router-link to="/wealth-philosophy" class="promo-btn">
          财富三观
        </router-link>
        <div class="status-chip" :class="refreshStateClass">
          <span class="status-dot"></span>
          {{ refreshStatusText }}
        </div>
        <button class="refresh-btn" @click="refreshBoard">
          刷新
        </button>
      </div>
    </header>

    <section class="meta-row">
      <article v-for="card in kpiCards" :key="card.label" class="kpi-card">
        <div class="kpi-label">{{ card.label }}</div>
        <div class="kpi-value">{{ card.value }}</div>
        <div class="kpi-footnote">{{ card.note }}</div>
      </article>
    </section>

    <section class="project-panel">
      <div class="section-head">
        <div>
          <p class="section-kicker">项目选择器</p>
          <h2>在 R18 与历史项目之间切换</h2>
        </div>
        <div class="section-summary">
          <span>{{ selectedProject.project_status }}</span>
          <span>{{ selectedProject.project_name }}</span>
        </div>
      </div>

      <div class="project-pills">
        <button
          v-for="project in orderedProjects"
          :key="project.project_id"
          class="project-pill"
          :class="{ active: project.project_id === selectedProjectId }"
          @click="selectedProjectId = project.project_id"
        >
          <span class="project-pill-id">{{ project.project_id }}</span>
          <span class="project-pill-name">{{ project.project_status }}</span>
          <span class="project-pill-count">{{ project.total }} tasks</span>
        </button>
      </div>

      <div class="progress-card">
        <div class="progress-header">
          <div>
            <div class="progress-title">{{ selectedProject.project_name }}</div>
            <div class="progress-subtitle">
              {{ selectedProject.completed }} / {{ selectedProject.total }} 已完成
              · {{ selectedProject.blocked }} 阻塞
              · {{ selectedProject.pending }} 待启动
            </div>
          </div>
          <div class="progress-percent">{{ progressPercent }}%</div>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>
        </div>
      </div>
    </section>

    <section class="content-grid">
      <article class="task-panel">
        <div class="section-head compact">
          <div>
            <p class="section-kicker">任务拆解清单</p>
            <h2>按状态和优先级排序</h2>
          </div>
          <div class="small-copy">自动刷新倒计时：{{ refreshCountdownLabel }}</div>
        </div>

        <div class="task-list">
          <div
            v-for="task in selectedProjectTasks"
            :key="task.task_id"
            class="task-row"
            :class="task.task_statusClass"
          >
            <div class="task-main">
              <div class="task-topline">
                <div class="task-id">{{ task.task_id }}</div>
                <div class="status-badge" :class="task.task_statusClass">
                  {{ task.task_status }}
                </div>
              </div>
              <div class="task-name">{{ task.task_name }}</div>
              <div class="task-note">
                负责人 {{ task.owner }}
                <span v-if="task.dependencies"> · 依赖 {{ task.dependencies }}</span>
                <span v-if="task.blockers"> · 阻塞 {{ task.blockers }}</span>
              </div>
            </div>

            <div class="task-side">
              <div class="priority-pill">{{ task.priority }}</div>
              <div class="task-meta">
                <span v-if="task.completion_date">完成 {{ formatDate(task.completion_date) }}</span>
                <span v-else-if="task.start_date">开始 {{ formatDate(task.start_date) }}</span>
                <span v-else>待排期</span>
              </div>
              <div v-if="task.evidence_ref" class="task-evidence">{{ task.evidence_ref }}</div>
            </div>
          </div>
        </div>
      </article>

      <aside class="side-panel">
        <div class="alert-card">
          <div class="section-kicker">阻塞项告警</div>
          <div v-if="blockedTasks.length > 0" class="blocked-list">
            <div v-for="task in blockedTasks" :key="task.task_id" class="blocked-item">
              <div class="blocked-title">{{ task.task_id }} · {{ task.task_name }}</div>
              <div class="blocked-copy">{{ task.blockers }}</div>
              <div class="blocked-meta">负责方 {{ task.owner }} · 依赖 {{ task.dependencies || '无' }}</div>
            </div>
          </div>
          <div v-else class="empty-state">当前项目没有阻塞项。</div>
        </div>

        <div class="timeline-card">
          <div class="section-kicker">完成时间线</div>
          <div v-if="completionTimeline.length > 0" class="timeline">
            <div v-for="item in completionTimeline" :key="item.task_id" class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-body">
                <div class="timeline-date">{{ formatDate(item.completion_date) }}</div>
                <div class="timeline-title">{{ item.task_id }} · {{ item.task_name }}</div>
                <div class="timeline-copy">{{ item.owner }} · {{ item.priority }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">暂无已完成任务。</div>
        </div>

        <div class="summary-card">
          <div class="section-kicker">当前视图</div>
          <div class="summary-lines">
            <div>项目：{{ selectedProject.project_id }}</div>
            <div>状态：{{ selectedProject.project_status }}</div>
            <div>数据源：{{ dataSourceLabel }}</div>
            <div v-if="dataSourceHint">来源：{{ dataSourceHint }}</div>
            <div>最近刷新：{{ lastRefreshedLabel }}</div>
          </div>
        </div>
      </aside>
    </section>

    <section v-if="loadError" class="fallback-banner">
      <div class="fallback-title">数据回退</div>
      <div class="fallback-copy">{{ loadError }}</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getStrategicTasks } from '../api/strategicTasks'
import {
  strategicTaskProjects as localStrategicTaskProjects,
  strategicTaskRecords as localStrategicTaskRecords
} from '../data/strategicTasks'

const refreshIntervalSeconds = 1800
const selectedProjectId = ref('R18')
const lastRefreshedAt = ref(Date.now())
const refreshCountdown = ref(refreshIntervalSeconds)
const clockTick = ref(0)
const dataSourceLabel = ref('本地种子')
const dataSourceHint = ref('页面尚未连接飞书实时数据')
const loadError = ref('')
const isLoading = ref(false)
const activeProjects = ref([...localStrategicTaskProjects])
const activeRecords = ref([...localStrategicTaskRecords])
let countdownTimer = null

const statusRank = {
  阻塞: 0,
  进行中: 1,
  待启动: 2,
  已完成: 3
}

const priorityRank = {
  P0: 0,
  P1: 1,
  P2: 2
}

const normalizeText = (value) => {
  if (value == null) return ''
  if (Array.isArray(value)) {
    return value.map(item => normalizeText(item)).filter(Boolean).join('、')
  }
  if (typeof value === 'object') {
    return normalizeText(value.name ?? value.text ?? value.value ?? value.label ?? value.display_text)
  }
  return String(value).trim()
}

const normalizeDate = (value) => {
  if (value == null || value === '') return ''
  if (Array.isArray(value)) {
    return normalizeDate(value[0])
  }
  if (typeof value === 'object') {
    return normalizeDate(value.value ?? value.timestamp ?? value.text ?? value.date)
  }
  if (typeof value === 'number') {
    const timestamp = Math.abs(value) >= 10 ** 12 ? value : value * 1000
    return new Date(timestamp).toISOString()
  }
  const text = String(value).trim()
  if (!text) return ''
  if (/^\d+$/.test(text)) {
    const timestamp = Number(text)
    return new Date(Math.abs(timestamp) >= 10 ** 12 ? timestamp : timestamp * 1000).toISOString()
  }
  return text
}

const normalizeTaskRecord = (record) => {
  const fields = record?.fields ?? record ?? {}
  return {
    project_id: normalizeText(fields.project_id),
    project_name: normalizeText(fields.project_name),
    project_status: normalizeText(fields.project_status) || '进行中',
    task_id: normalizeText(fields.task_id),
    task_name: normalizeText(fields.task_name),
    task_status: normalizeText(fields.task_status) || '待启动',
    priority: normalizeText(fields.priority) || 'P1',
    owner: normalizeText(fields.owner) || '未指定',
    start_date: normalizeDate(fields.start_date),
    completion_date: normalizeDate(fields.completion_date),
    blockers: normalizeText(fields.blockers),
    evidence_ref: normalizeText(fields.evidence_ref),
    dependencies: normalizeText(fields.dependencies),
    notes: normalizeText(fields.notes)
  }
}

const buildProjectList = (records) => {
  const fallbackOrder = new Map(localStrategicTaskProjects.map((project, index) => [project.project_id, index]))
  const byProject = new Map()

  for (const record of records) {
    if (!record.project_id || byProject.has(record.project_id)) continue
    const fallback = localStrategicTaskProjects.find(project => project.project_id === record.project_id) || {}
    byProject.set(record.project_id, {
      ...fallback,
      project_id: record.project_id,
      project_name: record.project_name || fallback.project_name || record.project_id,
      project_status: record.project_status || fallback.project_status || '进行中',
      project_order: fallback.project_order ?? fallbackOrder.get(record.project_id) ?? byProject.size
    })
  }

  const projects = [...byProject.values()].sort((a, b) => {
    if (a.project_order !== b.project_order) {
      return a.project_order - b.project_order
    }
    return a.project_id.localeCompare(b.project_id)
  })

  return projects.length > 0 ? projects : [...localStrategicTaskProjects]
}

const applyDataset = (records, sourceLabel, hint) => {
  const normalizedRecords = records.map(normalizeTaskRecord).filter(record => record.task_id)
  activeRecords.value = normalizedRecords
  activeProjects.value = buildProjectList(normalizedRecords)
  dataSourceLabel.value = sourceLabel
  dataSourceHint.value = hint

  if (!activeProjects.value.some(project => project.project_id === selectedProjectId.value)) {
    selectedProjectId.value = activeProjects.value[0]?.project_id || 'R18'
  }
}

const applyFallbackDataset = (message) => {
  activeRecords.value = [...localStrategicTaskRecords]
  activeProjects.value = [...localStrategicTaskProjects]
  dataSourceLabel.value = '本地种子'
  dataSourceHint.value = '页面暂时回退到本地种子数据'
  loadError.value = message

  if (!activeProjects.value.some(project => project.project_id === selectedProjectId.value)) {
    selectedProjectId.value = activeProjects.value[0]?.project_id || 'R18'
  }
}

const formatCountdown = (seconds) => {
  const safeSeconds = Math.max(0, Number(seconds) || 0)
  const minutes = Math.floor(safeSeconds / 60)
  const remainder = safeSeconds % 60
  return `${minutes}m ${String(remainder).padStart(2, '0')}s`
}

const orderedProjects = computed(() => {
  return [...activeProjects.value].sort((a, b) => a.project_order - b.project_order)
})

const selectedProject = computed(() => {
  return orderedProjects.value.find(project => project.project_id === selectedProjectId.value) || orderedProjects.value[0] || {
    project_id: 'R18',
    project_name: '战略任务追踪',
    project_status: '进行中'
  }
})

const selectedProjectTasks = computed(() => {
  return activeRecords.value
    .filter(task => task.project_id === selectedProjectId.value)
    .map(task => ({
      ...task,
      task_statusClass: statusClass(task.task_status)
    }))
    .sort((a, b) => {
      const statusDiff = statusRank[a.task_status] - statusRank[b.task_status]
      if (statusDiff !== 0) return statusDiff
      const priorityDiff = priorityRank[a.priority] - priorityRank[b.priority]
      if (priorityDiff !== 0) return priorityDiff
      return a.task_id.localeCompare(b.task_id)
    })
})

const selectedProjectStats = computed(() => {
  const tasks = activeRecords.value.filter(task => task.project_id === selectedProjectId.value)
  const total = tasks.length
  const completed = tasks.filter(task => task.task_status === '已完成').length
  const blocked = tasks.filter(task => task.task_status === '阻塞').length
  const inProgress = tasks.filter(task => task.task_status === '进行中').length
  const pending = tasks.filter(task => task.task_status === '待启动').length
  return { total, completed, blocked, inProgress, pending }
})

const kpiCards = computed(() => {
  const stats = selectedProjectStats.value
  return [
    { label: '总计', value: stats.total, note: '当前项目的全部任务' },
    { label: '已完成', value: stats.completed, note: '已经有真实证据的条目' },
    { label: '进行中', value: stats.inProgress, note: '正在被推进的任务' },
    { label: '阻塞', value: stats.blocked, note: '需要单独盯住的风险项' },
    { label: '待启动', value: stats.pending, note: '等待上游条件成熟' }
  ]
})

const progressPercent = computed(() => {
  const stats = selectedProjectStats.value
  if (!stats.total) return 0
  return Math.round((stats.completed / stats.total) * 100)
})

const blockedTasks = computed(() => {
  return selectedProjectTasks.value.filter(task => task.task_status === '阻塞')
})

const completionTimeline = computed(() => {
  return activeRecords.value
    .filter(task => task.project_id === selectedProjectId.value && task.task_status === '已完成' && task.completion_date)
    .sort((a, b) => new Date(b.completion_date) - new Date(a.completion_date))
})

const refreshStateClass = computed(() => {
  return refreshCountdown.value <= 300 ? 'urgent' : 'calm'
})

const refreshCountdownLabel = computed(() => formatCountdown(refreshCountdown.value))

const refreshStatusText = computed(() => {
  const countdownText = refreshCountdownLabel.value
  return refreshCountdown.value <= 300
    ? `即将自动刷新 · ${countdownText}`
    : `自动刷新中 · ${countdownText}`
})

const lastRefreshedLabel = computed(() => {
  clockTick.value
  const seconds = Math.max(0, Math.floor((Date.now() - lastRefreshedAt.value) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ago`
})

const statusClass = (status) => {
  if (status === '阻塞') return 'blocked'
  if (status === '进行中') return 'active'
  if (status === '待启动') return 'pending'
  return 'done'
}

const formatDate = (input) => {
  if (!input) return '-'
  const date = new Date(input)
  if (Number.isNaN(date.getTime())) return input
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
}

const loadStrategicTasks = async () => {
  if (isLoading.value) return
  isLoading.value = true
  try {
    const response = await getStrategicTasks()
    const payload = response?.data || response
    const records = Array.isArray(payload?.records) ? payload.records : []
    if (!records.length) {
      throw new Error('飞书接口返回了 0 条记录')
    }
    applyDataset(records, '飞书多维表', `Base ${payload.base_id} · Table ${payload.table_id}`)
    loadError.value = ''
  } catch (error) {
    applyFallbackDataset(error?.message || '飞书任务数据读取失败')
  } finally {
    lastRefreshedAt.value = Date.now()
    refreshCountdown.value = refreshIntervalSeconds
    clockTick.value += 1
    isLoading.value = false
  }
}

const refreshBoard = () => {
  void loadStrategicTasks()
}

onMounted(() => {
  void loadStrategicTasks()
  countdownTimer = window.setInterval(() => {
    refreshCountdown.value = Math.max(0, refreshCountdown.value - 1)
    clockTick.value += 1
    if (refreshCountdown.value <= 0) {
      void loadStrategicTasks()
    }
  }, 1000)
})

onBeforeUnmount(() => {
  if (countdownTimer) {
    window.clearInterval(countdownTimer)
  }
})
</script>

<style scoped>
.strategic-page {
  min-height: 100vh;
  padding: 32px;
  color: #eef3ff;
  background:
    radial-gradient(circle at top left, rgba(0, 229, 255, 0.16), transparent 32%),
    radial-gradient(circle at top right, rgba(105, 240, 174, 0.12), transparent 28%),
    linear-gradient(180deg, #050814 0%, #090d1a 38%, #0b1020 100%);
  position: relative;
  overflow: hidden;
}

.ambient {
  position: absolute;
  border-radius: 999px;
  filter: blur(20px);
  opacity: 0.55;
  pointer-events: none;
}

.ambient-one {
  width: 280px;
  height: 280px;
  top: -80px;
  right: -60px;
  background: rgba(0, 229, 255, 0.2);
}

.ambient-two {
  width: 360px;
  height: 360px;
  bottom: -160px;
  left: -140px;
  background: rgba(105, 240, 174, 0.12);
}

.hero,
.project-panel,
.content-grid {
  position: relative;
  z-index: 1;
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.eyebrow,
.section-kicker {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.72rem;
  color: rgba(191, 205, 255, 0.72);
}

.hero h1 {
  margin: 10px 0 12px;
  font-size: clamp(2.1rem, 4vw, 3.6rem);
  line-height: 1;
  letter-spacing: -0.05em;
}

.subtitle {
  max-width: 720px;
  font-size: 1rem;
  line-height: 1.8;
  color: rgba(224, 231, 255, 0.72);
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.status-chip,
.promo-btn,
.refresh-btn,
.kpi-card,
.progress-card,
.task-panel,
.side-panel > *,
.project-pill {
  border: 1px solid rgba(144, 164, 255, 0.16);
  background: rgba(10, 15, 32, 0.78);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(16px);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 999px;
  color: #dfe7ff;
  font-size: 0.9rem;
}

.promo-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 16px;
  border-radius: 999px;
  color: #0b1020;
  text-decoration: none;
  font-weight: 800;
  background: linear-gradient(135deg, #ffc468 0%, #69f0ae 100%);
}

.status-chip.urgent {
  border-color: rgba(255, 82, 82, 0.35);
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.06);
}

.refresh-btn {
  color: #0b1020;
  background: linear-gradient(135deg, #69f0ae 0%, #00e5ff 100%);
  border: none;
  border-radius: 999px;
  font-weight: 700;
  padding: 12px 18px;
  cursor: pointer;
}

.meta-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.kpi-card {
  border-radius: 18px;
  padding: 18px 18px 16px;
}

.kpi-label {
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(191, 205, 255, 0.7);
}

.kpi-value {
  margin-top: 12px;
  font-size: clamp(1.8rem, 3vw, 2.4rem);
  font-weight: 700;
}

.kpi-footnote {
  margin-top: 10px;
  color: rgba(224, 231, 255, 0.66);
  font-size: 0.82rem;
  line-height: 1.6;
}

.project-panel {
  border-radius: 24px;
  padding: 22px;
  margin-bottom: 18px;
  background: rgba(8, 13, 28, 0.7);
  border: 1px solid rgba(144, 164, 255, 0.14);
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-head h2 {
  margin-top: 6px;
  font-size: 1.2rem;
}

.section-summary,
.small-copy {
  color: rgba(224, 231, 255, 0.62);
  font-size: 0.88rem;
  line-height: 1.5;
}

.section-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.project-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.project-pill {
  display: grid;
  gap: 4px;
  min-width: 170px;
  padding: 14px 16px;
  border-radius: 18px;
  color: #eef3ff;
  text-align: left;
  cursor: pointer;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}

.project-pill:hover {
  transform: translateY(-1px);
}

.project-pill.active {
  border-color: rgba(105, 240, 174, 0.6);
  background: rgba(8, 18, 28, 0.94);
}

.project-pill-id {
  font-weight: 800;
  letter-spacing: 0.12em;
}

.project-pill-name,
.project-pill-count {
  color: rgba(224, 231, 255, 0.68);
  font-size: 0.85rem;
}

.progress-card {
  margin-top: 16px;
  border-radius: 20px;
  padding: 18px;
}

.progress-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.progress-title {
  font-weight: 700;
}

.progress-subtitle {
  margin-top: 6px;
  color: rgba(224, 231, 255, 0.66);
  font-size: 0.9rem;
}

.progress-percent {
  font-size: 1.6rem;
  font-weight: 800;
  color: #69f0ae;
}

.progress-bar {
  position: relative;
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.06);
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #69f0ae 0%, #00e5ff 100%);
  box-shadow: 0 0 24px rgba(0, 229, 255, 0.24);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.9fr);
  gap: 18px;
}

.task-panel,
.side-panel > * {
  border-radius: 22px;
}

.task-panel {
  padding: 22px;
}

.section-head.compact {
  margin-bottom: 18px;
}

.task-list {
  display: grid;
  gap: 12px;
}

.task-row {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 16px 15px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(144, 164, 255, 0.08);
}

.task-row.blocked {
  border-color: rgba(255, 82, 82, 0.34);
  background: rgba(255, 82, 82, 0.06);
}

.task-row.active {
  border-color: rgba(0, 229, 255, 0.26);
}

.task-row.pending {
  opacity: 0.92;
}

.task-main {
  min-width: 0;
}

.task-topline,
.task-side {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.task-topline {
  margin-bottom: 8px;
}

.task-id {
  color: rgba(191, 205, 255, 0.74);
  font-size: 0.82rem;
  letter-spacing: 0.12em;
}

.status-badge,
.priority-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
}

.status-badge.done {
  color: #69f0ae;
  background: rgba(105, 240, 174, 0.12);
}

.status-badge.active {
  color: #00e5ff;
  background: rgba(0, 229, 255, 0.12);
}

.status-badge.blocked {
  color: #ff7979;
  background: rgba(255, 82, 82, 0.12);
}

.status-badge.pending {
  color: #a0a9c9;
  background: rgba(160, 169, 201, 0.12);
}

.task-name {
  font-size: 1.02rem;
  font-weight: 700;
  line-height: 1.5;
}

.task-note,
.task-meta,
.task-evidence,
.blocked-copy,
.blocked-meta,
.timeline-copy,
.summary-lines {
  color: rgba(224, 231, 255, 0.66);
  font-size: 0.88rem;
  line-height: 1.6;
}

.task-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 190px;
  text-align: right;
}

.priority-pill {
  color: #0b1020;
  background: linear-gradient(135deg, #69f0ae 0%, #d1f5ff 100%);
}

.task-evidence {
  font-size: 0.78rem;
  word-break: break-all;
}

.side-panel {
  display: grid;
  gap: 16px;
}

.alert-card,
.timeline-card,
.summary-card {
  padding: 18px;
  border-radius: 22px;
}

.blocked-list,
.timeline,
.summary-lines {
  display: grid;
  gap: 12px;
  margin-top: 10px;
}

.blocked-item,
.timeline-item {
  padding: 12px 0;
}

.blocked-title,
.timeline-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.empty-state {
  margin-top: 10px;
  color: rgba(224, 231, 255, 0.64);
  font-size: 0.9rem;
}

.timeline-item {
  display: flex;
  gap: 12px;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(180deg, #69f0ae 0%, #00e5ff 100%);
  box-shadow: 0 0 0 6px rgba(0, 229, 255, 0.08);
  margin-top: 5px;
  flex-shrink: 0;
}

.timeline-date {
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  color: rgba(191, 205, 255, 0.76);
  margin-bottom: 4px;
}

.fallback-banner {
  position: relative;
  z-index: 1;
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(255, 181, 74, 0.22);
  background: rgba(13, 17, 30, 0.82);
  color: #ffe1b5;
}

.fallback-title {
  margin-bottom: 6px;
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(255, 225, 181, 0.72);
}

.fallback-copy {
  line-height: 1.6;
  color: rgba(255, 235, 213, 0.9);
}

@media (max-width: 1080px) {
  .meta-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .strategic-page {
    padding: 18px;
  }

  .hero {
    flex-direction: column;
  }

  .hero-actions {
    width: 100%;
    justify-content: space-between;
  }

  .meta-row {
    grid-template-columns: 1fr;
  }

  .project-pill {
    min-width: 100%;
  }

  .task-row {
    flex-direction: column;
  }

  .task-side {
    align-items: flex-start;
    text-align: left;
    min-width: 0;
  }
}
</style>
