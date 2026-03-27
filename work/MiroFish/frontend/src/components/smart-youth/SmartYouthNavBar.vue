<template>
  <header class="smart-youth-nav card">
    <div class="nav-brand-block">
      <router-link to="/" class="brand-link">
        <span class="brand mono">AI造物</span>
        <span class="brand-note">RAYGEN INNOVATIONS × 智能少年</span>
      </router-link>
    </div>

    <label class="nav-selector">
      <span class="selector-label mono">CHILD</span>
      <select :value="activeStudentId" @change="handleStudentChange">
        <option value="">选择你的孩子</option>
        <option
          v-for="student in students"
          :key="student.孩子ID"
          :value="student.孩子ID"
        >
          {{ optionLabel(student) }}
        </option>
      </select>
    </label>

    <nav class="nav-tabs" aria-label="Smart Youth pages">
      <router-link
        v-for="tab in tabs.filter(tab => !tab.comingSoon)"
        :key="tab.key"
        :to="tabTo(tab)"
        class="nav-tab"
        :class="{ active: activeTabName === tab.routeName }"
      >
        {{ tab.label }}
      </router-link>

      <button
        v-for="tab in tabs.filter(tab => tab.comingSoon)"
        :key="tab.key"
        type="button"
        class="nav-tab nav-tab-coming-soon"
        :title="tab.hint || '即将上线'"
        disabled
      >
        <span>{{ tab.label }}</span>
        <span class="tab-coming-soon-label">{{ tab.hint || '即将上线' }}</span>
      </button>
    </nav>

    <div class="nav-source mono" :class="sourceClass">
      {{ sourceLabel }}
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { smartYouthTabs } from '../../data/smartYouthTheme'

const props = defineProps({
  students: {
    type: Array,
    default: () => []
  },
  activeStudentId: {
    type: String,
    default: ''
  },
  activeTabName: {
    type: String,
    default: ''
  },
  source: {
    type: String,
    default: 'fallback'
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['change-student'])

const sourceLabel = computed(() => {
  if (props.loading) {
    return '加载中'
  }
  return props.source === 'feishu' ? '飞书实时' : '本地回退'
})

const sourceClass = computed(() => (props.source === 'feishu' ? 'source-feishu' : 'source-fallback'))

const tabTo = (tab) => {
  if (!props.activeStudentId) {
    return { name: 'SmartYouthSelector' }
  }
  return { name: tab.routeName, params: { studentId: props.activeStudentId } }
}

const handleStudentChange = (event) => {
  emit('change-student', event.target.value)
}

const optionLabel = (student) => {
  const age = student?.当前年龄 ? `${student.当前年龄}岁` : ''
  const gate = student?.gateLabel && student?.gateName ? `${student.gateLabel} ${student.gateName}` : ''
  const gateCode = student?.gateCodeLabel || student?.gateCode ? `#${student.gateCodeLabel || student.gateCode}` : ''
  return [student?.姓名, age, gate, gateCode].filter(Boolean).join(' · ')
}

const tabs = smartYouthTabs
</script>

<style scoped>
.smart-youth-nav {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) minmax(220px, 1fr) minmax(280px, 1.2fr) auto;
  gap: 16px;
  align-items: center;
}

.brand-link {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: inherit;
  text-decoration: none;
}

.brand {
  color: var(--gold);
  font-size: 18px;
  letter-spacing: 0.18em;
}

.brand-note {
  color: var(--dim);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.nav-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-label {
  color: var(--dim);
  font-size: 11px;
  letter-spacing: 0.15em;
}

select {
  width: 100%;
  border: 1px solid var(--rule-light);
  background: var(--abyss);
  color: var(--paper);
  padding: 10px 12px;
  font: inherit;
  outline: none;
}

.nav-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.nav-tab {
  padding: 8px 12px;
  border-bottom: 2px solid transparent;
  color: rgba(245, 240, 232, 0.72);
  text-decoration: none;
  font-family: 'Space Mono', monospace;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.12em;
}

.nav-tab.active {
  color: var(--paper);
  border-bottom-color: var(--gold);
}

.nav-tab-coming-soon {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: not-allowed;
}

.nav-tab-coming-soon:disabled {
  opacity: 0.65;
}

.tab-coming-soon-label {
  color: var(--spark);
  font-size: 9px;
  letter-spacing: 0.08em;
}

.nav-source {
  justify-self: end;
  padding: 6px 10px;
  border: 1px solid var(--rule-light);
  font-size: 11px;
  letter-spacing: 0.1em;
}

.source-feishu {
  color: var(--gold);
}

.source-fallback {
  color: var(--dim);
}

@media (max-width: 1100px) {
  .smart-youth-nav {
    grid-template-columns: 1fr;
  }

  .nav-source {
    justify-self: start;
  }
}
</style>
