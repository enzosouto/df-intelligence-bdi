<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { api } from '@/api'
import { dateTime } from '@/format'

const route = useRoute()
const lastUpdate = ref<string | null>(null)

const NAV = [
  { to: '/', label: 'Dashboard' },
  { to: '/insights', label: 'Insights' },
  { to: '/fontes', label: 'Fontes & Qualidade' },
]

onMounted(async () => {
  try {
    lastUpdate.value = (await api.overview()).data_last_updated_at
  } catch {
    lastUpdate.value = null
  }
})
</script>

<template>
  <div class="min-h-screen">
    <header class="sticky top-0 z-40 border-b border-line bg-base/80 backdrop-blur-xl">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4 sm:px-8">
        <RouterLink to="/" class="group flex items-center gap-3">
          <span
            class="grid h-9 w-9 place-items-center rounded-xl border border-population/30
                   bg-population/10 font-display text-sm font-bold text-population
                   transition-shadow group-hover:shadow-glow"
            aria-hidden="true"
          >
            DF
          </span>
          <span class="leading-tight">
            <span class="block font-display text-[15px] font-bold tracking-tight text-ink">
              DF INTELLIGENCE
            </span>
            <span class="block text-[11px] text-faint">Brasília através dos dados.</span>
          </span>
        </RouterLink>

        <nav class="flex items-center gap-1" aria-label="Navegação principal">
          <RouterLink
            v-for="item in NAV"
            :key="item.to"
            :to="item.to"
            class="rounded-lg px-3 py-1.5 text-sm transition-colors"
            :class="
              route.path === item.to
                ? 'bg-elevated text-ink'
                : 'text-muted hover:bg-elevated/60 hover:text-ink'
            "
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="ml-auto flex items-center gap-3">
          <span v-if="lastUpdate" class="chip">
            <span class="h-1.5 w-1.5 rounded-full bg-population" aria-hidden="true" />
            atualizado {{ dateTime(lastUpdate) }}
          </span>
          <a
            href="/docs"
            target="_blank"
            rel="noopener"
            class="hidden rounded-lg border border-line px-3 py-1.5 text-xs text-muted
                   transition-colors hover:border-population/40 hover:text-ink sm:block"
          >
            API
          </a>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-10">
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
        class="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-8 text-xs text-faint sm:flex-row
               sm:items-center sm:justify-between sm:px-8"
      >
        <p>
          Dados públicos de IBGE, IBRAM/ONDA-DF, SSP-DF, CNES/Ministério da Saúde, SEEDF/Inep, IDE-DF e Open-Meteo.
        </p>
        <p>
          Projeto independente, sem vínculo com o Governo do Distrito Federal.
        </p>
      </div>
    </footer>
  </div>
</template>
