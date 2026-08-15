# Informe de pruebas — Reverse Agent (antes Qwen Code)

Fecha: 2026-08-06 (America/Bogota)

## Resumen

El árbol completo compila y los caminos principales del producto fueron probados contra el backend real de Qwen. Durante la matriz se encontraron y corrigieron cuatro problemas reales:

1. El ejecutable vendorizado de ripgrep no estaba incluido en el source map.
2. La TUI cargaba un stub de `color-diff-napi` sin método `render()`.
3. El backend web de Qwen intentaba ejecutar nombres de herramientas locales por su cuenta y devolvía `Tool X does not exists`.
4. Qwen podía devolver streams vacíos durante límites transitorios y el puente los trataba como éxito.

## Resultados

| Área | Prueba | Resultado |
|---|---|---|
| Build | Bundle de `src/entry.ts` | ✅ 3.852 módulos, 19,84 MB |
| Puente | Unit tests Python | ✅ 6/6 |
| API | `/health` | ✅ |
| Modelos | Descubrimiento `/v1/models` | ✅ 3 modelos publicados |
| Modelo | `qwen3.8-max` | ✅ |
| Modelo | `qwen3.7-plus` | ✅ |
| Modelo | `qwen3.7-max` | ✅ |
| Modelo | `qwen3.8-max-thinking` | ✅ |
| Salida | texto | ✅ |
| Salida | JSON | ✅ |
| Salida | stream-json | ✅ |
| Entrada | stream-json por stdin | ✅ |
| Herramienta | Read | ✅ llamada real y resultado leído |
| Herramienta | Write | ✅ archivo creado |
| Herramienta | Edit | ✅ `uno` → `dos` verificado en disco |
| Herramienta | Bash | ✅ comando ejecutado |
| Herramienta | Glob | ✅ coincidencias encontradas |
| Herramienta | Grep | ✅ coincidencia `needle` encontrada |
| Registro | Herramientas base | ✅ 24 herramientas cargadas |
| Agentes | Agente personalizado con `--agents/--agent` | ✅ `CUSTOM_AGENT_OK` |
| Agentes | Subagente `general-purpose` mediante Agent | ✅ hijo y padre completados |
| MCP | Servidor MCP stdio temporal + herramienta echo | ✅ `MCP_ECHO:ping` |
| Skills | Skill local temporal | ✅ `SKILL_OK` |
| Hooks | Hook `SessionStart` por comando | ✅ marcador escrito |
| Structured output | `--json-schema` | ✅ `{ "status": "schema_ok" }` |
| TUI | Arranque en pseudo-terminal | ✅ sin error de renderizado |
| TUI | `/help` | ✅ diálogo abierto/cerrado |
| TUI | `/model` | ✅ muestra `qwen3.8-max` actual |
| TUI | `/agents` | ✅ muestra agentes incorporados |
| TUI | `/exit` | ✅ salida limpia, código 0 |
| Ripgrep | Ejecución directa | ✅ ripgrep 15.0.0 |

## Correcciones aplicadas durante las pruebas

### Ripgrep multiplataforma

Se añadió `@vscode/ripgrep` y `src/utils/ripgrep.ts` ahora resuelve el binario del paquete específico de plataforma. Esto rehabilitó `Glob` y `Grep`.

### Renderizado de diferencias

`src/components/StructuredDiff/colorDiff.ts` usa ahora la implementación TypeScript completa de `src/native-ts/color-diff/` en lugar del stub nativo incompleto. La TUI volvió a renderizar diferencias sin lanzar `render is not a function`.

### Herramientas con Qwen

El puente ahora:

- desactiva tool-search/deferred tools no compatibles;
- presenta todas las herramientas al modelo;
- usa envolturas de texto `<qwen_local_tool>`;
- asigna alias neutrales y los traduce al nombre real;
- reconoce JSON puro, JSON con prefijo/sufijo y formato `[Tool call: ...]`;
- conserva `tool_use`/`tool_result` entre turnos.

### Fiabilidad

Las respuestas vacías se reintentan hasta tres veces. Los eventos se recolectan antes de iniciar la respuesta HTTP, evitando convertir un fallo tardío del backend en una respuesta SSE exitosa y vacía.

## Limitaciones verificadas

- `tsc --noEmit` sobre los más de 2.100 archivos supera la memoria disponible del sandbox: con el límite normal abortó cerca de 1 GB y con 4 GB el sistema operativo terminó el proceso. La compilación real de Bun sí finaliza correctamente.
- No se probaron funciones que requieren hardware o servicios externos ausentes: captura de voz, control de navegador/Chrome, SSH remoto, teletransporte, proveedores Bedrock/Vertex/Foundry y conectores empresariales.
- `qwen-reverse` depende de endpoints web no oficiales. En una ráfaga de pruebas Qwen devolvió un `internal_error` transitorio; los nuevos reintentos evitaron respuestas vacías posteriores.
