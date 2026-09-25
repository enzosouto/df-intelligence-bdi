import { onBeforeUnmount, ref, type Ref } from 'vue'

/**
 * Media query reativa. Para decisões de CONTEÚDO que o CSS sozinho não resolve
 * (quantas linhas de ranking mostrar, se um bloco nasce aberto). Para layout,
 * as classes responsivas do Tailwind continuam sendo o caminho.
 */
export function useMedia(query: string): Ref<boolean> {
  const list = typeof window !== 'undefined' ? window.matchMedia(query) : null
  const matches = ref(list?.matches ?? false)
  const update = (event: MediaQueryListEvent) => (matches.value = event.matches)
  list?.addEventListener('change', update)
  onBeforeUnmount(() => list?.removeEventListener('change', update))
  return matches
}

/** Abaixo do `sm` do Tailwind (640px): celular. */
export const useIsPhone = () => useMedia('(max-width: 639px)')
