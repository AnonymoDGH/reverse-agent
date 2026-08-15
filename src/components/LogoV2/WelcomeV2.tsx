import * as React from 'react'
import { Box, Text } from 'src/ink.js'

const WELCOME_V2_WIDTH = 58

/**
 * Pantalla de bienvenida de Reverse Agent. Un campo de estrellas con Wisp,
 * la mascota, en el centro. Los colores se adaptan al tema vía las claves
 * `claude` (acento de marca) y `mascot_*`.
 */
export function WelcomeV2(): React.ReactNode {
  return (
    <Box width={WELCOME_V2_WIDTH} flexDirection="column">
      <Text>
        <Text color="claude">Welcome to Reverse Agent </Text>
        <Text dimColor>v{MACRO.VERSION} </Text>
      </Text>
      <Text dimColor>{'─'.repeat(WELCOME_V2_WIDTH)}</Text>
      <Text>{'      ·        ✦           ·         ✧        ·          '}</Text>
      <Text>{'  ✧          ·        ✦          ·          ✧            '}</Text>
      <Text>
        {'        ·         ✧        '}
        <Text color="mascot_body">▄▄▄▄▄▄▄▄</Text>
        {'        ·           '}
      </Text>
      <Text>
        {'   ✦        ·        '}
        <Text color="mascot_body">▐</Text>
        <Text color="mascot_body" backgroundColor="mascot_background">▜███▛</Text>
        <Text color="mascot_body">▌</Text>
        {'      ✧        ·       '}
      </Text>
      <Text>
        {'        ✧        ·    '}
        <Text color="mascot_body">▜</Text>
        <Text color="mascot_body" backgroundColor="mascot_background">█████</Text>
        <Text color="mascot_body">▛</Text>
        {'   ·         ✦         '}
      </Text>
      <Text>
        {'  ·        ✦           '}
        <Text color="mascot_body">▚▞▚▞▚▞▚▞</Text>
        {'        ✧        ·     '}
      </Text>
      <Text>{'        ✦        ·         ✧         ·        ✧           '}</Text>
      <Text dimColor>{'─'.repeat(WELCOME_V2_WIDTH)}</Text>
    </Box>
  )
}
