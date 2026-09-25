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
  // Voltar (gesto ou botão) devolve a rolagem onde estava — no celular, perder
  // o lugar numa página longa a cada "voltar" é o atrito mais comum. Âncora
  // (#seguranca) rola até a seção descontando o cabeçalho fixo.
  scrollBehavior: (to, _from, saved) => {
    if (saved) return saved
    if (to.hash) return { el: to.hash, top: 112, behavior: 'smooth' }
    return { top: 0 }
  },
})
