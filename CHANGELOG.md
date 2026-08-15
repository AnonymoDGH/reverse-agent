# Changelog — Reverse Agent

## [2.0.0] - 2026-08-16

### Rebrand
- El producto pasa de "Qwen Code" a **Reverse Agent**: CLI `reverse-agent`,
  título de proceso, banner de versión, ayuda, pantalla de bienvenida,
  logo condensado, título de terminal, user agent y atribución de commits.
- 401 cadenas "Claude Code" y 176 invocaciones de subcomandos `claude ...`
  reemplazadas por su equivalente de Reverse Agent.
- Los prompts de sistema ahora presentan al agente como
  "Reverse Agent, a multi-provider terminal coding agent".

### Identidad visual
- Nueva paleta de marca en los 6 temas: cian + violeta + fucsia
  (antes naranja Claude). Claves de tema `clawd_*` renombradas a `mascot_*`.
- Nueva mascota **Wisp** (fantasma del espacio profundo) con animaciones de
  clic, en reemplazo del logo clonado.
- Pantalla de bienvenida rediseñada: campo de estrellas con Wisp.

### Proveedores
- Registro de proveedores en el bridge: qwen-reverse (principal),
  OpenCode Zen, OpenRouter, Groq, DeepSeek y OpenAI-compatible local
  (Ollama/LM Studio/vLLM), con ruteo por prefijo de modelo.
- Catálogo de modelos de proveedor en el picker `/model` de la TUI.
- Nuevo comando `/providers` para ver el estado de cada proveedor.
- `/v1/models` agrega las listas en vivo de todos los proveedores configurados.

### Infraestructura
- Scripts multiplataforma: `test:bridge`, `test:local` funcionan en Windows.
- `REVERSE_AGENT_FEATURES` como variable de feature flags (con fallback).
- README, INICIO_RAPIDO y .env.example reescritos.
- Repo git inicializado con historial por cambio y publicado en GitHub.

## [1.0.0] - 2026-08-07
- Reconstrucción original del CLI sobre el backend qwen-reverse.
