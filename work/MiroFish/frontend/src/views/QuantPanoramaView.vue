<template>
  <div class="wealth-page quant-panorama">
    <div class="glow glow-one"></div>
    <div class="glow glow-two"></div>

    <header class="page-header">
      <div class="brand-row">
        <router-link to="/home" class="brand">MIROFISH</router-link>
        <span class="crumb">/ 财富三观 · 虚实之变 · 量化投资全景</span>
      </div>

      <div class="nav-row">
        <router-link to="/wealth-philosophy" class="nav-pill">总览</router-link>
        <router-link to="/wealth-philosophy/past-present" class="nav-pill">古今之变</router-link>
        <router-link to="/wealth-philosophy/east-west" class="nav-pill">东西之变</router-link>
        <router-link to="/wealth-philosophy/virtual-real" class="nav-pill">虚实之变</router-link>
        <router-link to="/wealth-philosophy/virtual-real/quant-panorama" class="nav-pill active">
          量化全景
        </router-link>
        <button type="button" class="nav-pill nav-button" @click="resetPanorama">
          重置视图
        </button>
      </div>
    </header>

    <section class="hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">Layer 1 · Treemap Panorama</p>
        <h1>{{ overview.title }}</h1>
        <p class="quote">{{ overview.quote }}</p>
        <p class="summary">{{ overview.summary }}</p>

        <div class="breadcrumb-bar" aria-label="breadcrumb">
          <button
            v-for="crumb in breadcrumbs"
            :key="crumb.label"
            type="button"
            class="breadcrumb-chip"
            :class="{ active: crumb.active }"
            @click="crumb.onClick"
          >
            <span class="breadcrumb-label">{{ crumb.label }}</span>
            <span class="breadcrumb-hint">{{ crumb.hint }}</span>
          </button>
        </div>

        <div class="hero-chips">
          <span v-for="chip in heroChips" :key="chip.label" class="chip">
            <strong>{{ chip.label }}</strong>
            <span>{{ chip.value }}</span>
          </span>
        </div>
      </div>

      <aside class="hero-panel">
        <div class="panel-title">行业总览条</div>
        <p class="panel-copy">{{ overview.subtitle }}</p>

        <div class="stat-grid">
          <article v-for="stat in overview.stats" :key="stat.label" class="stat-card">
            <div class="stat-label">{{ stat.label }}</div>
            <div class="stat-value">{{ stat.value }}</div>
          </article>
        </div>

        <div class="meta-strip">
          <span v-for="meta in overview.meta" :key="meta.label" class="meta-pill">
            {{ meta.label }} · {{ meta.value }}
          </span>
        </div>
      </aside>
    </section>

    <section class="panorama-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">全景地图</p>
          <h2>先全貌，再纵深</h2>
        </div>
        <p class="section-copy">
          块面积按家族下属节点数分配，颜色映射风险特征，点击任一策略家族即可进入 Layer 2。
        </p>
      </div>

      <div class="treemap-grid">
        <button
          v-for="family in familyTiles"
          :key="family.node_id"
          type="button"
          class="family-card treemap-card"
          :class="{ active: family.node_id === selectedFamilyId }"
          :style="{
            '--family-color': family.color_code,
            gridColumn: `span ${family.span}`,
            minHeight: `${family.height}px`
          }"
          @click="selectFamily(family.node_id)"
        >
          <div class="family-glow"></div>

          <div class="family-topline">
            <span class="family-code">{{ family.node_id }}</span>
            <span class="family-mode">{{ family.decision_mode }}</span>
          </div>

          <div class="family-count">{{ family.descendantCount }}</div>
          <h3>{{ family.node_name }}</h3>
          <p class="family-desc">{{ family.description }}</p>

          <div class="family-meta">
            <span>{{ family.industry_avg_return_2025 }}</span>
            <span>{{ family.risk_return_profile }}</span>
            <span>{{ family.strategyAxis }}</span>
          </div>

          <div class="family-chip-row">
            <span>{{ family.categoryCount }} 子类</span>
            <span>{{ family.variantCount }} 变体</span>
            <span>{{ family.treemapHint }}</span>
          </div>

          <div class="family-footer">点击进入 Layer 2 · {{ family.node_name }}</div>
        </button>
      </div>

      <div class="kpi-grid">
        <article v-for="stat in panoramaKpis" :key="stat.label" class="kpi-card">
          <div class="kpi-label">{{ stat.label }}</div>
          <div class="kpi-value">{{ stat.value }}</div>
        </article>
      </div>
    </section>

    <section v-if="selectedFamily" class="category-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">Layer 2</p>
          <h2>{{ selectedFamily.node_name }} · 策略家族详情</h2>
        </div>
        <p class="section-copy">{{ selectedFamily.description }}</p>
      </div>

      <div class="family-summary-grid">
        <article v-for="stat in selectedFamilyStats" :key="stat.label" class="family-summary-card">
          <div class="family-summary-label">{{ stat.label }}</div>
          <div class="family-summary-value">{{ stat.value }}</div>
        </article>
      </div>

      <div class="category-grid">
        <button
          v-for="category in categories"
          :key="category.node_id"
          type="button"
          class="category-card"
          :class="{
            active: category.node_id === selectedCategoryId,
            highlighted: category.is_highlighted
          }"
          @click="selectCategory(category.node_id)"
        >
          <div class="category-topline">
            <span class="category-name">{{ category.node_name }}</span>
            <span class="category-mode">{{ category.decision_mode }}</span>
          </div>

          <p class="category-desc">{{ category.description }}</p>

          <div class="category-metrics">
            <span>变体 {{ category.variantCount }} 个</span>
            <span>AI {{ category.ai_dependency }}/5</span>
            <span>{{ category.expected_annual_return }}</span>
          </div>

          <div class="fit-tags">
            <span v-for="fit in category.market_condition_fit" :key="fit" class="fit-tag">
              {{ fit }}
            </span>
          </div>

          <p class="category-analogy">{{ category.analogy }}</p>
        </button>
      </div>
    </section>

    <section v-if="selectedCategory" class="detail-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">Layer 3</p>
          <h2>{{ selectedCategory.node_name }} · 变体详情</h2>
        </div>
        <p class="section-copy">{{ selectedCategory.description }}</p>
      </div>

      <div class="detail-card">
        <div class="detail-summary">
          <div class="detail-stat">
            <span>策略家族</span>
            <strong>{{ selectedFamily?.node_name }}</strong>
          </div>
          <div class="detail-stat">
            <span>子类轴</span>
            <strong>{{ selectedCategory.classification_axis }}</strong>
          </div>
          <div class="detail-stat">
            <span>风险收益</span>
            <strong>{{ selectedCategory.risk_return_profile }}</strong>
          </div>
          <div class="detail-stat">
            <span>AI 依赖</span>
            <strong>{{ selectedCategory.ai_dependency }}/5</strong>
          </div>
        </div>

        <div class="detail-notes">
          <article class="detail-note">
            <span>品类说明</span>
            <strong>{{ selectedCategory.description }}</strong>
          </article>
          <article class="detail-note accent">
            <span>类比说明</span>
            <strong>{{ selectedCategory.analogy }}</strong>
          </article>
        </div>

        <div class="table-wrap">
          <table class="variant-table">
            <thead>
              <tr>
                <th class="sticky-col">指标</th>
                <th
                  v-for="variant in selectedCategory.children"
                  :key="variant.node_id"
                  :class="{ highlighted: variant.is_highlighted }"
                >
                  <div class="variant-head">
                    <span class="variant-name">{{ variant.node_name }}</span>
                    <span v-if="variant.is_highlighted" class="variant-badge">重点关注</span>
                  </div>
                  <div class="variant-sub">{{ variant.node_name_en }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="metric in detailMetrics" :key="metric.key">
                <th class="sticky-col">{{ metric.label }}</th>
                <td
                  v-for="variant in selectedCategory.children"
                  :key="`${metric.key}-${variant.node_id}`"
                  :class="{ highlighted: variant.is_highlighted }"
                >
                  {{ getVariantValue(variant, metric.key) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="compare-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">范式对比</p>
          <h2>主观 vs 量化</h2>
        </div>
        <p class="section-copy">
          量化不是否定人，而是把人的经验压缩成可迭代、可验证、可扩容的系统。
        </p>
      </div>

      <div class="compare-grid">
        <article class="compare-card subjective">
          <div class="compare-title">人脑（主观）</div>
          <div v-for="row in comparisonRows" :key="row.label" class="compare-row">
            <span>{{ row.label }}</span>
            <strong>{{ row.subjective }}</strong>
          </div>
        </article>

        <article class="compare-card quantitative">
          <div class="compare-title">AI 脑（量化）</div>
          <div v-for="row in comparisonRows" :key="row.label" class="compare-row">
            <span>{{ row.label }}</span>
            <strong>{{ row.quantitative }}</strong>
          </div>
        </article>
      </div>

      <div class="callout">
        <strong>底部金句：</strong>
        你不跟 AI 下棋了，为什么还在跟 AI 做交易对手？
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  quantPanoramaComparison,
  quantPanoramaFamilies,
  quantPanoramaNodes,
  quantPanoramaOverview
} from '../data/wealthPhilosophy'

const overview = quantPanoramaOverview
const families = quantPanoramaFamilies

const viewMode = ref('panorama')
const selectedFamilyId = ref(families[0]?.node_id || '')
const selectedCategoryId = ref(families[0]?.children?.[0]?.node_id || '')

const clamp = (value, min, max) => Math.max(min, Math.min(max, value))

const sumCategoryVariants = (family) =>
  family.children.reduce((sum, category) => sum + (category.variants?.length || 0), 0)

const countFamilyNodes = (family) => family.children.length + sumCategoryVariants(family)

const allocateSpans = (weights, total = 12, minSpan = 2) => {
  if (!weights.length) return []
  const safeWeights = weights.map(weight => Math.max(1, weight))
  const totalWeight = safeWeights.reduce((sum, weight) => sum + weight, 0) || 1
  const raw = safeWeights.map(weight => (weight / totalWeight) * total)
  const spans = raw.map(value => Math.max(minSpan, Math.floor(value)))
  let assigned = spans.reduce((sum, value) => sum + value, 0)
  const fractions = raw
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction)

  let fractionIndex = 0
  while (assigned < total) {
    spans[fractions[fractionIndex % fractions.length].index] += 1
    assigned += 1
    fractionIndex += 1
  }

  while (assigned > total) {
    const reducible = [...spans.entries()].sort((a, b) => b[1] - a[1]).find(([, span]) => span > minSpan)
    if (!reducible) break
    spans[reducible[0]] -= 1
    assigned -= 1
  }

  return spans
}

const familyTileSource = computed(() =>
  families.map((family) => {
    const categoryCount = family.children.length
    const variantCount = sumCategoryVariants(family)
    const descendantCount = countFamilyNodes(family)
    return {
      ...family,
      categoryCount,
      variantCount,
      descendantCount,
      strategyAxis: family.classification_axis,
      treemapHint: family.is_highlighted ? '重点家族' : '策略家族',
      weight: descendantCount
    }
  })
)

const familyTiles = computed(() => {
  const weights = familyTileSource.value.map(item => item.weight)
  const spans = allocateSpans(weights, 12, 2)
  const maxWeight = Math.max(...weights, 1)

  return familyTileSource.value.map((family, index) => ({
    ...family,
    span: spans[index] || 3,
    height: clamp(Math.round(190 + (family.weight / maxWeight) * 120), 190, 340)
  }))
})

const selectedFamily = computed(
  () => families.find(family => family.node_id === selectedFamilyId.value) || families[0] || null
)

const categories = computed(() => selectedFamily.value?.children || [])

const selectedCategory = computed(() => {
  const current = categories.value.find(category => category.node_id === selectedCategoryId.value)
  return current || categories.value[0] || null
})

watch(
  selectedFamilyId,
  () => {
    selectedCategoryId.value = selectedFamily.value?.children?.[0]?.node_id || ''
  },
  { immediate: true }
)

const selectFamily = (familyId) => {
  selectedFamilyId.value = familyId
  viewMode.value = 'family'
}

const selectCategory = (categoryId) => {
  const family = families.find(item => item.children.some(category => category.node_id === categoryId))
  if (family) {
    selectedFamilyId.value = family.node_id
  }
  selectedCategoryId.value = categoryId
  viewMode.value = 'category'
}

const resetPanorama = () => {
  viewMode.value = 'panorama'
  selectedFamilyId.value = families[0]?.node_id || ''
  selectedCategoryId.value = families[0]?.children?.[0]?.node_id || ''
}

const modeCounts = computed(() => {
  const counts = new Map()
  quantPanoramaNodes.forEach((node) => {
    const key = (node.decision_mode || '其他').replace(/\s+/g, '')
    counts.set(key, (counts.get(key) || 0) + 1)
  })
  return counts
})

const marketCounts = computed(() => {
  const counts = new Map()
  quantPanoramaNodes.forEach((node) => {
    ;(node.market_condition_fit || []).forEach((fit) => {
      counts.set(fit, (counts.get(fit) || 0) + 1)
    })
  })
  return counts
})

const formatBreakdown = (counts, order) =>
  order
    .filter(key => counts.get(key))
    .map(key => `${key} ${counts.get(key)}`)
    .join(' / ')

const breadcrumbs = computed(() => {
  const trail = [
    {
      label: '全景',
      hint: 'Layer 1',
      active: viewMode.value === 'panorama',
      onClick: resetPanorama
    }
  ]

  if (selectedFamily.value) {
    trail.push({
      label: selectedFamily.value.node_name,
      hint: `Layer 2 · ${selectedFamily.value.children.length} 类`,
      active: viewMode.value !== 'panorama',
      onClick: () => {
        viewMode.value = 'family'
      }
    })
  }

  if (selectedCategory.value) {
    trail.push({
      label: selectedCategory.value.node_name,
      hint: 'Layer 3',
      active: viewMode.value === 'category',
      onClick: () => {
        viewMode.value = 'category'
      }
    })
  }

  return trail
})

const familyPath = computed(() => breadcrumbs.value.map(crumb => crumb.label).join(' › '))

const panoramaKpis = computed(() => [
  { label: '总策略节点', value: `${quantPanoramaNodes.length} 节点` },
  { label: '策略家族', value: `${families.length} 家族` },
  {
    label: '决策模式',
    value: formatBreakdown(modeCounts.value, ['量化', '主观', '量化+主观', '综合']) || '待统计'
  },
  {
    label: '市场适配',
    value: formatBreakdown(marketCounts.value, ['牛市', '震荡市', '结构市', '熊市']) || '待统计'
  }
])

const selectedFamilyStats = computed(() => {
  if (!selectedFamily.value) return []
  const variantCount = sumCategoryVariants(selectedFamily.value)
  return [
    { label: '子类数量', value: `${selectedFamily.value.children.length} 个` },
    { label: '变体数量', value: `${variantCount} 个` },
    { label: '策略轴', value: selectedFamily.value.classification_axis },
    { label: '行业均值', value: selectedFamily.value.industry_avg_return_2025 }
  ]
})

const heroChips = computed(() => [
  { label: '当前路径', value: familyPath.value },
  { label: '当前视图', value: viewMode.value === 'panorama' ? '全景地图' : viewMode.value === 'family' ? '家族视图' : '品类视图' },
  { label: '重点节点', value: `${overview.meta[2].value} 个` }
])

const detailMetrics = [
  { key: 'expected_annual_return', label: '预期年化' },
  { key: 'expected_excess_return', label: '超额收益' },
  { key: 'expected_max_drawdown', label: '最大回撤' },
  { key: 'market_condition_fit', label: '市场适配' },
  { key: 'industry_avg_return_2025', label: '行业均值' },
  { key: 'key_players', label: '代表机构' },
  { key: 'analogy', label: '类比说明' }
]

const comparisonRows = quantPanoramaComparison

const getVariantValue = (variant, key) => {
  if (key === 'market_condition_fit') {
    return Array.isArray(variant.market_condition_fit)
      ? variant.market_condition_fit.join(' / ')
      : variant.market_condition_fit || '—'
  }
  if (key === 'key_players') return variant.key_players || '—'
  if (key === 'analogy') return variant.analogy || '—'
  return variant[key] || '—'
}
</script>

<style scoped>
.wealth-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  padding: 28px;
  color: #f5f7ff;
  background:
    radial-gradient(circle at top left, rgba(0, 229, 255, 0.16), transparent 24%),
    radial-gradient(circle at top right, rgba(255, 196, 104, 0.14), transparent 22%),
    linear-gradient(180deg, #050913 0%, #09101e 54%, #11182a 100%);
}

.glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(28px);
  opacity: 0.64;
  pointer-events: none;
}

.glow-one {
  width: 340px;
  height: 340px;
  top: -120px;
  right: -80px;
  background: rgba(255, 196, 104, 0.14);
}

.glow-two {
  width: 420px;
  height: 420px;
  bottom: -180px;
  left: -140px;
  background: rgba(0, 229, 255, 0.12);
}

.page-header,
.hero-grid,
.panorama-section,
.category-section,
.detail-section,
.compare-section {
  position: relative;
  z-index: 1;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}

.brand-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.brand {
  color: inherit;
  text-decoration: none;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.crumb {
  color: rgba(233, 238, 255, 0.56);
  font-size: 0.92rem;
}

.nav-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.nav-pill,
.hero-copy,
.hero-panel,
.family-card,
.category-card,
.detail-card,
.compare-card,
.callout,
.kpi-card,
.family-summary-card,
.breadcrumb-chip,
.nav-button {
  border: 1px solid rgba(155, 176, 255, 0.16);
  background: rgba(11, 16, 32, 0.72);
  backdrop-filter: blur(14px);
  box-shadow: 0 20px 64px rgba(0, 0, 0, 0.22);
}

.nav-pill {
  color: inherit;
  text-decoration: none;
  padding: 10px 14px;
  border-radius: 999px;
}

.nav-button {
  color: inherit;
  padding: 10px 14px;
  border-radius: 999px;
  cursor: pointer;
}

.nav-pill.active,
.nav-button:hover {
  color: #08111f;
  background: linear-gradient(135deg, #00e5ff 0%, #ffc468 100%);
  border-color: transparent;
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.95fr);
  gap: 18px;
}

.hero-copy,
.hero-panel,
.family-card,
.category-card,
.detail-card,
.compare-card,
.callout,
.kpi-card,
.family-summary-card,
.breadcrumb-chip {
  border-radius: 24px;
}

.hero-copy {
  padding: 28px;
}

.eyebrow,
.section-kicker,
.panel-title {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.72rem;
  color: rgba(200, 214, 255, 0.7);
}

.hero-copy h1 {
  margin: 12px 0 10px;
  font-size: clamp(2.3rem, 4.8vw, 4.4rem);
  line-height: 1;
  letter-spacing: -0.06em;
}

.quote {
  color: #00e5ff;
  font-size: 1.08rem;
  line-height: 1.8;
}

.summary,
.panel-copy {
  margin-top: 14px;
  color: rgba(231, 236, 255, 0.74);
  line-height: 1.75;
}

.breadcrumb-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.breadcrumb-chip {
  padding: 12px 14px;
  text-align: left;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  min-width: 150px;
}

.breadcrumb-chip.active {
  border-color: rgba(0, 229, 255, 0.6);
  background: linear-gradient(180deg, rgba(0, 229, 255, 0.14), rgba(11, 16, 32, 0.74));
}

.breadcrumb-label {
  color: #f5f7ff;
  font-weight: 700;
}

.breadcrumb-hint {
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.82rem;
}

.hero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.chip {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  min-width: 160px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
}

.chip strong {
  color: #ffc468;
}

.chip span {
  color: rgba(231, 236, 255, 0.72);
  line-height: 1.5;
}

.hero-panel {
  padding: 22px;
}

.stat-grid {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.stat-card {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
}

.stat-label {
  color: rgba(231, 236, 255, 0.68);
}

.stat-value {
  margin-top: 8px;
  color: #00e5ff;
  font-size: 1.2rem;
  font-weight: 800;
}

.meta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.meta-pill {
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(231, 236, 255, 0.82);
}

.panorama-section,
.category-section,
.detail-section,
.compare-section {
  margin-top: 18px;
  padding: 22px;
  border-radius: 24px;
  background: rgba(8, 12, 24, 0.64);
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.section-kicker {
  margin-bottom: 8px;
}

.section-head h2 {
  font-size: clamp(1.35rem, 2vw, 1.95rem);
}

.section-copy {
  max-width: 540px;
  color: rgba(231, 236, 255, 0.72);
  line-height: 1.7;
}

.treemap-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
}

.family-card {
  position: relative;
  padding: 18px;
  text-align: left;
  color: inherit;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease,
    box-shadow 0.18s ease;
  border-left: 4px solid var(--family-color);
  overflow: hidden;
}

.treemap-card {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(8, 12, 24, 0.82));
}

.family-glow {
  position: absolute;
  inset: auto -40px -60px auto;
  width: 180px;
  height: 180px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--family-color) 24%, transparent);
  filter: blur(20px);
  opacity: 0.7;
  pointer-events: none;
}

.family-card:hover {
  transform: translateY(-2px);
}

.family-card.active {
  border-color: color-mix(in srgb, var(--family-color) 72%, white 28%);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.04));
  box-shadow:
    0 20px 64px rgba(0, 0, 0, 0.24),
    0 0 0 1px color-mix(in srgb, var(--family-color) 35%, transparent) inset;
}

.family-topline,
.category-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.family-code,
.category-mode {
  font-size: 0.78rem;
  color: rgba(231, 236, 255, 0.58);
}

.family-count {
  margin-top: 14px;
  font-size: clamp(2rem, 4vw, 3rem);
  font-weight: 800;
  color: #ffc468;
}

.family-card h3 {
  margin-top: 10px;
  font-size: 1.12rem;
}

.family-desc,
.category-desc,
.category-analogy {
  margin-top: 10px;
  color: rgba(231, 236, 255, 0.74);
  line-height: 1.65;
}

.family-meta,
.family-chip-row,
.fit-tags,
.category-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.family-meta span,
.family-chip-row span,
.fit-tag,
.category-metrics span {
  padding: 6px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(231, 236, 255, 0.84);
}

.family-footer {
  margin-top: 16px;
  color: rgba(231, 236, 255, 0.72);
  font-size: 0.84rem;
}

.kpi-grid,
.family-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.kpi-card,
.family-summary-card {
  padding: 16px;
  background: rgba(255, 255, 255, 0.04);
}

.kpi-label,
.family-summary-label {
  color: rgba(231, 236, 255, 0.68);
  font-size: 0.9rem;
}

.kpi-value,
.family-summary-value {
  margin-top: 8px;
  color: #00e5ff;
  font-size: 1.08rem;
  font-weight: 800;
  line-height: 1.5;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.category-card {
  padding: 18px;
  text-align: left;
  color: inherit;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.category-card:hover {
  transform: translateY(-2px);
}

.category-card.active {
  border-color: #00e5ff;
}

.category-card.highlighted {
  box-shadow:
    0 20px 64px rgba(0, 0, 0, 0.22),
    0 0 0 1px rgba(255, 196, 104, 0.26) inset;
}

.category-card.highlighted.active {
  border-color: #ffc468;
}

.category-name {
  font-size: 1.08rem;
  font-weight: 800;
}

.category-desc {
  min-height: 52px;
}

.category-metrics {
  margin-top: 14px;
}

.category-analogy {
  margin-top: 14px;
  color: #ffc468;
}

.detail-card {
  padding: 18px;
}

.detail-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-stat {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
}

.detail-stat span {
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.9rem;
}

.detail-stat strong {
  display: block;
  margin-top: 8px;
  color: #f5f7ff;
}

.detail-notes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
  margin-bottom: 16px;
}

.detail-note {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
}

.detail-note span {
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.9rem;
}

.detail-note strong {
  display: block;
  margin-top: 8px;
  line-height: 1.7;
}

.detail-note.accent {
  background: linear-gradient(180deg, rgba(0, 229, 255, 0.08), rgba(255, 255, 255, 0.04));
}

.table-wrap {
  overflow-x: auto;
}

.variant-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 880px;
}

.variant-table th,
.variant-table td {
  padding: 14px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  vertical-align: top;
}

.variant-table thead th {
  position: sticky;
  top: 0;
  background: rgba(11, 16, 32, 0.96);
  text-align: left;
  z-index: 1;
}

.sticky-col {
  width: 160px;
  color: #00e5ff;
  font-weight: 800;
  position: sticky;
  left: 0;
  background: rgba(11, 16, 32, 0.96);
  z-index: 2;
}

.variant-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.variant-name {
  font-size: 1rem;
  font-weight: 800;
}

.variant-sub {
  margin-top: 6px;
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.88rem;
}

.variant-badge {
  padding: 4px 8px;
  border-radius: 999px;
  color: #06111f;
  font-size: 0.76rem;
  font-weight: 800;
  background: linear-gradient(135deg, #ffc468 0%, #69f0ae 100%);
}

.variant-table th.highlighted,
.variant-table td.highlighted {
  background: rgba(255, 196, 104, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 196, 104, 0.16);
}

.compare-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.compare-card {
  padding: 18px;
}

.compare-card.subjective {
  background: linear-gradient(180deg, rgba(255, 134, 79, 0.12), rgba(11, 16, 32, 0.72));
}

.compare-card.quantitative {
  background: linear-gradient(180deg, rgba(0, 229, 255, 0.12), rgba(11, 16, 32, 0.72));
}

.compare-title {
  font-size: 1.05rem;
  font-weight: 800;
  margin-bottom: 10px;
}

.compare-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.compare-row span {
  color: rgba(231, 236, 255, 0.66);
}

.compare-row strong {
  line-height: 1.6;
}

.callout {
  margin-top: 16px;
  padding: 16px 18px;
  color: #00e5ff;
  line-height: 1.7;
}

@media (max-width: 1120px) {
  .hero-grid,
  .kpi-grid,
  .family-summary-grid,
  .category-grid,
  .detail-summary,
  .detail-notes,
  .compare-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .section-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .treemap-grid {
    grid-template-columns: 1fr;
  }

  .family-card {
    grid-column: auto !important;
  }
}

@media (max-width: 720px) {
  .wealth-page {
    padding: 18px;
  }

  .hero-copy,
  .hero-panel,
  .panorama-section,
  .category-section,
  .detail-section,
  .compare-section {
    padding: 18px;
  }

  .compare-row {
    grid-template-columns: 1fr;
  }

  .breadcrumb-chip {
    min-width: 100%;
  }
}
</style>
