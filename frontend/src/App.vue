<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { api, apiUrl, apiWaking } from '@/api'
import { dateTime, shortDate } from '@/format'
import { bindPointer, hasFinePointer, prefersReducedMotion } from '@/motion'
import AppLoader from '@/components/AppLoader.vue'
import BackgroundField from '@/components/BackgroundField.vue'
import Malha from '@/components/Malha.vue'
import Reticle from '@/components/Reticle.vue'
import type { Coverage } from '@/types'

const route = useRoute()
const router = useRouter()
const lastUpdate = ref<string | null>(null)
const coverage = ref<Coverage[]>([])

const booting = ref(true)
const booted = ref(false)
const withReticle = hasFinePointer() && !prefersReducedMotion()

/** Os passos do loader são as requisições reais do boot, com status real. */
const steps = reactive<{ label: string; status: 'pending' | 'ok' | 'fail' }[]>([
  { label: '/api/overview', status: 'pending' },
  { label: '/api/coverage', status: 'pending' },
])

/**
 * Três destinos, os mesmos no topo (desktop) e na barra de baixo (celular).
 * `icon` é o traço de um SVG 24×24 — desenhado em linha reta e canto vivo,
 * como o resto da interface.
 */
const NAV = [
  { to: '/', label: 'Painel', long: 'Dashboard', icon: 'M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z' },
  { to: '/insights', label: 'Insights', long: 'Insights', icon: 'M4 20h16M6 16l4-5 3 3 5-7' },
  { to: '/fontes', label: 'Fontes', long: 'Fontes', icon: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3' },
]

/** A aba de uma página de região é o Painel: é de lá que se chega nela. */
function isActive(to: string): boolean {
  if (to === '/') return route.path === '/' || route.path.startsWith('/regiao/')
  return route.path.startsWith(to)
}

const docsUrl = apiUrl('/docs')

onMounted(async () => {
  bindPointer()
  // Falha aqui não pode derrubar o cabeçalho: o miolo da página tem o seu
  // próprio estado de erro, com botão de tentar de novo.
  const [overview, coverageList] = await Promise.allSettled([api.overview(), api.coverage()])

  if (overview.status === 'fulfilled') {
    lastUpdate.value = overview.value.data_last_updated_at
    steps[0].status = 'ok'
  } else {
    steps[0].status = 'fail'
  }

  if (coverageList.status === 'fulfilled') {
    coverage.value = coverageList.value
    steps[1].status = 'ok'
  } else {
    steps[1].status = 'fail'
  }

  booted.value = true
})
</script>

<template>
  <BackgroundField />
  <Reticle v-if="withReticle" />

  <AppLoader v-if="booting" :steps="steps" :ready="booted" @done="booting = false" />

  <a
    href="#conteudo"
    class="sr-only z-[60] bg-accent px-4 py-3 font-mono text-xs uppercase text-night focus:not-sr-only
           focus:fixed focus:left-4 focus:top-4"
  >
    Pular para o conteúdo
  </a>

  <!-- Aviso de API acordando: a primeira visita depois de um tempo parado
       espera o servidor gratuito ligar. Explicar a espera evita que a pessoa
       ache que o site quebrou e vá embora. -->
  <Transition
    enter-active-class="transition duration-200"
    enter-from-class="opacity-0 -translate-y-2"
    leave-active-class="transition duration-200"
    leave-to-class="opacity-0"
  >
    <div
      v-if="apiWaking && !booting"
      role="status"
      class="fixed inset-x-4 top-[calc(4rem+env(safe-area-inset-top))] z-[210] mx-auto max-w-md border
             border-warn/50 bg-elevated px-4 py-3 font-mono text-[11px] leading-relaxed text-muted sm:top-6"
    >
      <span class="mr-2 inline-block h-1.5 w-1.5 animate-blink bg-warn align-middle" aria-hidden="true" />
      <span class="text-warn">Ligando o servidor.</span>
      A API gratuita dorme depois de 15 min sem acesso e leva até 1 minuto para acordar.
    </div>
  </Transition>

  <div class="min-h-screen">
    <header class="safe-top sticky top-0 z-40 border-b border-line bg-night/90 backdrop-blur-sm">
      <div class="mx-auto max-w-[88rem] px-4 sm:px-8">
        <div class="flex h-14 items-center gap-x-6 sm:h-auto sm:py-4">
          <RouterLink to="/" class="flex min-h-[44px] items-center gap-2.5 sm:min-h-0 sm:gap-3">
            <span
              class="font-display text-[1.25rem] font-bold leading-none tracking-tight text-ink sm:text-[1.35rem]"
              style="font-stretch: 118%"
            >
              DF
            </span>
            <span class="h-4 w-px bg-line" aria-hidden="true" />
            <span class="font-mono text-[11px] uppercase tracking-plan text-muted">
              Intelligence
            </span>
          </RouterLink>

          <!-- Desktop: navegação no topo. No celular ela desce para a barra de
               baixo, onde o polegar alcança. -->
          <nav class="hidden items-center gap-5 sm:flex" aria-label="Navegação principal">
            <RouterLink
              v-for="item in NAV"
              :key="item.to"
              :to="item.to"
              class="border-b-2 py-1 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors"
              :class="isActive(item.to) ? 'border-accent text-ink' : 'border-transparent text-faint hover:text-muted'"
              :aria-current="isActive(item.to) ? 'page' : undefined"
            >
              {{ item.long }}
            </RouterLink>
          </nav>

          <div class="ml-auto flex items-center gap-4">
            <span
              v-if="lastUpdate"
              class="font-mono text-[10px] uppercase tracking-[0.12em] text-faint"
              :title="`Dados atualizados em ${dateTime(lastUpdate)}`"
            >
              <span class="hidden lg:inline">Atualizado {{ dateTime(lastUpdate) }}</span>
              <span class="inline-flex items-center gap-1.5 lg:hidden">
                <span class="h-1.5 w-1.5 bg-education" aria-hidden="true" />
                {{ shortDate(lastUpdate) }}
              </span>
            </span>
            <a
              :href="docsUrl"
              target="_blank"
              rel="noopener"
              class="hidden border border-line px-2.5 py-1 font-mono text-[10px] uppercase
                     tracking-[0.12em] text-faint transition-colors hover:border-accent
                     hover:text-ink sm:inline-block"
            >
              API
            </a>
          </div>
        </div>

        <!-- A malha: cobertura das 35 RAs. No celular os 35 módulos teriam 9px
             cada — alvo de toque impossível e ruído no cabeçalho fixo. Ela
             aparece a partir do tablet. -->
        <div v-if="coverage.length" class="hidden items-center gap-4 pb-3 sm:flex">
          <span class="label shrink-0">Cobertura</span>
          <Malha :coverage="coverage" @select="router.push(`/regiao/${$event}`)" />
          <span class="label ml-auto hidden shrink-0 text-right md:block">35 RA · 6 domínios</span>
        </div>
      </div>
    </header>

    <main
      id="conteudo"
      class="mx-auto max-w-[88rem] px-4 pb-10 pt-6 sm:px-8 sm:py-12"
    >
      <RouterView v-slot="{ Component }">
        <Transition
          mode="out-in"
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="opacity-0 translate-y-2"
          leave-active-class="transition duration-150 ease-in"
          leave-to-class="opacity-0"
        >
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

    <footer class="border-t border-line pb-[calc(4.5rem+env(safe-area-inset-bottom))] sm:pb-0">
      <div
        class="mx-auto flex max-w-[88rem] flex-col gap-3 px-4 py-8 font-mono text-[10px]
               uppercase leading-relaxed tracking-[0.1em] text-faint sm:flex-row
               sm:items-center sm:justify-between sm:gap-2 sm:px-8"
      >
        <p>IBGE · IBRAM/ONDA-DF · SSP-DF · CNES · SEEDF/Inep · IDE-DF · Open-Meteo</p>
        <p>
          <span class="text-accent">Enzo Souto</span> · Analista de dados
          <span class="text-faint"> · Projeto independente, sem vínculo com o GDF</span>
        </p>
        <a :href="docsUrl" target="_blank" rel="noopener" class="link-underline py-3 sm:hidden">
          Documentação da API
        </a>
      </div>
    </footer>

    <!-- Barra de abas do celular: fixa embaixo, 56px + a área da barra de
         gestos. Ícone + rótulo (rótulo sozinho some, ícone sozinho é enigma). -->
    <nav
      class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-night/95 backdrop-blur-sm sm:hidden"
      style="padding-bottom: env(safe-area-inset-bottom)"
      aria-label="Navegação principal"
    >
      <ul class="grid h-14 grid-cols-3">
        <li v-for="item in NAV" :key="item.to">
          <RouterLink
            :to="item.to"
            class="relative flex h-full flex-col items-center justify-center gap-1 font-mono
                   text-[10px] uppercase tracking-[0.12em] transition-colors"
            :class="isActive(item.to) ? 'text-ink' : 'text-faint'"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            <span
              class="absolute inset-x-6 top-0 h-[2px] transition-colors"
              :class="isActive(item.to) ? 'bg-accent' : 'bg-transparent'"
              aria-hidden="true"
            />
            <svg
              viewBox="0 0 24 24"
              class="h-5 w-5"
              fill="none"
              :stroke="isActive(item.to) ? '#FF006A' : 'currentColor'"
              stroke-width="1.6"
              stroke-linejoin="miter"
              aria-hidden="true"
            >
              <path :d="item.icon" />
            </svg>
            {{ item.label }}
          </RouterLink>
        </li>
      </ul>
    </nav>
  </div>
</template>
