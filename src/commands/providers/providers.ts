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
    // The bridge can also read the locally stored opencode key.
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
      value: 'The reverse backend is not active (QWEN_REVERSE=0).',
    }
  }

  const lines: string[] = []
  lines.push('Reverse Agent providers')
  lines.push('')

  const qwenModel = process.env.QWEN_MODEL || 'qwen3.8-max-thinking'
  lines.push(`● qwen-reverse (primary) — always active`)
  lines.push(`    bridge: ${getQwenReverseBaseUrl() ?? 'http://127.0.0.1:8090'}`)
  lines.push(`    default model: ${qwenModel}`)
  lines.push('')

  const providerIds: ProviderId[] = ['zen', 'openrouter', 'groq', 'deepseek', 'local']
  for (const id of providerIds) {
    const configured = isConfigured(id)
    const mark = configured ? '●' : '○'
    const status = configured ? 'configured' : `not configured (missing ${PROVIDER_KEY_ENV[id]})`
    lines.push(`${mark} ${PROVIDER_DISPLAY_NAMES[id]} — ${status}`)
    lines.push(`    prefix: ${PREFIXES[id]}<model>`)
    const models = PROVIDER_MODELS.filter(m => m.provider === id)
    if (models.length > 0) {
      lines.push(`    featured: ${models.slice(0, 3).map(m => m.id).join(', ')}`)
    }
    lines.push('')
  }

  lines.push('Switch models with /model or QWEN_MODEL=<prefix>/<model>.')
  return { type: 'text' as const, value: lines.join('\n') }
}
