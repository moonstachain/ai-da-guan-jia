<template>
  <section class="card heavy-top-gold not-found">
    <p class="eyebrow mono">404</p>
    <h1>页面未找到</h1>
    <p class="not-found-copy">请返回家长入口重新选择孩子，或者切换到已存在的页面。</p>
    <router-link to="/" class="back-link">返回选人器 →</router-link>
  </section>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.not-found-copy {
  color: var(--dim);
  line-height: 1.8;
}

.back-link {
  color: var(--gold);
  font-family: 'Space Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  text-decoration: none;
}
</style>

