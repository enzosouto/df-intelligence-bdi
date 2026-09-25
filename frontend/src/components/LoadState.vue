<script setup lang="ts">
defineProps<{ loading: boolean; error: string | null; empty?: boolean }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="loading" class="space-y-3" role="status" aria-live="polite">
    <div class="skeleton h-3 w-2/5" />
    <div class="skeleton h-40 w-full" />
    <span class="sr-only">Carregando dados</span>
  </div>

  <div v-else-if="error" class="border border-security/40 bg-security/[0.07] p-5">
    <p class="label text-security">Falha ao carregar</p>
    <p class="mt-2 text-sm text-ink">A API não respondeu. Os dados não foram carregados.</p>
    <p class="mt-1 font-mono text-[11px] text-faint">{{ error }}</p>
    <button
      type="button"
      class="mt-4 border border-security/50 px-3 py-1.5 font-mono text-[10px] uppercase
             tracking-[0.12em] text-security transition-colors hover:bg-security/10"
      @click="$emit('retry')"
    >
      Tentar de novo
    </button>
  </div>

  <p v-else-if="empty" class="py-8 text-center font-mono text-xs uppercase tracking-[0.12em] text-faint">
    Nenhum dado publicado para este recorte
  </p>

  <slot v-else />
</template>
