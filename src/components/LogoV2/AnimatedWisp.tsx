import * as React from 'react'
import { useEffect, useRef, useState } from 'react'
import { Box } from '../../ink.js'
import { getInitialSettings } from '../../utils/settings/settings.js'
import { Wisp, type WispPose } from './Wisp.js'

type Frame = {
  pose: WispPose
  offset: number
}

/** Mantiene una pose durante n frames (60 ms cada uno). */
function hold(pose: WispPose, offset: number, frames: number): Frame[] {
  return Array.from({ length: frames }, () => ({ pose, offset }))
}

// Semántica del offset: marginTop dentro de un contenedor de altura fija 3.
// 0 = normal, 1 = agachado. La altura del contenedor se mantiene en 3 para que
// el layout nunca se mueva; durante el agache (offset=1) la fila de la cola de
// Wisp queda recortada — se lee como "se agacha bajo el marco" antes de saltar.

// Animación de clic: agacharse y saltar con las esquinas levantadas. Dos veces.
const JUMP_WAVE: readonly Frame[] = [
  ...hold('default', 1, 2), // agacharse
  ...hold('arms-up', 0, 3), // ¡saltar!
  ...hold('default', 0, 1),
  ...hold('default', 1, 2), // agacharse otra vez
  ...hold('arms-up', 0, 3), // ¡saltar!
  ...hold('default', 0, 1),
]

// Animación de clic: mirar a la derecha, luego a la izquierda, y volver.
const LOOK_AROUND: readonly Frame[] = [
  ...hold('look-right', 0, 5),
  ...hold('look-left', 0, 5),
  ...hold('default', 0, 1),
]

const CLICK_ANIMATIONS: readonly (readonly Frame[])[] = [JUMP_WAVE, LOOK_AROUND]
const IDLE: Frame = { pose: 'default', offset: 0 }
const FRAME_MS = 60
const incrementFrame = (i: number) => i + 1
const WISP_HEIGHT = 3

/**
 * Wisp con animaciones disparadas por clic (agacharse-saltar con las esquinas
 * arriba, o mirar alrededor). La altura del contenedor es fija (WISP_HEIGHT) —
 * la misma huella que un `<Wisp />` simple — así el layout circundante nunca
 * se mueve. El clic solo dispara cuando el tracking de mouse está activo
 * (dentro de `<AlternateScreen>` / pantalla completa); en cualquier otro lado
 * se renderiza y comporta igual que un `<Wisp />` plano.
 */
export function AnimatedWisp() {
  const { pose, bounceOffset, onClick } = useWispAnimation()
  return (
    <Box height={WISP_HEIGHT} flexDirection="column" onClick={onClick}>
      <Box marginTop={bounceOffset} flexShrink={0}>
        <Wisp pose={pose} />
      </Box>
    </Box>
  )
}

function useWispAnimation(): {
  pose: WispPose
  bounceOffset: number
  onClick: () => void
} {
  // Se lee una vez al montar — sin suscripción a useSettings(), para no
  // re-renderizar en cada cambio de configuración.
  const [reducedMotion] = useState(
    () => getInitialSettings().prefersReducedMotion ?? false,
  )
  const [frameIndex, setFrameIndex] = useState(-1)
  const sequenceRef = useRef<readonly Frame[]>(JUMP_WAVE)

  const onClick = () => {
    if (reducedMotion || frameIndex !== -1) return
    sequenceRef.current =
      CLICK_ANIMATIONS[Math.floor(Math.random() * CLICK_ANIMATIONS.length)]!
    setFrameIndex(0)
  }

  useEffect(() => {
    if (frameIndex === -1) return
    if (frameIndex >= sequenceRef.current.length) {
      setFrameIndex(-1)
      return
    }
    const timer = setTimeout(setFrameIndex, FRAME_MS, incrementFrame)
    return () => clearTimeout(timer)
  }, [frameIndex])

  const seq = sequenceRef.current
  const current =
    frameIndex >= 0 && frameIndex < seq.length ? seq[frameIndex]! : IDLE
  return {
    pose: current.pose,
    bounceOffset: current.offset,
    onClick,
  }
}
