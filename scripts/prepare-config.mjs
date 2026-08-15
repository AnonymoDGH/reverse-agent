#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Qwen no necesita el onboarding OAuth de Anthropic. Conservamos el diálogo
// de confianza por proyecto, pero preparamos tema y la clave local ficticia.
const file = path.join(os.homedir(), '.claude.json');
let config = {};
try {
  if (existsSync(file)) config = JSON.parse(readFileSync(file, 'utf8'));
} catch {
  // Si el archivo previo no es JSON válido, el CLI mostrará su propio aviso.
  process.exit(0);
}
const approved = new Set(config.customApiKeyResponses?.approved ?? []);
approved.add('qwen-reverse');
config = {
  ...config,
  hasCompletedOnboarding: true,
  theme: config.theme || 'dark',
  customApiKeyResponses: {
    ...(config.customApiKeyResponses ?? {}),
    approved: [...approved],
    rejected: (config.customApiKeyResponses?.rejected ?? []).filter(key => key !== 'qwen-reverse'),
  },
};
mkdirSync(path.dirname(file), { recursive: true });
writeFileSync(file, JSON.stringify(config, null, 2) + '\n', { mode: 0o600 });
