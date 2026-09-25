<script setup lang="ts">
/**
 * O fundo: a prancheta.
 *
 * Uma grade de 44px desenhada em canvas, sobre o violeta quase preto da
 * base. Três
 * coisas acontecem nela, e nenhuma é enfeite solto:
 *
 * 1. **A passada do plotter** — uma faixa vertical atravessa a tela devagar,
 *    acendendo as linhas por onde passa. É o gesto que dá nome ao movimento do
 *    projeto inteiro: a página é plotada, não exibida.
 * 2. **Os pontos sob o cursor** — os cruzamentos da grade acendem em volta do
 *    ponteiro, com queda pela distância. A prancheta responde a quem aponta.
 * 3. **Os pontos que piscam** — alguns cruzamentos acendem e apagam sozinhos,
 *    em ritmo irregular. É a leitura do dado chegando.
 *
 * Canvas em vez de DOM porque são centenas de elementos repintados por quadro;
 * em `div`s isso seria um massacre de layout. O laço é o `gsap.ticker`, o mesmo
 * relógio das outras animações, então tudo anda em fase.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { gsap } from 'gsap'
import { pointer, prefersReducedMotion } from '@/motion'

const canvas = ref<HTMLCanvasElement | null>(null)

const GRID = 44
const BASE_ALPHA = 0.028
const SWEEP_SECONDS = 14
const CURSOR_RADIUS = 190

let context: CanvasRenderingContext2D | null = null
let width = 0
let height = 0
let elapsed = 0

/** Cruzamentos que piscam: posição em células e fase própria. */
let blinkers: { col: number; row: number; phase: number; speed: number }[] = []

function resize() {
  const element = canvas.value
  if (!element) return
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  width = window.innerWidth
  height = window.innerHeight
  element.width = Math.floor(width * ratio)
  element.height = Math.floor(height * ratio)
  element.style.width = `${width}px`
  element.style.height = `${height}px`
  context = element.getContext('2d')
  context?.setTransform(ratio, 0, 0, ratio, 0, 0)

  // Um punhado de piscadas, proporcional à área: telas grandes não ficam
  // vazias, celulares não pagam por pontos que ninguém vê.
  const count = Math.round((width * height) / 52000)
  const columns = Math.ceil(width / GRID)
  const rows = Math.ceil(height / GRID)
  blinkers = Array.from({ length: count }, () => ({
    col: Math.floor(Math.random() * columns),
    row: Math.floor(Math.random() * rows),
    phase: Math.random() * Math.PI * 2,
    speed: 0.6 + Math.random() * 1.8,
  }))
}

function draw(time: number) {
  const ctx = context
  if (!ctx) return
  ctx.clearRect(0, 0, width, height)

  // A faixa do plotter, em posição normalizada de 0 a 1.
  const sweep = ((time % SWEEP_SECONDS) / SWEEP_SECONDS) * (width + 400) - 200

  ctx.lineWidth = 1

  for (let x = 0; x <= width; x += GRID) {
    const distance = Math.abs(x - sweep)
    const boost = distance < 180 ? (1 - distance / 180) * 0.09 : 0
    ctx.strokeStyle = `rgba(247, 242, 255, ${BASE_ALPHA + boost})`
    ctx.beginPath()
    ctx.moveTo(x + 0.5, 0)
    ctx.lineTo(x + 0.5, height)
    ctx.stroke()
  }

  ctx.strokeStyle = `rgba(247, 242, 255, ${BASE_ALPHA})`
  for (let y = 0; y <= height; y += GRID) {
    ctx.beginPath()
    ctx.moveTo(0, y + 0.5)
    ctx.lineTo(width, y + 0.5)
    ctx.stroke()
  }

  // Cruzamentos que piscam — a leitura chegando.
  for (const blinker of blinkers) {
    const pulse = (Math.sin(time * blinker.speed + blinker.phase) + 1) / 2
    if (pulse < 0.72) continue
    const alpha = (pulse - 0.72) / 0.28
    ctx.fillStyle = `rgba(255, 0, 106, ${alpha * 0.7})`
    ctx.fillRect(blinker.col * GRID - 1, blinker.row * GRID - 1, 3, 3)
  }

  // Cruzamentos sob o cursor.
  if (pointer.active) {
    const firstCol = Math.floor((pointer.x - CURSOR_RADIUS) / GRID)
    const lastCol = Math.ceil((pointer.x + CURSOR_RADIUS) / GRID)
    const firstRow = Math.floor((pointer.y - CURSOR_RADIUS) / GRID)
    const lastRow = Math.ceil((pointer.y + CURSOR_RADIUS) / GRID)

    for (let col = firstCol; col <= lastCol; col += 1) {
      for (let row = firstRow; row <= lastRow; row += 1) {
        const x = col * GRID
        const y = row * GRID
        const distance = Math.hypot(x - pointer.x, y - pointer.y)
        if (distance > CURSOR_RADIUS) continue
        const falloff = 1 - distance / CURSOR_RADIUS
        ctx.fillStyle = `rgba(255, 0, 106, ${falloff * falloff * 0.85})`
        ctx.fillRect(x - 1, y - 1, 2.5, 2.5)
      }
    }
  }
}

function tick() {
  elapsed += gsap.ticker.deltaRatio(60) / 60
  draw(elapsed)
}

onMounted(() => {
  resize()
  window.addEventListener('resize', resize, { passive: true })
  if (prefersReducedMotion()) {
    draw(0)
    return
  }
  gsap.ticker.add(tick)
})

onBeforeUnmount(() => {
  gsap.ticker.remove(tick)
  window.removeEventListener('resize', resize)
})
</script>

<template>
  <canvas
    ref="canvas"
    class="pointer-events-none fixed inset-0 -z-10 h-full w-full"
    aria-hidden="true"
  />
</template>
