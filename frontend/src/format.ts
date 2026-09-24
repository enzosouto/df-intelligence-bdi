/** Formatação pt-BR. Tudo que vai para a tela passa por aqui. */

const integer = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const oneDecimal = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const compact = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })

/** Ausência de dado nunca vira zero. */
export const EMPTY = '—'

export function num(value: number | null | undefined): string {
  return value === null || value === undefined ? EMPTY : integer.format(value)
}

export function dec(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return EMPTY
  return digits === 1
    ? oneDecimal.format(value)
    : new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(value)
}

export function short(value: number | null | undefined): string {
  return value === null || value === undefined ? EMPTY : compact.format(value)
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return EMPTY
  const sign = value > 0 ? '+' : ''
  return `${sign}${dec(value, digits)}%`
}

export function temperature(value: number | null | undefined): string {
  return value === null || value === undefined ? EMPTY : `${dec(value, 1)} °C`
}

const MONTHS = [
  'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
  'jul', 'ago', 'set', 'out', 'nov', 'dez',
]

export function monthLabel(iso: string): string {
  const [year, month] = iso.split('-')
  return `${MONTHS[Number(month) - 1]}/${year.slice(2)}`
}

export function fullDate(iso: string | null | undefined): string {
  if (!iso) return EMPTY
  return new Date(iso).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return EMPTY
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const DOMAIN_COLORS: Record<string, string> = {
  population: '#5EE6C5',
  security: '#FF6B81',
  health: '#4CC2FF',
  weather: '#A98BFF',
  quality: '#F5A524',
}

export const DOMAIN_LABELS: Record<string, string> = {
  population: 'População',
  security: 'Segurança',
  health: 'Saúde',
  weather: 'Clima',
  quality: 'Qualidade dos dados',
}
