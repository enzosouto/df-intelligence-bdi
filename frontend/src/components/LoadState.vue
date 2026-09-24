<script setup lang="ts">
defineProps<{ loading: boolean; error: string | null; empty?: boolean }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="loading" class="space-y-3" role="status" aria-live="polite">
    <div class="skeleton h-4 w-2/5" />
    <div class="skeleton h-40 w-full" />
    <span class="sr-only">Carregando dados</span>
  </div>

  <div
    v-else-if="error"
    class="rounded-xl border border-security/30 bg-security/[0.06] px-4 py-3 text-sm text-security"
  >
    <p class="font-medium">Não foi possível carregar os dados.</p>
    <p class="mt-1 text-xs opacity-80">{{ error }}</p>
    <button
      type="button"
      class="mt-3 rounded-lg border border-security/40 px-3 py-1.5 text-xs transition-colors hover:bg-security/10"
      @click="$emit('retry')"
    >
      Tentar de novo
    </button>
  </div>

  <p v-else-if="empty" class="py-8 text-center text-sm text-faint">
    Nenhum dado publicado para este recorte.
  </p>

  <slot v-else />
</template>
