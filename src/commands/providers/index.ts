/**
 * Providers command - minimal metadata only.
 * Implementation is lazy-loaded from providers.ts to reduce startup time.
 */
import type { Command } from '../../commands.js'
import { isQwenReverseEnabled } from '../../services/api/qwenReverse.js'

const providers = {
  type: 'local',
  name: 'providers',
  description: 'Show the model providers configured behind the bridge',
  // Solo tiene sentido cuando el backend reverse está activo.
  isEnabled: () => isQwenReverseEnabled(),
  supportsNonInteractive: true,
  load: () => import('./providers.js'),
} satisfies Command

export default providers
