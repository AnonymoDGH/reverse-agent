import * as React from 'react'
import { Box, Text } from '../../ink.js'
import { env } from '../../utils/env.js'

/**
 * Wisp — la mascota de Reverse Agent. Un pequeño fantasma del espacio
 * profundo que viaja "al revés" por tu código. Misma huella que la mascota
 * anterior (8-9 columnas × 3 filas) para no mover el layout.
 */
export type WispPose =
  | 'default'
  | 'arms-up' // esquinas superiores levantadas (durante el salto)
  | 'look-left' // pupilas desplazadas a la izquierda
  | 'look-right' // pupilas desplazadas a la derecha

type Props = {
  pose?: WispPose
}

// Fragmentos por pose. Cada fila se parte en segmentos para poder variar solo
// lo que cambia (ojos, esquinas) manteniendo estables los spans de cuerpo/fondo.
// Fila 1: 8 columnas · Filas 2 y 3: 9 columnas.
//
// Los ojos usan huecos de color de fondo en las esquinas:
//   default   → ▜███▛ (pupilas arriba, mirando al vacío)
//   look-left → ▟███▟ (pupilas a la izquierda)
//   look-right→ ▙███▙ (pupilas a la derecha)
type Segments = {
  /** fila 1 izquierda: esquina + opcional "brazo" levantado */
  r1L: string
  /** fila 1 ojos (con fondo): ojo izquierdo, frente, ojo derecho */
  r1E: string
  /** fila 1 derecha: opcional "brazo" levantado + esquina */
  r1R: string
  /** fila 2 izquierda: costado del cuerpo */
  r2L: string
  /** fila 2 derecha: costado del cuerpo */
  r2R: string
}

const POSES: Record<WispPose, Segments> = {
  default: {
    r1L: ' ▐',
    r1E: '▜███▛',
    r1R: '▌',
    r2L: ' ▜',
    r2R: '▛ ',
  },
  'look-left': {
    r1L: ' ▐',
    r1E: '▟███▟',
    r1R: '▌',
    r2L: ' ▜',
    r2R: '▛ ',
  },
  'look-right': {
    r1L: ' ▐',
    r1E: '▙███▙',
    r1R: '▌',
    r2L: ' ▜',
    r2R: '▛ ',
  },
  'arms-up': {
    r1L: '▗▟',
    r1E: '▜███▛',
    r1R: '▙▖',
    r2L: ' ▜',
    r2R: '▛ ',
  },
}

// Apple Terminal usa relleno de fondo (ver abajo); solo tienen sentido las
// poses de ojos.
const APPLE_EYES: Record<WispPose, string> = {
  default: ' ▖   ▗ ',
  'look-left': ' ▘   ▘ ',
  'look-right': ' ▝   ▝ ',
  'arms-up': ' ▖   ▗ ',
}

export function Wisp({ pose = 'default' }: Props) {
  if (env.terminal === 'Apple_Terminal') {
    return <AppleTerminalWisp pose={pose} />
  }
  const p = POSES[pose]
  return (
    <Box flexDirection="column">
      <Text>
        <Text color="mascot_body">{p.r1L}</Text>
        <Text color="mascot_body" backgroundColor="mascot_background">
          {p.r1E}
        </Text>
        <Text color="mascot_body">{p.r1R}</Text>
      </Text>
      <Text>
        <Text color="mascot_body">{p.r2L}</Text>
        <Text color="mascot_body" backgroundColor="mascot_background">
          █████
        </Text>
        <Text color="mascot_body">{p.r2R}</Text>
      </Text>
      {/* Cola ondulada del fantasma */}
      <Text color="mascot_body">{'  ▚▞▚▞▚▞▚▞  '}</Text>
    </Box>
  )
}

function AppleTerminalWisp({ pose }: { pose: WispPose }) {
  const eyes = APPLE_EYES[pose]
  return (
    <Box flexDirection="column" alignItems="center">
      <Text>
        <Text color="mascot_body">▗</Text>
        <Text color="mascot_background" backgroundColor="mascot_body">
          {eyes}
        </Text>
        <Text color="mascot_body">▖</Text>
      </Text>
      <Text backgroundColor="mascot_body">{' '.repeat(7)}</Text>
      <Text color="mascot_body">▚▞▚▞▚</Text>
    </Box>
  )
}
