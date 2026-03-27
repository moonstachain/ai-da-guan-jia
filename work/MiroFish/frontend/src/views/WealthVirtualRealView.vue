<template>
  <div class="wealth-page track-page virtual-real">
    <header class="page-header">
      <div class="brand-row">
        <router-link to="/home" class="brand">MIROFISH</router-link>
        <span class="crumb">/ 财富三观 · 虚实之变</span>
      </div>
      <div class="nav-row">
        <router-link to="/wealth-philosophy" class="nav-pill">总览</router-link>
        <router-link to="/wealth-philosophy/past-present" class="nav-pill">古今之变</router-link>
        <router-link to="/wealth-philosophy/east-west" class="nav-pill">东西之变</router-link>
        <router-link to="/wealth-philosophy/virtual-real" class="nav-pill active">虚实之变</router-link>
      </div>
    </header>

    <section class="hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">Virtual / Real</p>
        <h1>{{ track.model_name }}</h1>
        <p class="quote">{{ track.quote }}</p>
        <p class="summary">{{ track.bridge }}</p>
      </div>

      <aside class="hero-panel">
        <div class="panel-title">页面目标</div>
        <p class="panel-copy">
          用四阶迁移拆解“实体 → 线上 → 链上 → 智能”，把未来资产的形态变化讲清楚。
        </p>
        <div class="mini-grid">
          <div v-for="kpi in track.kpis" :key="kpi.label" class="mini-card">
            <span>{{ kpi.label }}</span>
            <strong>{{ kpi.value }}</strong>
          </div>
        </div>
      </aside>
    </section>

    <section class="layer-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">资产迁移</p>
          <h2>虚实之间的四阶路径</h2>
        </div>
      </div>

      <div class="layer-grid">
        <article v-for="layer in track.layers" :key="layer.name" class="layer-card">
          <div class="layer-index">{{ layer.name }}</div>
          <p class="layer-thesis">{{ layer.thesis }}</p>
          <p class="layer-evidence">{{ layer.evidence }}</p>
          <div class="layer-chart">{{ layer.chart }}</div>
          <div v-if="layer.name === '智能资产'" class="layer-action">
            <router-link
              to="/wealth-philosophy/virtual-real/quant-panorama"
              class="deep-dive-link"
            >
              → 深入探索：量化投资全景
            </router-link>
          </div>
        </article>
      </div>
    </section>

    <section class="proposition-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">核心命题</p>
          <h2>为什么“虚”不是假</h2>
        </div>
      </div>

      <div class="proposition-grid">
        <article v-for="item in propositions.slice(0, 6)" :key="item.proposition_id" class="proposition-card">
          <div class="proposition-id">{{ item.proposition_id }}</div>
          <div class="proposition-title">{{ item.title }}</div>
          <p class="proposition-thesis">{{ item.thesis }}</p>
        </article>
      </div>
    </section>

    <section class="data-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">数据联动</p>
          <h2>线上税、链上税和智能税</h2>
        </div>
      </div>

      <div class="data-grid">
        <article class="data-card flow-card">
          <h3>形态迁移流</h3>
          <div class="flow-list">
            <div v-for="step in flowSteps" :key="step.label" class="flow-row">
              <div class="flow-label">{{ step.label }}</div>
              <div class="flow-note">{{ step.note }}</div>
            </div>
          </div>
        </article>

        <article class="data-card asset-card">
          <h3>标的库选取</h3>
          <div class="asset-list">
            <div v-for="asset in assets" :key="asset.asset_aesthetic_id" class="asset-row">
              <div>
                <div class="asset-name">{{ asset.asset_name }}</div>
                <div class="asset-meta">{{ asset.asset_form }} · {{ asset.representative_ticker }}</div>
              </div>
              <div class="asset-risk">{{ asset.risk_level }}</div>
            </div>
          </div>
        </article>

        <article class="data-card principle-card">
          <h3>配置原则</h3>
          <div class="principle-list">
            <div v-for="item in track.valuationNotes" :key="item.label" class="principle-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div class="chip-list">
            <span v-for="principle in principles" :key="principle" class="chip">{{ principle }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="strategy-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">行动指南</p>
          <h2>1% 原则和杠铃策略</h2>
        </div>
      </div>

      <div class="strategy-grid">
        <article v-for="strategy in strategies" :key="strategy.strategy_id" class="strategy-card">
          <div class="strategy-name">{{ strategy.strategy_name }}</div>
          <div class="strategy-line">{{ strategy.target_persona }}</div>
          <div class="strategy-line">{{ strategy.asset_threshold }}</div>
          <div class="strategy-meta">
            <span>{{ strategy.allocation_pct }}</span>
            <span>{{ strategy.holding_period }}</span>
            <span>{{ strategy.risk_profile }}</span>
          </div>
          <p class="strategy-guide">{{ strategy.action_guide }}</p>
        </article>
      </div>

      <div class="callout">
        <strong>行动提示：</strong>
        {{ track.actionGuide }}
      </div>
    </section>
  </div>
</template>

<script setup>
import {
  getAssetsForTrack,
  getPropositionsForTrack,
  getStrategiesForTrack,
  wealthPhilosophyTracks
} from '../data/wealthPhilosophy'

const track = wealthPhilosophyTracks.find(item => item.key === 'virtual-real')
const propositions = getPropositionsForTrack('virtual-real')
const strategies = getStrategiesForTrack('virtual-real')
const principles = track.principles
const assets = getAssetsForTrack('virtual-real').slice(0, 10)

const flowSteps = [
  { label: '实体 → 线上', note: '把现实中稀缺的东西压缩成平台可交易的入口。' },
  { label: '线上 → 链上', note: '把结算和所有权拆成协议层可以验证的模块。' },
  { label: '链上 → 智能', note: '让资产具备自主执行、自动分发和再配置能力。' }
]
</script>

<style scoped>
.wealth-page {
  min-height: 100vh;
  padding: 28px;
  color: #f4f7ff;
  background:
    radial-gradient(circle at top left, rgba(0, 229, 255, 0.18), transparent 24%),
    radial-gradient(circle at bottom right, rgba(255, 196, 104, 0.12), transparent 24%),
    linear-gradient(180deg, #050913 0%, #09101e 54%, #11182a 100%);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
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
  color: rgba(233, 238, 255, 0.58);
}

.nav-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.nav-pill,
.hero-copy,
.hero-panel,
.layer-card,
.data-card,
.strategy-card,
.callout,
.proposition-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(10, 14, 28, 0.72);
  backdrop-filter: blur(14px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.24);
}

.nav-pill {
  color: inherit;
  text-decoration: none;
  padding: 10px 14px;
  border-radius: 999px;
}

.nav-pill.active {
  color: #08111f;
  background: linear-gradient(135deg, #00e5ff 0%, #ffc468 100%);
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.85fr);
  gap: 18px;
}

.hero-copy,
.hero-panel,
.layer-card,
.data-card,
.strategy-card,
.callout,
.proposition-card {
  border-radius: 22px;
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

.hero-panel {
  padding: 22px;
}

.mini-grid {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.mini-card {
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mini-card span {
  color: rgba(231, 236, 255, 0.68);
}

.mini-card strong {
  color: #00e5ff;
}

.layer-section,
.proposition-section,
.data-section,
.strategy-section {
  margin-top: 18px;
  padding: 22px;
  border-radius: 24px;
  background: rgba(8, 12, 24, 0.64);
}

.layer-grid,
.proposition-grid,
.data-grid,
.strategy-grid {
  display: grid;
  gap: 14px;
}

.layer-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.proposition-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.data-grid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 0.9fr);
}

.strategy-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.layer-card,
.data-card,
.strategy-card,
.proposition-card {
  padding: 18px;
}

.layer-index {
  font-weight: 800;
  color: #00e5ff;
  margin-bottom: 12px;
}

.layer-thesis {
  font-size: 1rem;
  line-height: 1.72;
  color: #f6f8ff;
}

.layer-evidence {
  margin-top: 10px;
  color: rgba(231, 236, 255, 0.7);
  line-height: 1.65;
}

.layer-chart {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  color: #ffc468;
}

.layer-action {
  margin-top: 14px;
}

.deep-dive-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 14px;
  color: #06111f;
  text-decoration: none;
  font-weight: 700;
  background: linear-gradient(135deg, #00e5ff 0%, #ffc468 100%);
  box-shadow: 0 14px 30px rgba(0, 229, 255, 0.18);
  transition: transform 0.18s ease;
}

.deep-dive-link:hover {
  transform: translateY(-1px);
}

.proposition-id {
  color: #00e5ff;
  font-size: 0.82rem;
  font-weight: 800;
}

.proposition-title {
  margin-top: 10px;
  font-weight: 800;
  line-height: 1.5;
}

.proposition-thesis {
  margin-top: 10px;
  color: rgba(231, 236, 255, 0.76);
  line-height: 1.65;
}

.data-card h3 {
  font-size: 1.05rem;
  margin-bottom: 14px;
}

.flow-list,
.principle-list {
  display: grid;
  gap: 10px;
}

.flow-row,
.principle-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.flow-label {
  font-weight: 700;
}

.flow-note {
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.9rem;
  line-height: 1.55;
}

.asset-list {
  display: grid;
  gap: 10px;
}

.asset-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.asset-name {
  font-weight: 700;
}

.asset-meta {
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.9rem;
  margin-top: 4px;
}

.asset-risk {
  color: #ffc468;
  font-weight: 700;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.chip {
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}

.strategy-name {
  font-size: 1.05rem;
  font-weight: 800;
}

.strategy-line {
  margin-top: 8px;
  color: rgba(231, 236, 255, 0.72);
}

.strategy-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0;
}

.strategy-meta span {
  padding: 6px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}

.strategy-guide {
  color: rgba(231, 236, 255, 0.74);
  line-height: 1.7;
}

.callout {
  margin-top: 16px;
  padding: 16px 18px;
  color: #00e5ff;
  line-height: 1.7;
}

@media (max-width: 1100px) {
  .hero-grid,
  .layer-grid,
  .proposition-grid,
  .data-grid,
  .strategy-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 720px) {
  .wealth-page {
    padding: 16px;
  }
}
</style>
