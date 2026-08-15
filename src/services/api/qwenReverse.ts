import { isEnvTruthy } from '../../utils/envUtils.js'

/**
 * Configuración central del backend qwen-reverse.
 *
 * Este fork usa Qwen por defecto. Para volver a otro endpoint compatible se
 * puede definir ANTHROPIC_BASE_URL explícitamente o desactivar QWEN_REVERSE.
 */
export const DEFAULT_QWEN_REVERSE_URL = 'http://127.0.0.1:8090'
export const DEFAULT_QWEN_MODEL = 'qwen3.8-max-thinking'
export const DEFAULT_QWEN_SMALL_MODEL = 'qwen3.8-max'
export const QWEN_DUMMY_API_KEY = 'qwen-reverse'

// ---------------------------------------------------------------------------
// Catálogo de modelos Qwen conocidos
// ---------------------------------------------------------------------------

export interface QwenModelInfo {
  id: string
  displayName: string
  shortName: string
  description: string
  /** Modelo con capacidad de razonamiento extendido (thinking) */
  thinking: boolean
  /** Modelo rápido / ligero */
  fast: boolean
}

/**
 * Todos los modelos de qwen-reverse conocidos. El orden determina la
 * prioridad en el picker de /model. Basado en qwen_reverse/models.py.
 *
 * MODELS_REQUIRE_THINKING (thinking por defecto):
 *   qwen3.8-max-preview, qwen3.8-max, qwen3.7-plus, qwen3.7-max, qwen3.6-plus
 */
export const QWEN_MODELS: readonly QwenModelInfo[] = [
  {
    id: 'qwen3.8-max',
    displayName: 'Qwen 3.8 Max',
    shortName: 'Qwen 3.8 Max',
    description: 'Más capaz · razonamiento extendido por defecto',
    thinking: true,
    fast: false,
  },
  {
    id: 'qwen3.8-max-preview',
    displayName: 'Qwen 3.8 Max Preview',
    shortName: 'Qwen 3.8 Preview',
    description: 'Versión preview del modelo más capaz',
    thinking: true,
    fast: false,
  },
  {
    id: 'qwen3.7-max',
    displayName: 'Qwen 3.7 Max',
    shortName: 'Qwen 3.7 Max',
    description: 'Modelo previo de alta capacidad',
    thinking: true,
    fast: false,
  },
  {
    id: 'qwen3.7-plus',
    displayName: 'Qwen 3.7 Plus',
    shortName: 'Qwen 3.7 Plus',
    description: 'Equilibrio entre calidad y velocidad',
    thinking: true,
    fast: false,
  },
  {
    id: 'qwen3.6-plus',
    displayName: 'Qwen 3.6 Plus',
    shortName: 'Qwen 3.6 Plus',
    description: 'Modelo 3.6 con thinking · estable',
    thinking: true,
    fast: false,
  },
  {
    id: 'qwen3-coder-plus',
    displayName: 'Qwen 3 Coder Plus',
    shortName: 'Qwen Coder',
    description: 'Optimizado para programación',
    thinking: false,
    fast: false,
  },
  {
    id: 'qwen3.5-flash',
    displayName: 'Qwen 3.5 Flash',
    shortName: 'Qwen Flash',
    description: 'El más rápido para respuestas cortas',
    thinking: false,
    fast: true,
  },
  {
    id: 'qwen3.5-plus',
    displayName: 'Qwen 3.5 Plus',
    shortName: 'Qwen 3.5 Plus',
    description: 'Modelo 3.5 de uso general',
    thinking: false,
    fast: false,
  },
  {
    id: 'qwen3-vl-plus',
    displayName: 'Qwen 3 VL Plus',
    shortName: 'Qwen VL',
    description: 'Modelo con capacidades de visión',
    thinking: false,
    fast: false,
  },
] as const

/** Mapa id → info para lookup rápido. */
const QWEN_MODEL_MAP = new Map<string, QwenModelInfo>(
  QWEN_MODELS.map(m => [m.id, m]),
)

// ---------------------------------------------------------------------------
// Funciones de consulta
// ---------------------------------------------------------------------------

export function isQwenReverseEnabled(): boolean {
  return process.env.QWEN_REVERSE === undefined
    ? true
    : isEnvTruthy(process.env.QWEN_REVERSE)
}

export function getQwenReverseBaseUrl(): string | undefined {
  if (!isQwenReverseEnabled()) return process.env.ANTHROPIC_BASE_URL
  return (
    process.env.QWEN_REVERSE_BASE_URL ||
    process.env.ANTHROPIC_BASE_URL ||
    DEFAULT_QWEN_REVERSE_URL
  ).replace(/\/$/, '')
}

export function getQwenModel(fallback = DEFAULT_QWEN_MODEL): string {
  return process.env.QWEN_MODEL || process.env.ANTHROPIC_MODEL || fallback
}

/** Devuelve la info de un modelo Qwen conocido, o undefined. */
export function getQwenModelInfo(modelId: string): QwenModelInfo | undefined {
  return QWEN_MODEL_MAP.get(modelId)
}

/** Nombre legible para la UI. Devuelve el ID si no lo reconoce. */
export function getQwenModelDisplayName(modelId: string): string {
  return QWEN_MODEL_MAP.get(modelId)?.displayName ?? modelId
}

/** Lista de IDs de modelos disponibles. */
export function getQwenAvailableModelIds(): string[] {
  return QWEN_MODELS.map(m => m.id)
}

/** Verifica si un string es un modelo Qwen conocido. */
export function isKnownQwenModel(modelId: string): boolean {
  return QWEN_MODEL_MAP.has(modelId) || modelId.startsWith('qwen')
}
