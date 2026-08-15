# Qwen Code — reconstrucción completa en TypeScript

Este proyecto contiene el árbol completo recuperado del CLI (más de 2.100 archivos en `src/`) y lo ejecuta con **Qwen** mediante [`qwen-reverse`](https://pypi.org/project/qwen-reverse/). No es la implementación reducida creada inicialmente: el agente, REPL, herramientas, permisos, MCP, memoria, hooks, plugins, tareas y UI originales están nuevamente en `src/`.

## Cambios realizados

- Se recuperaron los módulos que no estaban presentes en el ZIP original usando la reconstrucción compilable compatible con el mismo snapshot.
- Se añadió la configuración de compilación completa para Bun y las dependencias del árbol original.
- `src/entry.ts` restaura el punto de entrada que faltaba en el source map e invoca `main()`.
- `src/services/api/qwenReverse.ts` centraliza URL, modelo y activación de Qwen.
- `src/services/api/client.ts` usa `qwen-reverse` en lugar de autenticación y servidores Anthropic.
- `src/utils/model/model.ts` selecciona modelos Qwen por defecto.
- `qwen_bridge.py` corrige incompatibilidades de `qwen-reverse 0.1.4` con:
  - system prompts estructurados;
  - streaming Anthropic SSE;
  - bloques `tool_use` y `tool_result`;
  - llamadas de herramientas seguidas por texto adicional;
  - conteo aproximado de tokens.
- `scripts/qwen-run.mjs` inicia y detiene automáticamente el backend Python.

El snapshot incompleto recibido se conserva en `original-incomplete-src/` y el primer prototipo reducido en `rewrite-prototype/`; ninguno participa en la compilación.

## Requisitos

- Node.js 20+
- Python 3.10+

Bun se instala localmente como dependencia del proyecto.

## Inicio automático — un solo comando

Con Node.js 20+ y Python 3.10+ instalados, descomprime el proyecto y ejecuta:

```bash
npm start
```

El comando instala automáticamente dependencias, Bun y `qwen-reverse`, crea el entorno Python, inicia el backend y abre la TUI. Consulta [`INICIO_RAPIDO.md`](INICIO_RAPIDO.md) para Windows, macOS y Linux.

## Uso después de la primera instalación

Modo interactivo rápido:

```bash
npm run qwen
```

Una tarea y salida:

```bash
npm run qwen -- --print "revisa este proyecto y corrige los tests" \
  --output-format text --bare --dangerously-skip-permissions
```

Cambiar modelo:

```bash
QWEN_MODEL=qwen3.8-max npm run qwen
```

Configuración disponible:

```env
QWEN_REVERSE=1
QWEN_REVERSE_BASE_URL=http://127.0.0.1:8090
QWEN_MODEL=qwen3.8-max-thinking
QWEN_TOKEN=
```

`QWEN_TOKEN` es opcional; `qwen-reverse` admite funcionamiento anónimo.

## Compilación y pruebas

```bash
npm run build
npm run test:qwen-bridge
```

La compilación genera `dist/entry.js` y su mapa de fuentes. Se verificó también manualmente el flujo completo: CLI TypeScript → puente Anthropic → qwen-reverse → Qwen → llamada de herramienta → escritura local → respuesta final.

## Aviso

`qwen-reverse` utiliza endpoints web no oficiales de Qwen. Puede dejar de funcionar si el servicio cambia y puede estar sujeto a límites o bloqueos. Úsalo conforme a los términos aplicables.
