# Reverse Agent — inicio con un solo comando

## Requisitos previos

Instala solamente:

1. **Node.js 20 o superior:** https://nodejs.org
2. **Python 3.10 o superior:** https://python.org

Durante la instalación de Python en Windows, marca **Add Python to PATH**.

## Ejecutar

Descomprime el ZIP, abre una terminal dentro de su carpeta y ejecuta:

```bash
npm start
```

Eso es todo. El primer arranque automáticamente:

- instala Bun y las dependencias TypeScript;
- crea `.venv`;
- instala `qwen-reverse`;
- prepara la configuración local;
- inicia el bridge multi-proveedor;
- abre la TUI de Reverse Agent;
- detiene el servidor al salir.

La primera vez solo tendrás que confirmar que confías en la carpeta donde lo ejecutas.

## Accesos alternativos

### Windows

```powershell
.\iniciar.cmd
```

O:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
```

### macOS/Linux

```bash
./iniciar.sh
```

## Ejecutar una tarea directamente

```bash
npm start -- --print "revisa el proyecto y corrige los tests" --output-format text
```

## Elegir modelo

### macOS/Linux

```bash
QWEN_MODEL=qwen3.7-plus npm start
```

### PowerShell

```powershell
$env:QWEN_MODEL="qwen3.7-plus"; npm start
```

Modelos Qwen disponibles:

- `qwen3.8-max-thinking` — predeterminado;
- `qwen3.8-max`;
- `qwen3.7-plus`;
- `qwen3.7-max`.

### Otros proveedores

Con su API key configurada, usa el prefijo correspondiente:

```bash
# OpenRouter
OPENROUTER_API_KEY=sk-or-... QWEN_MODEL=openrouter/anthropic/claude-sonnet-4.5 npm start

# Groq
GROQ_API_KEY=gsk_... QWEN_MODEL=groq/llama-3.3-70b-versatile npm start

# DeepSeek
DEEPSEEK_API_KEY=sk-... QWEN_MODEL=deepseek/deepseek-reasoner npm start

# Ollama / LM Studio / vLLM (local)
OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1 QWEN_MODEL=local/llama3.1 npm start
```

Dentro de la TUI, `/model` lista todos los modelos de los proveedores configurados.

## Cuenta opcional

El modo anónimo funciona sin clave. Para usar un token de `chat.qwen.ai`,
configura `QWEN_TOKEN` antes de iniciar.

## Solución rápida de problemas

- **Node no encontrado:** instala Node.js 20+ y abre una terminal nueva.
- **Python no encontrado:** instala Python 3.10+ y habilita PATH.
- **Windows bloquea PowerShell:** usa `iniciar.cmd`.
- **El backend web limita solicitudes:** espera unos minutos y vuelve a ejecutar `npm start`.
- **Un proveedor da error de autenticación:** revisa su variable de API key en `.env.example`.
