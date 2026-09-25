<script setup lang="ts">
/**
 * Ressalva metodológica. Existe para que nenhuma limitação importante — fonte
 * não governamental, infraestrutura lida como produção, lacuna de publicação —
 * fique só na documentação.
 *
 * Não é uma caixa de alerta: é uma nota de rodapé de desenho técnico, presa ao
 * gráfico por uma régua vertical. Lê-se junto com o dado, não por cima dele.
 */
withDefaults(defineProps<{ tone?: 'info' | 'warn' }>(), { tone: 'info' })
</script>

<template>
  <p
    class="border-l-2 pl-3 text-xs leading-relaxed"
    :class="tone === 'warn' ? 'border-warn text-warn/90' : 'border-line text-muted'"
  >
    <span class="label mr-2 align-middle" :class="tone === 'warn' ? 'text-warn' : ''">
      {{ tone === 'warn' ? 'Atenção' : 'Nota' }}
    </span>
    <slot />
  </p>
</template>
