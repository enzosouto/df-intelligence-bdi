/** Tipos compartilhados dos gráficos. Fora do SFC porque `<script setup>` não exporta. */

export interface ChartPoint {
  x: string
  y: number | null
  /** Ponto de um período incompleto — desenhado, mas rotulado como parcial. */
  partial?: boolean
}

export interface Series {
  key: string
  label: string
  color: string
  points: ChartPoint[]
}
