<template>
  <div class="wealth-page wealth-overview">
    <div class="glow glow-one"></div>
    <div class="glow glow-two"></div>

    <header class="page-header">
      <div class="brand-row">
        <router-link to="/" class="brand">MIROFISH</router-link>
        <span class="crumb">/ 认知入口</span>
      </div>

      <div class="nav-row">
        <router-link to="/strategic-tasks" class="nav-pill">战略任务</router-link>
        <router-link to="/wealth-philosophy" class="nav-pill active">财富三观</router-link>
      </div>
    </header>

    <section class="hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">Wealth Philosophy · Why Layer</p>
        <h1>{{ overview.title }}</h1>
        <p class="quote">{{ overview.quote }}</p>
        <p class="summary">{{ overview.summary }}</p>

        <div class="hero-chips">
          <span v-for="item in wealthPhilosophyLoop" :key="item.label" class="chip">
            <strong>{{ item.label }}</strong>
            <span>{{ item.note }}</span>
          </span>
        </div>
      </div>

      <aside class="hero-panel">
        <div class="panel-title">认知层概览</div>
        <div class="stat-grid">
          <article v-for="stat in overview.stats" :key="stat.label" class="stat-card">
            <div class="stat-label">{{ stat.label }}</div>
            <div class="stat-value">{{ stat.value }}</div>
          </article>
        </div>
        <div class="bridge-note">
          <span class="bridge-label">数据验证关系</span>
          <span>Why 框架 → What / How 证据层</span>
        </div>
      </aside>
    </section>

    <section class="track-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">三条主线</p>
          <h2>认知阶梯从这里进入</h2>
        </div>
        <p class="section-copy">每一张卡片都可以直接进入子页面，再回到资产和策略层验证。</p>
      </div>

      <div class="track-grid">
        <router-link
          v-for="track in tracks"
          :key="track.key"
          :to="track.route"
          class="track-card"
          :class="track.key"
        >
          <div class="track-topline">
            <span class="track-label">{{ track.label }}</span>
            <span class="track-link">进入 →</span>
          </div>
          <h3>{{ track.model_name }}</h3>
          <p class="track-quote">{{ track.quote }}</p>
          <p class="track-bridge">{{ track.bridge }}</p>

          <div class="track-kpis">
            <span v-for="kpi in track.kpis" :key="kpi.label" class="track-kpi">
              <strong>{{ kpi.value }}</strong>
              <small>{{ kpi.label }}</small>
            </span>
          </div>

          <div class="track-preview">
            <span v-for="layer in track.layers.slice(0, 2)" :key="layer.name" class="layer-preview">
              {{ layer.name }}
            </span>
          </div>
        </router-link>
      </div>
    </section>

    <section class="bridge-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">认知映射</p>
          <h2>与现有数据页面的关系</h2>
        </div>
        <p class="section-copy">这里不是替代数据页，而是提供进入数据页之前的解释框架。</p>
      </div>

      <div class="bridge-grid">
        <article v-for="page in bridgePages" :key="page.title" class="bridge-card">
          <div class="bridge-title">{{ page.title }}</div>
          <div class="bridge-note">{{ page.note }}</div>
        </article>
      </div>
    </section>

    <section class="signal-section">
      <div class="section-head">
        <div>
          <p class="section-kicker">验证信号</p>
          <h2>从认知到数据的三组桥接信号</h2>
        </div>
      </div>

      <div class="signal-grid">
        <article v-for="signal in comparativeSignals" :key="signal.label" class="signal-card">
          <div class="signal-label">{{ signal.label }}</div>
          <div class="signal-row">
            <span>{{ signal.left }}</span>
            <span class="signal-arrow">→</span>
            <span>{{ signal.right }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import {
  wealthPhilosophyBridgePages,
  wealthPhilosophyComparativeSignals,
  wealthPhilosophyLoop,
  wealthPhilosophyOverview,
  wealthPhilosophyTracks
} from '../data/wealthPhilosophy'

const overview = wealthPhilosophyOverview
const tracks = wealthPhilosophyTracks.map(track => ({
  ...track,
  route: track.key === 'past-present'
    ? '/wealth-philosophy/past-present'
    : track.key === 'east-west'
      ? '/wealth-philosophy/east-west'
      : '/wealth-philosophy/virtual-real'
}))
const bridgePages = wealthPhilosophyBridgePages
const comparativeSignals = wealthPhilosophyComparativeSignals
</script>

<style scoped>
.wealth-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  padding: 28px;
  color: #f5f7ff;
  background:
    radial-gradient(circle at top left, rgba(255, 196, 104, 0.22), transparent 28%),
    radial-gradient(circle at top right, rgba(0, 229, 255, 0.18), transparent 26%),
    linear-gradient(180deg, #070b15 0%, #090f1e 38%, #0d1326 100%);
}

.glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(24px);
  opacity: 0.72;
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
.track-section,
.bridge-section,
.signal-section {
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
  gap: 10px;
  flex-wrap: wrap;
}

.nav-pill,
.track-card,
.hero-panel,
.bridge-card,
.signal-card {
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

.nav-pill.active {
  color: #08111f;
  background: linear-gradient(135deg, #ffc468 0%, #69f0ae 100%);
  border-color: transparent;
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.9fr);
  gap: 18px;
  align-items: stretch;
}

.hero-copy,
.hero-panel,
.track-card,
.bridge-card,
.signal-card {
  border-radius: 22px;
}

.hero-copy {
  padding: 26px 28px 28px;
}

.eyebrow,
.section-kicker,
.panel-title,
.bridge-label,
.track-label {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.74rem;
  color: rgba(200, 214, 255, 0.68);
}

.hero-copy h1 {
  margin: 12px 0 10px;
  font-size: clamp(2.5rem, 5vw, 4.6rem);
  line-height: 1;
  letter-spacing: -0.06em;
}

.quote {
  font-size: 1.1rem;
  line-height: 1.8;
  color: #ffdca8;
  max-width: 860px;
}

.summary {
  margin-top: 16px;
  max-width: 820px;
  color: rgba(231, 236, 255, 0.76);
  line-height: 1.85;
}

.hero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.chip {
  display: grid;
  gap: 4px;
  min-width: 160px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.chip strong {
  font-size: 0.92rem;
}

.chip span {
  color: rgba(231, 236, 255, 0.68);
  font-size: 0.84rem;
  line-height: 1.45;
}

.hero-panel {
  padding: 22px;
}

.panel-title {
  margin-bottom: 16px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  min-height: 104px;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02));
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.stat-label {
  color: rgba(202, 214, 255, 0.68);
  font-size: 0.82rem;
}

.stat-value {
  margin-top: 10px;
  font-size: 1.8rem;
  font-weight: 800;
}

.bridge-note {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: rgba(231, 236, 255, 0.74);
  line-height: 1.6;
}

.track-section,
.bridge-section,
.signal-section {
  margin-top: 22px;
  padding: 22px;
  border-radius: 24px;
  background: rgba(8, 12, 24, 0.66);
  border: 1px solid rgba(155, 176, 255, 0.12);
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.section-head h2 {
  margin-top: 8px;
  font-size: 1.3rem;
}

.section-copy {
  max-width: 540px;
  color: rgba(231, 236, 255, 0.66);
  line-height: 1.6;
}

.track-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.track-card {
  display: block;
  color: inherit;
  text-decoration: none;
  padding: 20px;
  min-height: 246px;
  transition: transform 180ms ease, border-color 180ms ease;
}

.track-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.22);
}

.track-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.track-link {
  color: #ffdca8;
}

.track-card h3 {
  font-size: 1.18rem;
  line-height: 1.35;
  margin-bottom: 12px;
}

.track-quote {
  color: #ffdca8;
  line-height: 1.7;
  margin-bottom: 10px;
}

.track-bridge {
  color: rgba(231, 236, 255, 0.7);
  line-height: 1.65;
}

.track-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.track-kpi {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
}

.track-kpi strong {
  font-size: 1rem;
}

.track-kpi small {
  color: rgba(231, 236, 255, 0.64);
}

.track-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.layer-preview {
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(243, 246, 255, 0.9);
  font-size: 0.8rem;
}

.bridge-grid,
.signal-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.bridge-card,
.signal-card {
  padding: 18px;
}

.bridge-title,
.signal-label {
  font-weight: 700;
}

.bridge-note {
  margin-top: 10px;
  color: rgba(231, 236, 255, 0.68);
  line-height: 1.6;
}

.signal-row {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #ffdca8;
  font-weight: 700;
}

.signal-arrow {
  color: rgba(231, 236, 255, 0.5);
}

.past-present .track-link,
.past-present .track-quote,
.past-present .track-kpi strong {
  color: #ffc468;
}

.east-west .track-link,
.east-west .track-quote,
.east-west .track-kpi strong {
  color: #69f0ae;
}

.virtual-real .track-link,
.virtual-real .track-quote,
.virtual-real .track-kpi strong {
  color: #00e5ff;
}

@media (max-width: 1100px) {
  .hero-grid,
  .track-grid,
  .bridge-grid,
  .signal-grid {
    grid-template-columns: 1fr;
  }

  .section-head {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .wealth-page {
    padding: 16px;
  }

  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .stat-grid,
  .track-kpis {
    grid-template-columns: 1fr;
  }
}
</style>
