import type { ToolUseContext } from '../../Tool.js'
import type { LocalCommandResult } from '../../types/command.js'
import {
  PROVIDER_DISPLAY_NAMES,
  PROVIDER_KEY_ENV,
  PROVIDER_MODELS,
  getQwenReverseBaseUrl,
  isQwenReverseEnabled,
  type ProviderId,
} from '../../services/api/qwenReverse.js'

const PREFIXES: Record<ProviderId, string> = {
  zen: 'opencode/',
  openrouter: 'openrouter/',
  groq: 'groq/',
  deepseek: 'deepseek/',
  local: 'local/',
}

function isConfigured(provider: ProviderId): boolean {
  if (provider === 'local') {
    return Boolean(process.env.OPENAI_COMPATIBLE_BASE_URL)
  }
  if (provider === 'zen') {
    // El bridge también puede leer la key guardada de opencode local.
    return Boolean(process.env.ZEN_API_KEY || process.env.OPEN_CODE_API_KEY)
  }
  return Boolean(process.env[PROVIDER_KEY_ENV[provider]])
}

export async function call(
  _args: string,
  _context: ToolUseContext,
): Promise<LocalCommandResult> {
  if (!isQwenReverseEnabled()) {
    return {
      type: 'text' as const,
      value: 'El backend reverse no está activo (QWEN_REVERSE=0).',
    }
  }

  const lines: string[] = []
  lines.push('Proveedores de Reverse Agent')
  lines.push('')

  const qwenModel = process.env.QWEN_MODEL || 'qwen3.8-max-thinking'
  lines.push(`● qwen-reverse (principal) — siempre activo`)
  lines.push(`    bridge: ${getQwenReverseBaseUrl() ?? 'http://127.0.0.1:8090'}`)
  lines.push(`    modelo por defecto: ${qwenModel}`)
  lines.push('')

  const providerIds: ProviderId[] = ['zen', 'openrouter', 'groq', 'deepseek', 'local']
  for (const id of providerIds) {
    const configured = isConfigured(id)
    const mark = configured ? '●' : '○'
    const status = configured ? 'configurado' : `sin configurar (falta ${PROVIDER_KEY_ENV[id]})`
    lines.push(`${mark} ${PROVIDER_DISPLAY_NAMES[id]} — ${status}`)
    lines.push(`    prefijo: ${PREFIXES[id]}<modelo>`)
    const models = PROVIDER_MODELS.filter(m => m.provider === id)
    if (models.length > 0) {
      lines.push(`    destacados: ${models.slice(0, 3).map(m => m.id).join(', ')}`)
    }
    lines.push('')
  }

  lines.push('Cambia de modelo con /model o QWEN_MODEL=<prefijo>/<modelo>.')
  return { type: 'text' as const, value: lines.join('\n') }
}
