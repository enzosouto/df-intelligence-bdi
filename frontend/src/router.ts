import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
  {
    path: '/regiao/:regionId',
    name: 'region',
    component: () => import('@/views/RegionView.vue'),
    props: true,
  },
  { path: '/insights', name: 'insights', component: () => import('@/views/InsightsView.vue') },
  { path: '/fontes', name: 'sources', component: () => import('@/views/SourcesView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})
