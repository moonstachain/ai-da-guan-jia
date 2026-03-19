import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import StrategicTaskView from '../views/StrategicTaskView.vue'
import WealthPhilosophyView from '../views/WealthPhilosophyView.vue'
import WealthPastPresentView from '../views/WealthPastPresentView.vue'
import WealthEastWestView from '../views/WealthEastWestView.vue'
import WealthVirtualRealView from '../views/WealthVirtualRealView.vue'
import QuantPanoramaView from '../views/QuantPanoramaView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  },
  {
    path: '/strategic-tasks',
    name: 'StrategicTasks',
    component: StrategicTaskView
  },
  {
    path: '/wealth-philosophy',
    name: 'WealthPhilosophy',
    component: WealthPhilosophyView
  },
  {
    path: '/wealth-philosophy/past-present',
    name: 'WealthPastPresent',
    component: WealthPastPresentView
  },
  {
    path: '/wealth-philosophy/east-west',
    name: 'WealthEastWest',
    component: WealthEastWestView
  },
  {
    path: '/wealth-philosophy/virtual-real',
    name: 'WealthVirtualReal',
    component: WealthVirtualRealView
  },
  {
    path: '/wealth-philosophy/virtual-real/quant-panorama',
    name: 'QuantPanorama',
    component: QuantPanoramaView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
