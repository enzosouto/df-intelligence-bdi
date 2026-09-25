<script setup lang="ts">
/**
 * Ir para uma região pelo nome.
 *
 * `<select>` nativo de propósito: no celular ele abre o seletor do sistema
 * (roda no iOS, lista no Android), com rolagem, busca por letra e alvos do
 * tamanho certo — tudo o que um mapa com 35 polígonos, alguns de 3 mm na tela,
 * não consegue oferecer ao dedo.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{ regions: { id: string; name: string }[]; current?: string | null; label?: string }>(),
  { current: null, label: 'Ir para uma região' },
)

const router = useRouter()
const sorted = computed(() =>
  [...props.regions].sort((a, b) => a.name.localeCompare(b.name, 'pt-BR')),
)

function go(event: Event) {
  const id = (event.target as HTMLSelectElement).value
  if (id && id !== props.current) router.push(`/regiao/${id}`)
}
</script>

<template>
  <label class="relative block">
    <span class="sr-only">{{ label }}</span>
    <select
      class="h-11 w-full appearance-none border border-line bg-elevated pl-3 pr-10 font-mono
             text-[12px] uppercase tracking-[0.08em] text-ink focus:border-accent focus:outline-none"
      :value="current ?? ''"
      @change="go"
    >
      <option value="" disabled>{{ label }}</option>
      <option v-for="region in sorted" :key="region.id" :value="region.id">{{ region.name }}</option>
    </select>
    <svg
      viewBox="0 0 24 24"
      class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-accent"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  </label>
</template>
