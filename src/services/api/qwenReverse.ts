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
  return (
    QWEN_MODEL_MAP.get(modelId)?.displayName ??
    PROVIDER_MODEL_MAP.get(modelId)?.displayName ??
    modelId
  )
}

/** Lista de IDs de modelos disponibles. */
export function getQwenAvailableModelIds(): string[] {
  return QWEN_MODELS.map(m => m.id)
}

/** Verifica si un string es un modelo Qwen conocido o de proveedor. */
export function isKnownQwenModel(modelId: string): boolean {
  return (
    QWEN_MODEL_MAP.has(modelId) ||
    modelId.startsWith('qwen') ||
    isKnownProviderModel(modelId)
  )
}

// ---------------------------------------------------------------------------
// Catálogo de modelos de proveedores adicionales (detrás del bridge)
// ---------------------------------------------------------------------------

export type ProviderId = 'zen' | 'openrouter' | 'groq' | 'deepseek' | 'local'

export interface ProviderModelInfo {
  /** ID completo con prefijo de proveedor, tal como viaja al bridge. */
  id: string
  provider: ProviderId
  displayName: string
  description: string
  thinking: boolean
  fast: boolean
}

/** Nombre legible de cada proveedor para la UI. */
export const PROVIDER_DISPLAY_NAMES: Record<ProviderId, string> = {
  zen: 'OpenCode Zen',
  openrouter: 'OpenRouter',
  groq: 'Groq',
  deepseek: 'DeepSeek',
  local: 'Local (OpenAI-compatible)',
}

/** Variable de entorno que activa cada proveedor en el bridge. */
export const PROVIDER_KEY_ENV: Record<ProviderId, string> = {
  zen: 'ZEN_API_KEY',
  openrouter: 'OPENROUTER_API_KEY',
  groq: 'GROQ_API_KEY',
  deepseek: 'DEEPSEEK_API_KEY',
  local: 'OPENAI_COMPATIBLE_BASE_URL',
}

/**
 * Modelos destacados de cada proveedor. El ID lleva el prefijo que el bridge
 * usa para rutear (opencode/, openrouter/, groq/, deepseek/, local/).
 */
export const PROVIDER_MODELS: readonly ProviderModelInfo[] = [
  // --- OpenCode Zen (gateway opencode.ai/zen) ---
  { id: 'opencode/claude-fable-5', provider: 'zen', displayName: 'Claude Fable 5 (Zen)', description: 'OpenCode Zen · Claude Fable 5', thinking: true, fast: false },
  { id: 'opencode/claude-sonnet-4-6', provider: 'zen', displayName: 'Claude Sonnet 4.6 (Zen)', description: 'OpenCode Zen · Sonnet 4.6', thinking: false, fast: false },
  { id: 'opencode/gpt-5.5-pro', provider: 'zen', displayName: 'GPT-5.5 Pro (Zen)', description: 'OpenCode Zen · GPT-5.5 Pro', thinking: true, fast: false },
  { id: 'opencode/kimi-k3', provider: 'zen', displayName: 'Kimi K3 (Zen)', description: 'OpenCode Zen · Kimi K3', thinking: false, fast: false },
  { id: 'opencode/deepseek-v4-flash-free', provider: 'zen', displayName: 'DeepSeek V4 Flash (Zen · gratis)', description: 'OpenCode Zen · gratis y rápido', thinking: false, fast: true },
  // --- OpenRouter ---
  { id: 'openrouter/openrouter/auto', provider: 'openrouter', displayName: 'Auto (OpenRouter)', description: 'OpenRouter elige el mejor modelo por prompt', thinking: false, fast: false },
  { id: 'openrouter/anthropic/claude-sonnet-4.5', provider: 'openrouter', displayName: 'Claude Sonnet 4.5 (OpenRouter)', description: 'OpenRouter · Anthropic', thinking: false, fast: false },
  { id: 'openrouter/openai/gpt-5.2', provider: 'openrouter', displayName: 'GPT-5.2 (OpenRouter)', description: 'OpenRouter · OpenAI', thinking: true, fast: false },
  { id: 'openrouter/google/gemini-3-pro', provider: 'openrouter', displayName: 'Gemini 3 Pro (OpenRouter)', description: 'OpenRouter · Google', thinking: true, fast: false },
  { id: 'openrouter/deepseek/deepseek-v3.2', provider: 'openrouter', displayName: 'DeepSeek V3.2 (OpenRouter)', description: 'OpenRouter · DeepSeek', thinking: false, fast: false },
  { id: 'openrouter/x-ai/grok-4', provider: 'openrouter', displayName: 'Grok 4 (OpenRouter)', description: 'OpenRouter · xAI', thinking: true, fast: false },
  { id: 'openrouter/qwen/qwen3-coder', provider: 'openrouter', displayName: 'Qwen3 Coder (OpenRouter)', description: 'OpenRouter · Qwen para código', thinking: false, fast: false },
  { id: 'openrouter/moonshotai/kimi-k2', provider: 'openrouter', displayName: 'Kimi K2 (OpenRouter)', description: 'OpenRouter · Moonshot', thinking: false, fast: false },
  // --- Groq (inferencia ultrarrápida) ---
  { id: 'groq/llama-3.3-70b-versatile', provider: 'groq', displayName: 'Llama 3.3 70B (Groq)', description: 'Groq · rápido y versátil', thinking: false, fast: true },
  { id: 'groq/openai/gpt-oss-120b', provider: 'groq', displayName: 'GPT-OSS 120B (Groq)', description: 'Groq · open-source 120B', thinking: true, fast: false },
  { id: 'groq/qwen/qwen3-32b', provider: 'groq', displayName: 'Qwen3 32B (Groq)', description: 'Groq · Qwen3 32B', thinking: false, fast: true },
  // --- DeepSeek directo ---
  { id: 'deepseek/deepseek-chat', provider: 'deepseek', displayName: 'DeepSeek Chat', description: 'DeepSeek V3 · uso general', thinking: false, fast: false },
  { id: 'deepseek/deepseek-reasoner', provider: 'deepseek', displayName: 'DeepSeek Reasoner', description: 'DeepSeek R1 · razonamiento', thinking: true, fast: false },
] as const

const PROVIDER_MODEL_MAP = new Map<string, ProviderModelInfo>(
  PROVIDER_MODELS.map(m => [m.id, m]),
)

/** Devuelve la info de un modelo de proveedor conocido, o undefined. */
export function getProviderModelInfo(modelId: string): ProviderModelInfo | undefined {
  return PROVIDER_MODEL_MAP.get(modelId)
}

/** Nombre legible de un modelo de proveedor; devuelve el ID si no lo reconoce. */
export function getProviderModelDisplayName(modelId: string): string {
  return PROVIDER_MODEL_MAP.get(modelId)?.displayName ?? modelId
}

/** Verifica si un string es un modelo de proveedor conocido o lleva prefijo de proveedor. */
export function isKnownProviderModel(modelId: string): boolean {
  if (PROVIDER_MODEL_MAP.has(modelId)) return true
  return (
    modelId.startsWith('opencode/') ||
    modelId.startsWith('openrouter/') ||
    modelId.startsWith('groq/') ||
    modelId.startsWith('deepseek/') ||
    modelId.startsWith('local/')
  )
}

/** IDs de todos los modelos de proveedor (para el picker). */
export function getProviderAvailableModelIds(): string[] {
  return PROVIDER_MODELS.map(m => m.id)
}
