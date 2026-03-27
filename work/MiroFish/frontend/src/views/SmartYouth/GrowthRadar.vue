<template>
  <div class="growth-page">
    <section class="card heavy-top-gold radar-card">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">六维成长</p>
          <h1>{{ profile?.姓名 || '未命名学员' }} 的双层雷达图</h1>
        </div>
        <span class="mono section-meta">{{ latestDateLabel }}</span>
      </div>

      <div ref="chartRef" class="radar-chart"></div>
      <p class="radar-note">
        入营基线用灰色，最新评估用金色。D4 仿真试错若未解锁，会在轴标签上保留灰色提示。
      </p>
    </section>

    <section class="card heavy-top-teal">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">六维进度条</p>
          <h2>从入营分到最新分</h2>
        </div>
        <span class="mono section-meta">{{ latestJudgment ? '总教头已复核' : '待评估' }}</span>
      </div>

      <DimensionBar
        v-for="dimension in dimensionEntries"
        :key="dimension.key"
        :item="dimension"
      />
    </section>

    <section class="card heavy-top-spark">
      <div class="section-head">
        <div>
          <p class="eyebrow mono">总教头判断</p>
          <h2>最强特质与下一个突破口</h2>
        </div>
      </div>

      <article v-if="latestJudgment" class="judgment-card">
        <p class="serif judgment-text">
          {{ judgmentLead }}
          <span v-if="judgmentBreakthrough" class="gold">{{ judgmentBreakthrough }}</span>
        </p>
      </article>
      <p v-else class="empty-copy">暂无总教头判断。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import DimensionBar from '../../components/smart-youth/DimensionBar.vue'
import { smartYouthDimensionCatalog, formatSmartYouthDate } from '../../data/smartYouthTheme'
import { useGrowthEval } from '../../hooks/useGrowthEval'
import { useStudentProfile } from '../../hooks/useStudentProfile'
import { useRoute } from 'vue-router'

const route = useRoute()
const studentId = computed(() => String(route.params.studentId || ''))

const { profile } = useStudentProfile(studentId)
const { baselineValues, latestValues, dimensionEntries, latestJudgment, latestDate } = useGrowthEval(studentId)

const chartRef = ref(null)
let chartInstance = null

const latestDateLabel = computed(() => formatSmartYouthDate(latestDate.value, { mode: 'short' }) || '暂无日期')

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

const radarOption = computed(() => ({
  tooltip: {
    trigger: 'item'
  },
  legend: {
    bottom: 0,
    textStyle: {
      color: '#f5f0e8',
      fontFamily: 'Space Mono'
    }
  },
  radar: {
    shape: 'polygon',
    indicator: smartYouthDimensionCatalog.map(dimension => ({
      name: dimension.label,
      max: 5,
      color: dimension.key === 'D4仿真试错' && dimensionEntries.value.find(item => item.key === 'D4仿真试错')?.locked
        ? '#6b6560'
        : '#f5f0e8'
    })),
    axisLine: {
      lineStyle: {
        color: 'rgba(255,255,255,0.1)'
      }
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255,255,255,0.06)'
      }
    },
    splitArea: {
      show: false
    },
    name: {
      textStyle: {
        color: '#f5f0e8',
        fontSize: 11,
        fontFamily: 'Space Mono'
      }
    }
  },
  series: [
    {
      name: '入营基线',
      type: 'radar',
      symbol: 'none',
      lineStyle: { color: 'rgba(255,255,255,0.28)', width: 1 },
      areaStyle: { color: 'rgba(255,255,255,0.05)' },
      data: [{ value: baselineValues.value }]
    },
    {
      name: '最新评估',
      type: 'radar',
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: '#c9a84c' },
      lineStyle: { color: '#c9a84c', width: 2 },
      areaStyle: { color: 'rgba(201,168,76,0.15)' },
      data: [{ value: latestValues.value }]
    }
  ]
}))

const renderChart = () => {
  if (!chartRef.value) {
    return
  }
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(radarOption.value, true)
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(async () => {
  await nextTick()
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})

watch([baselineValues, latestValues, dimensionEntries], async () => {
  await nextTick()
  renderChart()
}, { deep: true })
</script>

<style scoped>
.growth-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.radar-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.radar-chart {
  width: 100%;
  min-height: 420px;
}

.radar-note {
  color: var(--dim);
  line-height: 1.7;
}

.judgment-card {
  padding-top: 8px;
}

.judgment-text {
  font-size: clamp(22px, 2.8vw, 32px);
  line-height: 1.65;
}

.gold {
  color: var(--gold);
}

.empty-copy {
  color: var(--dim);
}

@media (max-width: 720px) {
  .radar-chart {
    min-height: 340px;
  }
}
</style>

