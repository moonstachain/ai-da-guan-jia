<template>
  <div class="wealth-page track-page past-present">
    <header class="page-header">
      <div class="brand-row">
        <router-link to="/home" class="brand">MIROFISH</router-link>
        <span class="crumb">/ 财富三观 · 古今之变</span>
      </div>
      <div class="nav-row">
        <router-link to="/wealth-philosophy" class="nav-pill">总览</router-link>
        <router-link to="/wealth-philosophy/past-present" class="nav-pill active">古今之变</router-link>
        <router-link to="/wealth-philosophy/east-west" class="nav-pill">东西之变</router-link>
        <router-link to="/wealth-philosophy/virtual-real" class="nav-pill">虚实之变</router-link>
      </div>
    </header>

    <section class="hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">Past / Present</p>
        <h1>{{ track.model_name }}</h1>
        <p class="quote">{{ track.quote }}</p>
        <p class="summary">{{ track.bridge }}</p>
      </div>

      <aside class="hero-panel">
        <div class="panel-title">页面目标</div>
        <p class="panel-copy">
          用四层推演把“法币坍塌 → 坎蒂隆效应 → 确定性溢价 → 黄金锚点”连成一条可验证的认知链。
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
          <p class="section-kicker">四层推演</p>
          <h2>从货币信用走向资产锚点</h2>
        </div>
      </div>

      <div class="layer-grid">
        <article v-for="layer in track.layers" :key="layer.name" class="layer-card">
          <div class="layer-index">{{ layer.name }}</div>
          <p class="layer-thesis">{{ layer.thesis }}</p>
          <p class="layer-evidence">{{ layer.evidence }}</p>
          <div class="layer-chart">{{ layer.chart }}</div>
        </article>
      </div>
    </section>

    <section class="proposition-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">核心命题</p>
          <h2>这一层到底在说什么</h2>
        </div>
      </div>

      <div class="proposition-grid">
        <article v-for="item in propositions.slice(0, 6)" :key="item.proposition_id" class="proposition-card">
          <div class="proposition-id">{{ item.proposition_id }}</div>
          <div class="proposition-title">{{ item.title }}</div>
          <p class="proposition-thesis">{{ item.thesis }}</p>
          <p class="proposition-evidence">{{ item.evidence_chain }}</p>
        </article>
      </div>
    </section>

    <section class="data-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">数据联动</p>
          <h2>证据链、事件锚点和资产选择</h2>
        </div>
      </div>

      <div class="data-grid">
        <article class="data-card timeline-card">
          <h3>历史锚点</h3>
          <div class="timeline">
            <div v-for="item in track.timeline" :key="item.year" class="timeline-item">
              <div class="timeline-year">{{ item.year }}</div>
              <div>
                <div class="timeline-title">{{ item.title }}</div>
                <div class="timeline-note">{{ item.note }}</div>
              </div>
            </div>
          </div>
        </article>

        <article class="data-card asset-card">
          <h3>资产审美选取</h3>
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

        <article class="data-card signal-card">
          <h3>相关原则</h3>
          <div class="chip-list">
            <span v-for="principle in principles" :key="principle" class="chip">{{ principle }}</span>
          </div>
          <div class="valuation-list">
            <div v-for="item in track.valuationNotes" :key="item.label" class="valuation-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="strategy-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">行动指南</p>
          <h2>策略层的直接输出</h2>
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

const track = wealthPhilosophyTracks.find(item => item.key === 'past-present')
const assets = getAssetsForTrack('past-present').slice(0, 10)
const propositions = getPropositionsForTrack('past-present')
const strategies = getStrategiesForTrack('past-present')
const principles = track.principles
</script>

<style scoped>
.wealth-page {
  min-height: 100vh;
  padding: 28px;
  color: #f4f7ff;
  background:
    radial-gradient(circle at top left, rgba(255, 196, 104, 0.18), transparent 24%),
    radial-gradient(circle at bottom right, rgba(0, 229, 255, 0.1), transparent 22%),
    linear-gradient(180deg, #06090f 0%, #0b1020 55%, #11172a 100%);
}

.page-header,
.hero-grid,
.layer-section,
.data-section,
.strategy-section {
  position: relative;
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
.callout {
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
  background: linear-gradient(135deg, #ffc468 0%, #69f0ae 100%);
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
.callout {
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
  color: #ffc468;
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
  grid-template-columns: 1fr;
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
  color: #ffc468;
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

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin-top: 8px;
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
.strategy-card {
  padding: 18px;
}

.proposition-card {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
}

.proposition-id {
  color: #ffc468;
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

.proposition-evidence {
  margin-top: 12px;
  color: rgba(231, 236, 255, 0.6);
  line-height: 1.6;
}

.layer-index {
  font-weight: 800;
  color: #ffc468;
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
  color: #69f0ae;
}

.data-card h3 {
  font-size: 1.05rem;
  margin-bottom: 14px;
}

.timeline,
.asset-list,
.valuation-list {
  display: grid;
  gap: 10px;
}

.timeline-item,
.asset-row,
.valuation-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.timeline-year {
  font-weight: 800;
  color: #ffc468;
  min-width: 56px;
}

.timeline-title,
.asset-name {
  font-weight: 700;
}

.timeline-note,
.asset-meta {
  color: rgba(231, 236, 255, 0.66);
  font-size: 0.9rem;
  margin-top: 4px;
}

.asset-risk {
  color: #69f0ae;
  font-weight: 700;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.chip {
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: #f5f7ff;
}

.valuation-row {
  align-items: center;
}

.valuation-row strong {
  color: #ffc468;
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
  color: #ffdca8;
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
