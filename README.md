# Reverse Agent

[![CI](https://github.com/AnonymoDGH/reverse-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/AnonymoDGH/reverse-agent/actions/workflows/ci.yml)

Agente de programación para la terminal, multi-proveedor y con identidad propia.
Nació como una reconstrucción completa del CLI de Claude Code (más de 2.100
archivos en `src/`), pero hoy es un producto distinto:

- **Marca propia:** Reverse Agent, paleta cian/violeta y la mascota *Wisp*.
- **Backend principal:** [`qwen-reverse`](https://pypi.org/project/qwen-reverse/)
  a través de un puente local Anthropic-compatible (`qwen_bridge.py`).
- **Más proveedores:** OpenCode Zen, OpenRouter, Groq, DeepSeek y cualquier
  endpoint OpenAI-compatible local (Ollama, LM Studio, vLLM).
- **TUI completa:** herramientas, permisos, MCP, memoria, hooks, plugins,
  tareas, sesiones, modo plan, subagentes y pantalla completa.

## Requisitos

- Node.js 20+
- Python 3.10+

Bun se instala localmente como dependencia del proyecto.

## Inicio automático — un solo comando

```bash
npm start
```

El comando instala dependencias, Bun y `qwen-reverse`, crea el entorno
Python, inicia el bridge y abre la TUI. Consulta
[`INICIO_RAPIDO.md`](INICIO_RAPIDO.md) para Windows, macOS y Linux.

## Uso después de la primera instalación

Modo interactivo rápido:

```bash
npm run agent
```

Una tarea y salida:

```bash
npm run agent -- --print "revisa este proyecto y corrige los tests" \
  --output-format text --bare --dangerously-skip-permissions
```

## Proveedores

El bridge (`qwen_bridge.py`) expone `/v1/messages` en formato Anthropic y
rutea cada request al proveedor según el prefijo del modelo:

| Prefijo        | Proveedor            | Activación                                  |
| -------------- | -------------------- | ------------------------------------------- |
| *(ninguno)*    | qwen-reverse (web)   | siempre activo (backend principal)          |
| `opencode/`    | OpenCode Zen         | `ZEN_API_KEY` (o key local de opencode)     |
| `openrouter/`  | OpenRouter           | `OPENROUTER_API_KEY`                        |
| `groq/`        | Groq                 | `GROQ_API_KEY`                              |
| `deepseek/`    | DeepSeek             | `DEEPSEEK_API_KEY`                          |
| `local/`       | OpenAI-compatible    | `OPENAI_COMPATIBLE_BASE_URL` (Ollama, etc.) |

Ejemplos:

```bash
# Qwen (por defecto)
QWEN_MODEL=qwen3.8-max npm run agent

# OpenRouter
OPENROUTER_API_KEY=sk-or-... QWEN_MODEL=openrouter/anthropic/claude-sonnet-4.5 npm run agent

# Groq
GROQ_API_KEY=gsk_... QWEN_MODEL=groq/llama-3.3-70b-versatile npm run agent

# DeepSeek
DEEPSEEK_API_KEY=sk-... QWEN_MODEL=deepseek/deepseek-reasoner npm run agent

# Ollama local
OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1 QWEN_MODEL=local/llama3.1 npm run agent
```

También puedes cambiar de modelo dentro de la TUI con `/model`: el picker
lista los modelos Qwen y los de cada proveedor configurado. El comando
`/providers` muestra el estado de cada proveedor (activo, prefijo y modelos
destacados).

Cualquier modelo pedido sin prefijo que no sea Qwen se envía al primer
proveedor configurado; si no hay ninguno, se usa qwen-reverse.

## Configuración

```env
QWEN_REVERSE=1
QWEN_REVERSE_BASE_URL=http://127.0.0.1:8090
QWEN_MODEL=qwen3.8-max-thinking
QWEN_TOKEN=
```

`QWEN_TOKEN` es opcional; `qwen-reverse` admite funcionamiento anónimo.
El resto de variables de proveedores está en `.env.example`.

## Compilación y pruebas

```bash
npm run build
npm run test:bridge
```

La compilación genera `dist/entry.js` y su mapa de fuentes. El flujo completo
verificado: CLI TypeScript → puente Anthropic → proveedor → llamada de
herramienta → escritura local → respuesta final.

## Identidad visual

- Paleta de marca: cian (`#22d3ee`) + violeta (`#a78bfa`) + fucsia para bordes de shell.
- Mascota: **Wisp**, un fantasma del espacio profundo (reemplaza al clon del
  logo original en bienvenida, logo condensado y animaciones).
- Seis temas recalculados: dark, light, dark/light daltonizados y dark/light ANSI.

## Aviso

`qwen-reverse` utiliza endpoints web no oficiales de Qwen. Puede dejar de
funcionar si el servicio cambia y puede estar sujeto a límites o bloqueos.
Úsalo conforme a los términos aplicables. Los proveedores de API requieren sus
propias claves y términos.
