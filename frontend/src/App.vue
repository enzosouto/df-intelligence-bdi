<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { dateTime } from '@/format'
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

const NAV = [
  { to: '/', label: 'Dashboard' },
  { to: '/insights', label: 'Insights' },
  { to: '/fontes', label: 'Fontes' },
]

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

  <div class="min-h-screen">
    <header class="sticky top-0 z-40 border-b border-line bg-night/90 backdrop-blur-sm">
      <div class="mx-auto max-w-[88rem] px-4 sm:px-8">
        <div class="flex flex-wrap items-center gap-x-6 gap-y-3 py-3 sm:py-4">
          <RouterLink to="/" class="flex items-baseline gap-2.5 sm:gap-3">
            <span
              class="font-display text-[1.2rem] font-bold leading-none tracking-tight text-ink sm:text-[1.35rem]"
              style="font-stretch: 118%"
            >
              DF
            </span>
            <span class="h-4 w-px self-center bg-line" aria-hidden="true" />
            <span class="font-mono text-[10px] uppercase tracking-plan text-muted sm:text-[11px]">
              Intelligence
            </span>
          </RouterLink>

          <nav class="flex items-center gap-4 sm:gap-5" aria-label="Navegação principal">
            <RouterLink
              v-for="item in NAV"
              :key="item.to"
              :to="item.to"
              class="border-b-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em]
                     transition-colors sm:text-[11px]"
              :class="
                route.path === item.to
                  ? 'border-accent text-ink'
                  : 'border-transparent text-faint hover:text-muted'
              "
            >
              {{ item.label }}
            </RouterLink>
          </nav>

          <div class="ml-auto flex items-center gap-4">
            <span
              v-if="lastUpdate"
              class="hidden font-mono text-[10px] uppercase tracking-[0.12em] text-faint lg:block"
            >
              Atualizado {{ dateTime(lastUpdate) }}
            </span>
            <a
              href="/docs"
              target="_blank"
              rel="noopener"
              class="border border-line px-2.5 py-1 font-mono text-[10px] uppercase
                     tracking-[0.12em] text-faint transition-colors hover:border-accent
                     hover:text-ink"
            >
              API
            </a>
          </div>
        </div>

        <!-- A malha: cobertura das 35 RAs, sempre à vista. -->
        <div v-if="coverage.length" class="flex items-center gap-3 pb-3 sm:gap-4">
          <span class="label hidden shrink-0 sm:block">Cobertura</span>
          <Malha :coverage="coverage" @select="router.push(`/regiao/${$event}`)" />
          <span class="label ml-auto hidden shrink-0 text-right md:block">35 RA · 6 domínios</span>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-[88rem] px-4 py-8 sm:px-8 sm:py-12">
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

    <footer class="border-t border-line">
      <div
        class="mx-auto flex max-w-[88rem] flex-col gap-2 px-4 py-8 font-mono text-[10px]
               uppercase leading-relaxed tracking-[0.1em] text-faint sm:flex-row
               sm:items-center sm:justify-between sm:px-8"
      >
        <p>IBGE · IBRAM/ONDA-DF · SSP-DF · CNES · SEEDF/Inep · IDE-DF · Open-Meteo</p>
        <p>
          <span class="text-accent">Enzo Souto</span> · Analista de dados
          <span class="text-faint"> · Projeto independente, sem vínculo com o GDF</span>
        </p>
      </div>
    </footer>
  </div>
</template>
