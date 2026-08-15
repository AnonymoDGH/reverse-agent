// Entry point executable. Registra el polyfill de bun:bundle antes de cargar
// el programa; luego invoca explícitamente main(), que en el source map solo
// estaba exportado porque el wrapper de producción no fue incluido.
import { plugin } from 'bun'

plugin({
  name: 'bun-bundle-polyfill',
  setup(build) {
    build.onResolve({ filter: /^bun:bundle$|^bundle$/ }, () => ({
      path: import.meta.dir + '/stubs/bun-bundle-runtime.ts',
      namespace: 'file',
    }))
  },
})

const { main } = await import('./main.tsx')
await main()
