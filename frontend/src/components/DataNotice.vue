<script setup lang="ts">
/**
 * Aviso metodológico. Existe para que nenhuma ressalva importante — fonte não
 * governamental, dado de infraestrutura lido como produção, lacuna de
 * publicação — fique só na documentação.
 */
withDefaults(defineProps<{ tone?: 'info' | 'warn' }>(), { tone: 'info' })
</script>

<template>
  <p
    class="flex gap-2.5 rounded-xl border px-3.5 py-2.5 text-xs leading-relaxed"
    :class="
      tone === 'warn'
        ? 'border-warn/25 bg-warn/[0.06] text-warn/90'
        : 'border-line bg-elevated/60 text-muted'
    "
  >
    <svg viewBox="0 0 16 16" class="mt-[1px] h-3.5 w-3.5 shrink-0" fill="currentColor" aria-hidden="true">
      <path
        d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3a.9.9 0 110 1.8A.9.9 0 018 4zm1 8H7V7h2v5z"
      />
    </svg>
    <span><slot /></span>
  </p>
</template>
