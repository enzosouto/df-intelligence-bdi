<script setup lang="ts">
defineProps<{
  label: string
  value: string
  hint?: string
  accent?: string
  loading?: boolean
}>()
</script>

<template>
  <div class="card card-pad animate-fade-up">
    <p class="label">{{ label }}</p>
    <div v-if="loading" class="skeleton mt-3 h-9 w-28" />
    <p v-else class="metric mt-2" :style="accent ? { color: accent } : undefined">{{ value }}</p>
    <p v-if="hint" class="mt-2 text-xs leading-relaxed text-faint">{{ hint }}</p>
  </div>
</template>
